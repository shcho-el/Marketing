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
    if rank <= 3:
        return "🥇" if rank == 1 else ("🥈" if rank == 2 else "🥉")
    if rank <= 5:
        return "🟢"
    if rank <= 10:
        return "🟡"
    return "🔴"


def _build_message(results: list[dict], check_date: date) -> dict:
    """슬랙 Block Kit 메시지 생성 (블로그 + 파워링크 구분)."""
    blog_lines = []
    power_lines = []

    for r in results:
        kw = r["keyword"]

        blog_rank = r.get("rank")
        blog_emoji = _rank_emoji(blog_rank)
        blog_str = f"{blog_rank}위" if blog_rank else "미노출"
        blog_lines.append(f"{blog_emoji}  `{kw}`  →  *{blog_str}*")

        pl_rank = r.get("powerlink_rank")
        pl_emoji = _rank_emoji(pl_rank)
        pl_str = f"{pl_rank}위" if pl_rank else "미노출"
        power_lines.append(f"{pl_emoji}  `{kw}`  →  *{pl_str}*")

    date_str = check_date.strftime("%Y년 %m월 %d일")

    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 오블리브 키워드 순위 ({date_str})",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*📝 네이버 블로그*"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(blog_lines)},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*⚡ 파워링크 (광고)*"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(power_lines)},
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "블로그: 상위 30위 기준 · 파워링크: 네이버 통합검색 광고 섹션 · 오블리브 / 오블리브의원",
                    }
                ],
            },
        ]
    }


def send_slack(results: list[dict], check_date: date | None = None) -> bool:
    """
    슬랙으로 순위 결과 전송.
    성공 시 True, 실패 시 False 반환.
    """
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
