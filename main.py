"""
네이버 키워드 순위 모니터링 - 진입점

사용법:
  python main.py collect      # 지금 즉시 1회 수집
  python main.py scheduler    # 매일 자동 수집 (백그라운드 실행 권장)
  python main.py dashboard    # 웹 대시보드 실행 (http://localhost:5000)
  python main.py all          # 스케줄러 + 대시보드 동시 실행
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
        rank_str = f"{r['rank']}위" if r["rank"] else "미노출"
        print(f"  {r['keyword']:<20} → {rank_str}")
    print("====================\n")


def cmd_scheduler():
    from scheduler import run_scheduler
    run_scheduler()


def cmd_dashboard():
    from dashboard import run_dashboard
    run_dashboard()


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
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    COMMANDS[sys.argv[1]]()
