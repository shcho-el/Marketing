"""
네이버 블로그 검색 공식 API + 파워링크 스크래핑으로 키워드 순위를 추출하는 스크레이퍼

네이버 개발자센터 (https://developers.naver.com) 에서 애플리케이션 등록 후
NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수 또는 .env 파일에 설정 필요
"""

import os
import re
import time
import logging
from html import unescape
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from config import TARGET_BRAND, BRAND_ALIASES, SEARCH_DEPTH, REQUEST_DELAY

logger = logging.getLogger(__name__)

NAVER_API_URL = "https://openapi.naver.com/v1/search/blog.json"
NAVER_SEARCH_URL = "https://search.naver.com/search.naver?query={query}"
API_MAX_DISPLAY = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _get_api_keys() -> tuple[str, str]:
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise EnvironmentError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 설정되지 않았습니다.\n"
            ".env 파일을 만들어 값을 입력하거나 환경변수를 직접 설정해 주세요."
        )
    return client_id, client_secret


def _search_blog(keyword: str, start: int, display: int) -> list[dict]:
    """네이버 블로그 검색 API 호출."""
    client_id, client_secret = _get_api_keys()
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": keyword,
        "display": display,
        "start": start,
        "sort": "sim",
    }
    try:
        resp = requests.get(NAVER_API_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning("API 요청 실패 (keyword=%s, start=%d): %s", keyword, start, e)
        return []

    items = []
    for item in data.get("items", []):
        title = unescape(re.sub(r"<[^>]+>", "", item.get("title", "")))
        description = unescape(re.sub(r"<[^>]+>", "", item.get("description", "")))
        items.append({
            "title": title,
            "url": item.get("link", ""),
            "description": description,
            "blog_name": item.get("bloggername", ""),
        })
    return items


def _contains_brand(result: dict, brand: str = None) -> bool:
    """BRAND_ALIASES 중 하나라도 포함되면 오블리브 콘텐츠로 인식."""
    fields = " ".join([
        result.get("title", ""),
        result.get("description", ""),
        result.get("blog_name", ""),
        result.get("url", ""),
    ]).lower()
    return any(alias.lower() in fields for alias in BRAND_ALIASES)


def get_powerlink_rank(keyword: str, brand: str = TARGET_BRAND) -> dict:
    """
    Playwright로 네이버 통합검색을 실제 브라우저에서 열어
    파워링크(광고) 섹션의 브랜드 순위를 반환.
    반환: {"powerlink_rank": int | None, "powerlink_title": str}
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright 미설치 - 파워링크 건너뜀")
        return {"powerlink_rank": None, "powerlink_title": ""}

    url = NAVER_SEARCH_URL.format(query=quote(keyword))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)  # 광고 섹션 로딩 대기

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        # 파워링크 컨테이너 탐색
        pl_container = soup.find(
            class_=lambda c: c and any("pcPowerLink" in cls for cls in c)
        )
        if not pl_container:
            # 광고 섹션 텍스트로 폴백 탐색
            pl_container = soup.find(
                lambda tag: tag.name in ["div", "section", "ul"]
                and "관련 광고" in tag.get_text()
            )

        if not pl_container:
            return {"powerlink_rank": None, "powerlink_title": ""}

        # 개별 광고 항목 추출
        ad_items = (
            pl_container.select("li")
            or pl_container.select("[class*='item']")
            or pl_container.find_all("div", recursive=False)
        )

        for i, item in enumerate(ad_items, 1):
            text = item.get_text().lower()
            if any(alias.lower() in text for alias in BRAND_ALIASES):
                title_tag = item.select_one("a")
                title = title_tag.get_text(strip=True) if title_tag else text[:50]
                return {"powerlink_rank": i, "powerlink_title": title}

        return {"powerlink_rank": None, "powerlink_title": ""}

    except Exception as e:
        logger.warning("파워링크 조회 실패 (keyword=%s): %s", keyword, e)
        return {"powerlink_rank": None, "powerlink_title": ""}


def get_brand_rank(keyword: str, brand: str = TARGET_BRAND, depth: int = SEARCH_DEPTH) -> dict:
    """
    네이버 블로그 + 파워링크 순위를 모두 반환.

    반환:
        {
            "keyword": str,
            "brand": str,
            "rank": int | None,              # 블로그 순위
            "title": str,
            "url": str,
            "checked_count": int,
            "powerlink_rank": int | None,    # 파워링크 순위
            "powerlink_title": str,
        }
    """
    # 블로그 순위 (모든 매칭 위치 수집)
    matched_ranks = []
    matched_title = ""
    matched_url = ""
    global_rank = 0
    remaining = depth
    start = 1

    while remaining > 0:
        display = min(remaining, API_MAX_DISPLAY)
        items = _search_blog(keyword, start=start, display=display)
        if not items:
            break
        for item in items:
            global_rank += 1
            if _contains_brand(item):
                if not matched_ranks:
                    matched_title = item["title"]
                    matched_url = item["url"]
                matched_ranks.append(global_rank)
        remaining -= len(items)
        start += len(items)
        if remaining > 0:
            time.sleep(REQUEST_DELAY)

    # 파워링크 순위
    time.sleep(REQUEST_DELAY)
    powerlink = get_powerlink_rank(keyword, brand)

    return {
        "keyword": keyword,
        "brand": brand,
        "rank": matched_ranks[0] if matched_ranks else None,   # 최상위 순위
        "ranks": matched_ranks,                                 # 전체 순위 목록
        "title": matched_title,
        "url": matched_url,
        "checked_count": global_rank,
        "powerlink_rank": powerlink["powerlink_rank"],
        "powerlink_title": powerlink["powerlink_title"],
    }


def run_all_keywords(keywords: list[str]) -> list[dict]:
    """모든 키워드에 대해 블로그 + 파워링크 순위를 조회하고 결과 리스트를 반환."""
    results = []
    for i, keyword in enumerate(keywords):
        logger.info("[%d/%d] 키워드 조회 중: %s", i + 1, len(keywords), keyword)
        result = get_brand_rank(keyword)
        results.append(result)
        ranks = result.get("ranks", [])
        ranks_str = ", ".join(f"{r}위" for r in ranks) if ranks else "미노출"
        logger.info(
            "  -> 블로그: %s | 파워링크: %s",
            ranks_str,
            f"{result['powerlink_rank']}위" if result["powerlink_rank"] else "미노출",
        )
        if i < len(keywords) - 1:
            time.sleep(REQUEST_DELAY)

    return results
