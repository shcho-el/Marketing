"""
네이버 블로그 검색 공식 API를 사용하여 키워드 순위를 추출하는 스크레이퍼
"""

import os
import re
import time
import logging
from html import unescape

import requests

from config import TARGET_BRAND, BRAND_ALIASES, TARGET_URLS, SEARCH_DEPTH, REQUEST_DELAY

logger = logging.getLogger(__name__)

NAVER_API_URL = "https://openapi.naver.com/v1/search/blog.json"
API_MAX_DISPLAY = 100


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


def _normalize_url(url: str) -> str:
    """m.blog.naver.com → blog.naver.com 통일, 쿼리스트링 제거."""
    return url.replace("https://m.blog.naver.com/", "https://blog.naver.com/") \
              .replace("http://m.blog.naver.com/", "https://blog.naver.com/") \
              .split("?")[0].rstrip("/")

_TARGET_URLS_NORMALIZED = {_normalize_url(u) for u in TARGET_URLS}


def _contains_brand(result: dict) -> bool:
    """
    1순위: TARGET_URLS에 등록된 URL과 일치하면 오블리브 콘텐츠
    2순위: BRAND_ALIASES 포함 여부 (폴백)
    """
    result_url = _normalize_url(result.get("url", ""))
    if result_url in _TARGET_URLS_NORMALIZED:
        return True

    fields = " ".join([
        result.get("title", ""),
        result.get("description", ""),
        result.get("blog_name", ""),
    ]).lower()
    return any(alias.lower() in fields for alias in BRAND_ALIASES)


def get_brand_rank(keyword: str, brand: str = TARGET_BRAND, depth: int = SEARCH_DEPTH) -> dict:
    """
    네이버 블로그 검색에서 브랜드가 포함된 모든 순위를 반환.

    반환:
        {
            "keyword": str,
            "brand": str,
            "rank": int | None,    # 최상위 순위
            "ranks": list[int],    # 전체 매칭 순위 목록
            "title": str,
            "url": str,
            "checked_count": int,
        }
    """
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

    return {
        "keyword": keyword,
        "brand": brand,
        "rank": matched_ranks[0] if matched_ranks else None,
        "ranks": matched_ranks,
        "title": matched_title,
        "url": matched_url,
        "checked_count": global_rank,
    }


def run_all_keywords(keywords: list[str]) -> list[dict]:
    """모든 키워드에 대해 블로그 순위를 조회하고 결과 리스트를 반환."""
    results = []
    for i, keyword in enumerate(keywords):
        logger.info("[%d/%d] 키워드 조회 중: %s", i + 1, len(keywords), keyword)
        result = get_brand_rank(keyword)
        results.append(result)
        ranks = result.get("ranks", [])
        ranks_str = ", ".join(f"{r}위" for r in ranks) if ranks else "미노출"
        logger.info("  -> 블로그: %s", ranks_str)
        if i < len(keywords) - 1:
            time.sleep(REQUEST_DELAY)

    return results
