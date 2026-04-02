"""
매일 지정 시각에 키워드 순위를 자동 수집하는 스케줄러
"""

import logging
import schedule
import time
from datetime import date

from config import KEYWORDS, SCHEDULE_TIME
from scraper import run_all_keywords
from database import init_db, save_results

logger = logging.getLogger(__name__)


def collect_once() -> None:
    """키워드 순위 1회 수집 및 저장."""
    logger.info("===== 순위 수집 시작 (%s) =====", date.today())
    try:
        results = run_all_keywords(KEYWORDS)
        save_results(results)
        logger.info("===== 순위 수집 완료 =====")
    except Exception as e:
        logger.exception("순위 수집 중 오류 발생: %s", e)


def run_scheduler() -> None:
    """
    스케줄러 실행.
    - 시작 즉시 1회 수집
    - 이후 매일 SCHEDULE_TIME에 자동 수집
    """
    init_db()

    # 시작 즉시 1회 실행
    collect_once()

    # 매일 예약
    schedule.every().day.at(SCHEDULE_TIME).do(collect_once)
    logger.info("스케줄러 등록: 매일 %s 자동 수집", SCHEDULE_TIME)

    while True:
        schedule.run_pending()
        time.sleep(60)
