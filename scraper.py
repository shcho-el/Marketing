"""
네이버 블로그 검색 공식 API를 사용하여 키워드 순위를 추출하는 스크레이퍼

네이버 개발자센터 (https://developers.naver.com) 에서 애플리케이션 등록 후
NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수 또는 .env 파일에 설정 필요
"""

import os
import re
import time
import logging
from html import unescape

import requests

from config import TARGET_BRAND, SEARCH_DEPTH, REQUEST_DELAY

logger = logging.getLogger(__name__)

NAVER_API_URL = "https://openapi.naver.com/v1/search/blog.json"
API_MAX_DISPLAY = 100  # 네이버 API 1회 최대 조회 수


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
    """
    네이버 블로그 검색 API 호출.
    반환: [{"title": str, "url": str, "description": str, "blog_name": str}]
    """
    client_id, client_secret = _get_api_keys()
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": keyword,
        "display": display,
        "start": start,
        "sort": "sim",  # 정확도순 (관련성 높은 순)
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
        # 네이버 API는 HTML 태그와 엔티티가 섞여 있으므로 정리
        title = unescape(re.sub(r"<[^>]+>", "", item.get("title", "")))
        description = unescape(re.sub(r"<[^>]+>", "", item.get("description", "")))
        items.append({
            "title": title,
            "url": item.get("link", ""),
            "description": description,
            "blog_name": item.get("bloggername", ""),
        })
    return items


def _contains_brand(result: dict, brand: str) -> bool:
    """결과 항목이 브랜드명을 포함하는지 확인."""
    brand_lower = brand.lower()
    fields = [
        result.get("title", ""),
        result.get("description", ""),
        result.get("blog_name", ""),
        result.get("url", ""),
    ]
    return any(brand_lower in f.lower() for f in fields)


def get_brand_rank(keyword: str, brand: str = TARGET_BRAND, depth: int = SEARCH_DEPTH) -> dict:
    """
    네이버 블로그 검색에서 특정 브랜드가 포함된 결과의 순위를 반환.

    반환:
        {
            "keyword": str,
            "brand": str,
            "rank": int | None,   # 순위 (1부터 시작), 미노출이면 None
            "title": str,
            "url": str,
            "checked_count": int,
        }
    """
    rank = None
    matched_title = ""
    matched_url = ""
    global_rank = 0

    # API는 1회 최대 100건, start는 1~1000 범위
    remaining = depth
    start = 1

    while remaining > 0 and rank is None:
        display = min(remaining, API_MAX_DISPLAY)
        items = _search_blog(keyword, start=start, display=display)

        if not items:
            break

        for item in items:
            global_rank += 1
            if _contains_brand(item, brand):
                rank = global_rank
                matched_title = item["title"]
                matched_url = item["url"]
                break

        remaining -= len(items)
        start += len(items)

        if rank is None and remaining > 0:
            time.sleep(REQUEST_DELAY)

    return {
        "keyword": keyword,
        "brand": brand,
        "rank": rank,
        "title": matched_title,
        "url": matched_url,
        "checked_count": global_rank,
    }


def run_all_keywords(keywords: list[str]) -> list[dict]:
    """모든 키워드에 대해 순위를 조회하고 결과 리스트를 반환."""
    results = []
    for i, keyword in enumerate(keywords):
        logger.info("[%d/%d] 키워드 조회 중: %s", i + 1, len(keywords), keyword)
        result = get_brand_rank(keyword)
        results.append(result)
        logger.info(
            "  -> 순위: %s | 확인 건수: %d",
            f"{result['rank']}위" if result["rank"] else "미노출",
            result["checked_count"],
        )
        if i < len(keywords) - 1:
            time.sleep(REQUEST_DELAY)

    return results
