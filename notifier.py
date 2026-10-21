"""
슬랙 Incoming Webhook으로 키워드 순위 결과를 전송하는 모듈
"""

import os
import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)


def _get_webhook_url() -> str:
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        raise EnvironmentError(
            "SLACK_WEBHOOK_URL 환경변수가 설정되지 않았습니다.\n"
            ".env 파일에 SLACK_WEBHOOK_URL=https://hooks.slack.com/... 을 추가해 주세요."
        )
    return url


def _rank_emoji(rank) -> str:
    if rank is None:
        return "⬜"
    if rank == 1:
        return "🥇"
    if rank == 2:
        return "🥈"
    if rank == 3:
        return "🥉"
    if rank <= 5:
        return "🟢"
    if rank <= 10:
        return "🟡"
    return "🔴"


def _bar(count: int, depth: int = 20, width: int = 10) -> str:
    filled = round(count / depth * width) if depth > 0 else 0
    return "█" * filled + "░" * (width - filled)


def _build_message(results: list[dict], check_date: date) -> dict:
    """슬랙 Block Kit 메시지 생성."""
    rank_lines = []
    dom_lines = []

    for r in results:
        kw = r["keyword"]
        blog_ranks = r.get("ranks") or ([r["rank"]] if r.get("rank") else [])
        depth = r.get("checked_count") or 20
        count = len(blog_ranks)
        pct = round(count / depth * 100) if depth > 0 else 0

        if blog_ranks:
            emoji = _rank_emoji(blog_ranks[0])
            rank_str = ", ".join(f"{rk}위" for rk in blog_ranks)
        else:
            emoji = "⬜"
            rank_str = "미노출"

        rank_lines.append(f"{emoji}  `{kw}`  →  *{rank_str}*")
        dom_lines.append(
            f"`{kw}`\n{_bar(count, depth)}  *{count}개/{depth}위권*  ({pct}%)"
        )

    date_str = check_date.strftime("%Y년 %m월 %d일")
    total_count = sum(len(r.get("ranks") or ([r["rank"]] if r.get("rank") else [])) for r in results)
    total_depth = sum((r.get("checked_count") or 20) for r in results)
    total_pct = round(total_count / total_depth * 100) if total_depth > 0 else 0

    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 오블리브 네이버 블로그 순위 ({date_str})",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(rank_lines)},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*키워드별 20위권 장악률*  (전체 {total_count}개 · *{total_pct}%*)\n\n" + "\n\n".join(dom_lines),
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "네이버 블로그 탭 기준 상위 20위 · 오블리브",
                    }
                ],
            },
        ]
    }


def send_slack(results: list[dict], check_date: date | None = None) -> bool:
    """슬랙으로 순위 결과 전송. 성공 시 True, 실패 시 False 반환."""
    if check_date is None:
        check_date = date.today()

    try:
        webhook_url = _get_webhook_url()
    except EnvironmentError as e:
        logger.warning("슬랙 전송 건너뜀: %s", e)
        return False

    payload = _build_message(results, check_date)

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("슬랙 전송 완료")
            return True
        else:
            logger.warning("슬랙 전송 실패: %s %s", resp.status_code, resp.text)
            return False
    except requests.RequestException as e:
        logger.warning("슬랙 전송 오류: %s", e)
        return False
