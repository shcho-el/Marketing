"""
오블리브 콘텐츠 · 순위 모니터링 - 진입점

윈도우는 ob.bat, 맥/리눅스는 ./ob 로 짧게 쓸 수 있습니다.
  ob s          서버 실행
  ob a "제목"    제목 하나로 생성부터 업로드까지

전체 명령:
  python main.py collect      # 지금 즉시 1회 수집
  python main.py scheduler    # 매일 자동 수집 (백그라운드 실행 권장)
  python main.py dashboard    # 웹 대시보드 실행 (http://localhost:5000)
  python main.py all          # 스케줄러 + 대시보드 동시 실행
  python main.py content      # 콘텐츠 생성 앱 (http://localhost:5001)
  python main.py write        # 콘텐츠 1편 생성 (CLI)
  python main.py inspect-cms  # CMS 글쓰기 폼 분석 → 셀렉터 매핑 생성 (최초 1회)
  python main.py publish <id> # 생성한 글을 CMS에 업로드 (기본: 연습 실행)
  python main.py auto "제목"  # 제목만 넣으면 생성→검사→썸네일→업로드까지 한 번에
  python main.py doctor       # 환경 점검 (뭐가 빠졌는지 한 번에 확인)
  python main.py fonts        # 썸네일용 프리텐다드 폰트 내려받기
"""

import os
import sys
import logging
import threading

import console

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


def cmd_fonts():
    """썸네일용 폰트 내려받기."""
    import fonts

    sys.exit(fonts.run())


def cmd_doctor():
    """환경 점검."""
    import doctor

    sys.exit(doctor.run())


def cmd_auto():
    """제목만 넣으면 원고 생성부터 CMS 업로드까지 한 번에 처리한다.

      python main.py auto "송도 발톱무좀 병원 선택 기준"
      python main.py auto titles.txt          # 한 줄에 제목 하나씩
      python main.py auto "제목" --draft      # 업로드 없이 원고만
      python main.py auto "제목" --hidden     # 미노출로 업로드
      python main.py auto "제목" --dry        # 폼만 채우고 저장 안 함
    """
    import os

    import pipeline

    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    flags = {a for a in sys.argv[2:] if a.startswith("--")}

    if not args:
        print(cmd_auto.__doc__)
        return

    # 파일이면 한 줄에 제목 하나씩 읽는다.
    if len(args) == 1 and os.path.isfile(args[0]):
        with open(args[0], encoding="utf-8") as fp:
            titles = [ln.strip() for ln in fp if ln.strip() and not ln.startswith("#")]
        print(f"{args[0]}에서 제목 {len(titles)}개를 읽었습니다.")
    else:
        titles = [" ".join(args)] if len(args) > 1 else [args[0]]

    upload = "--draft" not in flags
    expose = "--hidden" not in flags
    dry_run = "--dry" in flags

    mode = (
        "원고만 생성 (업로드 없음)"
        if not upload
        else ("연습 실행 (저장 안 함)" if dry_run else ("노출 업로드" if expose else "미노출 업로드"))
    )
    print(f"모드: {mode} · 대상 {len(titles)}편\n")

    if upload and not dry_run and expose:
        print("생성한 글이 검사를 통과하면 블로그에 바로 공개됩니다.")
        if input("계속하려면 'yes' 입력: ").strip().lower() != "yes":
            print("취소했습니다.")
            return
        print()

    outcomes = pipeline.run_many(
        titles, upload=upload, expose=expose, dry_run=dry_run
    )

    print("\n===== 결과 =====")
    for outcome in outcomes:
        print(pipeline.format_outcome(outcome))
        print()
    print(pipeline.summarize(outcomes))

    blocked = [o for o in outcomes if o.get("blocked")]
    if blocked:
        print("\n의료법 검사를 통과하지 못한 글은 업로드하지 않았습니다.")
        print("웹 UI에서 지적 내용을 확인하고 수정하세요:")
        for o in blocked:
            print(f"  http://localhost:5001/post/{o.get('post_id')}")


