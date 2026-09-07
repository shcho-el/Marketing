"""
네이버 키워드 순위 모니터링 - 진입점

사용법:
  python main.py collect      # 지금 즉시 1회 수집
  python main.py scheduler    # 매일 자동 수집 (백그라운드 실행 권장)
  python main.py dashboard    # 웹 대시보드 실행 (http://localhost:5000)
  python main.py all          # 스케줄러 + 대시보드 동시 실행
  python main.py content      # 콘텐츠 생성 앱 (http://localhost:5001)
  python main.py write        # 콘텐츠 1편 생성 (CLI)
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
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    COMMANDS[sys.argv[1]]()
