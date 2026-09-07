"""
네이버 키워드 순위 모니터링 - 진입점

사용법:
  python main.py collect      # 지금 즉시 1회 수집
  python main.py scheduler    # 매일 자동 수집 (백그라운드 실행 권장)
  python main.py dashboard    # 웹 대시보드 실행 (http://localhost:5000)
  python main.py all          # 스케줄러 + 대시보드 동시 실행
  python main.py content      # 콘텐츠 생성 앱 (http://localhost:5001)
  python main.py write        # 콘텐츠 1편 생성 (CLI)
  python main.py inspect-cms  # CMS 글쓰기 폼 분석 → 셀렉터 매핑 생성 (최초 1회)
  python main.py publish <id> # 생성한 글을 CMS에 업로드 (기본: 연습 실행)
"""

import sys
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def cmd_collect():
    from database import init_db, save_results
    from scraper import run_all_keywords
    from notifier import send_slack
    from config import KEYWORDS
    from datetime import date

    init_db()
    results = run_all_keywords(KEYWORDS)
    save_results(results)
    send_slack(results, check_date=date.today())

    print("\n===== 수집 결과 =====")
    for r in results:
        ranks = r.get("ranks", [])
        rank_str = ", ".join(f"{rk}위" for rk in ranks) if ranks else "미노출"
        url_str = r.get("url", "")
        title_str = r.get("title", "")
        print(f"  {r['keyword']:<20} → {rank_str}")
        if url_str:
            print(f"    URL  : {url_str}")
            print(f"    제목 : {title_str}")
    print("====================\n")


def cmd_scheduler():
    from scheduler import run_scheduler
    run_scheduler()


def cmd_dashboard():
    from dashboard import run_dashboard
    run_dashboard()


def cmd_content():
    from content_app import run_app
    run_app()


def cmd_write():
    """CLI로 콘텐츠 1편 생성. 인자를 주지 않으면 대화형으로 묻는다.

      python main.py write <카테고리> <주키워드> <주제>
    """
    from content import generator, renderer, store

    args = sys.argv[2:]
    if len(args) >= 3:
        category, primary, topic = args[0], args[1], " ".join(args[2:])
    else:
        from content.taxonomy import CATEGORIES

        print("카테고리:", " / ".join(CATEGORIES))
        category = input("카테고리> ").strip()
        primary = input("주키워드> ").strip()
        topic = input("주제> ").strip()

    print(f"\n생성 중... ({category} / {primary})")
    result = generator.generate(category, primary, topic)
    doc, reports = result["doc"], result["reports"]
    post_id = store.save(doc, reports, topic)

    print("\n===== CMS 기본 정보 =====")
    for k, v in renderer.cms_fields(doc).items():
        print(f"  {k}: {v}")

    scores = reports["seo"]["scores"]
    print("\n===== 점검 =====")
    print(f"  SEO {scores['seo']} / AEO {scores['aeo']} / GEO {scores['geo']}"
          f" → 종합 {scores['total']} ({reports['seo']['grade']})")
    print(f"  의료법: {reports['law']['summary']}")
    for f in reports["law"]["findings"]:
        print(f"    [{f['severity']}] \"{f['matched']}\" - {f['reason']}")
    print(f"\n  저장 완료 (id={post_id}). 본문은 대시보드에서 확인하세요:")
    print("    python main.py content  →  http://localhost:5001/post/%d" % post_id)


def cmd_inspect_cms():
    """CMS 글쓰기 폼을 분석해 셀렉터 매핑을 만든다. 최초 1회, 화면 변경 시 재실행."""
    from publisher import inspector

    headless = "--show" not in sys.argv
    print("CMS에 로그인해 글쓰기 폼을 분석합니다...")
    if not headless:
        print("(브라우저 창을 띄웁니다)")

    result = inspector.inspect(headless=headless)
    print(inspector.report(result["mapping"]))

    fields = result["mapping"]["fields"]
    notes = result["mapping"]["_notes"]
    unresolved = [f for f, v in fields.items() if not v]
    uncertain = [
        f for f, n in notes.items()
        if fields.get(f) and not n.get("confident")
    ]
    if unresolved or uncertain:
        print("\n확인이 필요한 항목이 있습니다.")
        if unresolved:
            print(f"  찾지 못함: {', '.join(unresolved)}")
        if uncertain:
            print(f"  라벨 불일치: {', '.join(uncertain)}")
        print("  cms_form_dump.json에서 셀렉터를 찾아 cms_mapping.json에 채워 넣으세요.")
    else:
        print("\n모든 필드를 찾았습니다. 이제 업로드를 시도할 수 있습니다.")
        print("  python main.py publish <id>        # 연습 실행")
        print("  python main.py publish <id> --save # 실제 저장 (미노출)")


def cmd_publish():
    """생성한 글을 CMS에 업로드한다.

      python main.py publish 3           # 연습 실행 (저장 안 함)
      python main.py publish 3 --save    # 실제 저장, 미노출
      python main.py publish 3 --save --expose  # 실제 저장, 노출
    """
    from content import renderer, store
    from publisher import publish as cms

    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    flags = {a for a in sys.argv[2:] if a.startswith("--")}

    if not args:
        print("사용법: python main.py publish <id> [--save] [--expose] [--show]")
        rows = store.list_posts(10)
        if rows:
            print("\n최근 생성한 글:")
            for r in rows:
                print(f"  {r['id']:>3}  [{r['category']}] {r['h1'][:50]}"
                      f"  (종합 {r['score_total']}, 상태 {r['status']})")
        return

    post_id = int(args[0])
    record = store.get(post_id)
    if not record:
        print(f"id={post_id} 글을 찾을 수 없습니다.")
        return

    dry_run = "--save" not in flags
    expose = "--expose" in flags
    headless = "--show" not in flags

    doc = record["doc"]
    print(f"대상: [{doc.get('category')}] {doc.get('h1')}")
    print(f"모드: {'연습 실행 (저장 안 함)' if dry_run else '실제 저장'}"
          f" / {'노출' if expose else '미노출'}")

    if not dry_run and expose:
        answer = input("\n노출 상태로 바로 공개됩니다. 계속하려면 'yes' 입력: ")
        if answer.strip().lower() != "yes":
            print("취소했습니다.")
            return

    try:
        result = cms.publish(
            doc=doc,
            body_html=renderer.render_body(doc, include_schema=True),
            reports=record["reports"],
            expose=expose,
            dry_run=dry_run,
            headless=headless,
        )
    except cms.ComplianceBlocked as exc:
        print(f"\n업로드 중단\n{exc}")
        return
    except Exception as exc:
        print(f"\n업로드 실패: {exc}")
        return

    print(f"\n{result['message']}")
    for shot in result.get("shots", []):
        print(f"  캡처: {shot}")
    if result.get("alert"):
        print(f"  CMS 알림: {result['alert']}")
    if result.get("saved"):
        store.set_status(post_id, "published" if expose else "uploaded")


def cmd_all():
    """스케줄러를 백그라운드 스레드로, 대시보드를 메인 스레드로 실행."""
    scheduler_thread = threading.Thread(target=cmd_scheduler, daemon=True)
    scheduler_thread.start()
    cmd_dashboard()


COMMANDS = {
    "collect": cmd_collect,
    "scheduler": cmd_scheduler,
    "dashboard": cmd_dashboard,
    "all": cmd_all,
    "content": cmd_content,
    "write": cmd_write,
    "inspect-cms": cmd_inspect_cms,
    "publish": cmd_publish,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    COMMANDS[sys.argv[1]]()