def cmd_inspect_cms():
    """CMS 글쓰기 폼을 분석해 셀렉터 매핑을 만든다. 최초 1회, 화면 변경 시 재실행."""
    from publisher import config as cms_config
    from publisher import inspector

    if not cms_config.ensure_credentials():
        print("\n로그인 정보 없이는 폼을 읽을 수 없습니다.")
        return

    headless = "--show" not in sys.argv
    print("CMS에 로그인해 글쓰기 폼을 분석합니다...")
    if not headless:
        print("(브라우저 창을 띄웁니다)")

    # 무엇이 어디서 막혔는지 파일로 남긴다. 화면은 스크롤로 사라진다.
    os.makedirs("logs", exist_ok=True)
    handler = logging.FileHandler(os.path.join("logs", "cms.log"), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    try:
        result = inspector.inspect(headless=headless)
    except Exception as exc:
        logging.getLogger(__name__).exception("폼 읽기 실패")
        print()
        print("=" * 60)
        print("  폼을 읽지 못했습니다.")
        print("=" * 60)
        print()
        print(f"  {exc}")
        print()
        for path in getattr(exc, "evidence", []):
            print(f"  그때 화면을 남겼습니다: {path}")
        print("  자세한 기록: logs\\cms.log")
        print()
        print("  위 내용과 logs 폴더의 '실패화면' 파일을 보내 주시면 원인을 잡겠습니다.")
        print()
        return

    # 목록 화면에서 폼으로 넘어갔다면, 다음부터는 곧장 가도록 주소를 적어 둔다.
    found = result.get("write_url")
    if found:
        from publisher import config as cms_config

        cms_config._write_env("CMS_WRITE_URL", found)
        print()
        print(f"  글쓰기 폼 주소를 찾았습니다: {found}")
        print("  .env 의 CMS_WRITE_URL 에 적어 두었습니다. 다음부터는 곧장 갑니다.")

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
    from publisher import thumbnail as _thumb

    logo = _thumb.logo_status()
    print(f"대상: [{doc.get('category')}] {doc.get('h1')}")
    print(f"썸네일 로고: {logo['message'].splitlines()[0]}")
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
    "auto": cmd_auto,
    "doctor": cmd_doctor,
    "fonts": cmd_fonts,
    "inspect-cms": cmd_inspect_cms,
    "publish": cmd_publish,
}

# 짧은 이름과 한글 이름. 매번 긴 명령을 치지 않아도 되도록.
ALIASES = {
    # 서버
    "s": "content", "서버": "content", "웹": "content",
    # 생성
    "a": "auto", "생성": "auto", "글": "auto",
    "w": "write",
    # 업로드
    "p": "publish", "업로드": "publish",
    "i": "inspect-cms", "폼": "inspect-cms",
    # 점검·설정
    "d": "doctor", "점검": "doctor", "진단": "doctor",
    "f": "fonts", "폰트": "fonts",
    # 순위 모니터링
    "c": "collect", "수집": "collect",
    "순위": "dashboard",
}


def resolve(name: str) -> str:
    """입력한 명령 이름을 실제 명령으로 바꾼다."""
    name = (name or "").lower()
    return ALIASES.get(name, name)


def print_help() -> None:
    print(__doc__)
    print("짧게 쓰기:")
    print("  ob s        서버 (= content)")
    print("  ob a \"제목\"  생성부터 업로드까지 (= auto)")
    print("  ob p 3      업로드 (= publish)")
    print("  ob d        점검 (= doctor)")
    print("  ob i        CMS 폼 분석 (= inspect-cms)")
    print("  한글도 됩니다: ob 서버 / ob 생성 \"제목\" / ob 점검")
    print()


def suggest(name: str) -> None:
    """오타를 냈을 때 가까운 명령을 알려 준다."""
    import difflib

    pool = list(COMMANDS) + list(ALIASES)
    near = difflib.get_close_matches(name, pool, n=3, cutoff=0.5)
    print(f"'{name}' 은(는) 없는 명령입니다.")
    if near:
        print("혹시 이것인가요? " + ", ".join(near))
    print()


if __name__ == "__main__":
    console.use_utf8()
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    command = resolve(sys.argv[1])
    if command not in COMMANDS:
        suggest(sys.argv[1])
        print_help()
        sys.exit(1)

    # 하위 명령이 sys.argv를 그대로 읽으므로 별칭을 실제 이름으로 바꿔 둔다.
    sys.argv[1] = command
    COMMANDS[command]()
