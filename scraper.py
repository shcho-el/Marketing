"""
네이버 블로그 검색 공식 API를 사용하여 키워드 순위를 추출하는 스크레이퍼
"""

import os
import re
import time
import logging
from html import unescape

import requests
from bs4 import BeautifulSoup

from config import TARGET_BRAND, TARGET_URLS, SEARCH_DEPTH, REQUEST_DELAY, EXCLUDE_KEYWORDS

logger = logging.getLogger(__name__)

NAVER_API_URL = "https://openapi.naver.com/v1/search/blog.json"
NAVER_SEARCH_URL = "https://search.naver.com/search.naver"
API_MAX_DISPLAY = 100

_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.naver.com/",
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


_POSTVIEW_RE = re.compile(r"blogId=([^&]+)&logNo=(\d+)", re.IGNORECASE)


def _normalize_url(url: str) -> str:
    """
    URL을 https://blog.naver.com/{id}/{no} 형태로 통일.
    - m.blog.naver.com → blog.naver.com
    - PostView.naver?blogId=X&logNo=Y → blog.naver.com/X/Y
    - 쿼리스트링 제거, 후행 슬래시 제거
    """
    # PostView.naver 형식 처리
    if "PostView.naver" in url or "PostView.nhn" in url:
        m = _POSTVIEW_RE.search(url)
        if m:
            return f"https://blog.naver.com/{m.group(1)}/{m.group(2)}"
    return (
        url.replace("https://m.blog.naver.com/", "https://blog.naver.com/")
           .replace("http://m.blog.naver.com/", "https://blog.naver.com/")
           .split("?")[0]
           .rstrip("/")
    )

_TARGET_URLS_NORMALIZED = {_normalize_url(u) for u in TARGET_URLS}


def _contains_brand(result: dict) -> bool:
    """TARGET_URLS에 등록된 URL과 정확히 일치할 때만 오블리브 콘텐츠로 인식."""
    result_url = _normalize_url(result.get("url", ""))
    return result_url in _TARGET_URLS_NORMALIZED


def _is_excluded(result: dict) -> bool:
    """제목 또는 본문에 경쟁사 키워드가 포함되면 True (제외 대상)."""
    text = " ".join([
        unescape(result.get("title", "")),
        unescape(result.get("description", "")),
    ])
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def get_popular_rank(keyword: str) -> dict:
    """
    네이버 통합검색 '인기글' 구좌에서 브랜드 URL 순위를 반환.

    반환:
        {
            "popular_rank": int | None,
            "popular_ranks": list[int],
        }
    """
    params = {"query": keyword, "where": "nexearch"}
    try:
        resp = requests.get(
            NAVER_SEARCH_URL,
            headers=_SEARCH_HEADERS,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("인기글 요청 실패 (keyword=%s): %s", keyword, e)
        return {"popular_rank": None, "popular_ranks": []}

    soup = BeautifulSoup(resp.text, "html.parser")

    # 인기글 섹션 탐색: 제목에 "인기글" 텍스트를 포함하는 컨테이너 찾기
    popular_section = None
    for tag in soup.find_all(["section", "div", "li"]):
        heading = tag.find(
            lambda t: t.name in ("h2", "h3", "h4", "strong", "span")
            and t.get_text(strip=True) == "인기글",
            recursive=False,
        )
        if heading:
            popular_section = tag
            break

    # 폴백: 전체에서 "인기글" 헤딩 탐색 후 부모 사용
    if not popular_section:
        heading_tag = soup.find(
            lambda t: t.name in ("h2", "h3", "h4", "strong", "span")
            and t.get_text(strip=True) == "인기글"
        )
        if heading_tag:
            popular_section = heading_tag.find_parent(["section", "div", "li"])

    if not popular_section:
        logger.debug("인기글 구좌 없음 (keyword=%s)", keyword)
        return {"popular_rank": None, "popular_ranks": []}

    matched_ranks = []
    rank = 0
    seen_urls: set[str] = set()
    for a in popular_section.find_all("a", href=True):
        href = a["href"]
        if "blog.naver.com" not in href:
            continue
        normalized = _normalize_url(href)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        rank += 1
        if normalized in _TARGET_URLS_NORMALIZED:
            # 링크 주변 텍스트에서 경쟁사 키워드 확인
            card_text = a.get_text(" ", strip=True)
            if not any(kw in card_text for kw in EXCLUDE_KEYWORDS):
                matched_ranks.append(rank)

    return {
        "popular_rank": matched_ranks[0] if matched_ranks else None,
        "popular_ranks": matched_ranks,
    }


def get_brand_rank(keyword: str, brand: str = TARGET_BRAND, depth: int = SEARCH_DEPTH) -> dict:
    """
    네이버 블로그 검색에서 브랜드가 포함된 모든 순위를 반환.

    반환:
        {
            "keyword": str,
            "brand": str,
            "rank": int | None,         # 블로그 구좌 최상위 순위
            "ranks": list[int],          # 블로그 구좌 전체 순위
            "popular_rank": int | None,  # 인기글 구좌 최상위 순위
            "popular_ranks": list[int],  # 인기글 구좌 전체 순위
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
            if _contains_brand(item) and not _is_excluded(item):
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
        "popular_rank": None,
        "popular_ranks": [],
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
