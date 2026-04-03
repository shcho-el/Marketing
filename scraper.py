"""
네이버 블로그 탭 HTML 직접 스크래핑으로 키워드 순위를 추출하는 스크레이퍼
(실제 사용자가 검색해서 보는 화면 기준)
"""

import re
import time
import logging

import requests
from bs4 import BeautifulSoup

from config import TARGET_BRAND, TARGET_URLS, SEARCH_DEPTH, REQUEST_DELAY, EXCLUDE_KEYWORDS

logger = logging.getLogger(__name__)

NAVER_BLOG_SEARCH_URL = "https://search.naver.com/search.naver"
RESULTS_PER_PAGE = 10  # 네이버 블로그 탭 한 페이지 결과 수

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.naver.com/",
}

_POSTVIEW_RE = re.compile(r"blogId=([^&]+)&logNo=(\d+)", re.IGNORECASE)
_POST_URL_RE = re.compile(r"https://blog\.naver\.com/[^/]+/\d+")


def _normalize_url(url: str) -> str:
    """
    URL을 https://blog.naver.com/{id}/{no} 형태로 통일.
    - m.blog.naver.com → blog.naver.com
    - PostView.naver?blogId=X&logNo=Y → blog.naver.com/X/Y
    - 쿼리스트링 제거, 후행 슬래시 제거
    """
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


def _is_post_url(url: str) -> bool:
    """블로그 포스트 URL 여부 확인 (blog.naver.com/{id}/{숫자} 형식)."""
    normalized = _normalize_url(url)
    parts = normalized.replace("https://blog.naver.com/", "").split("/")
    return len(parts) == 2 and parts[1].isdigit() and len(parts[1]) > 6


def _scrape_blog_page(keyword: str, start: int = 1) -> list[dict]:
    """
    네이버 블로그 탭 한 페이지를 스크래핑하여 결과 목록 반환.
    start=1 → 1~10위, start=11 → 11~20위, start=21 → 21~30위
    """
    params = {
        "where": "blog",
        "query": keyword,
        "sm": "tab_jum",          # 관련도순
        "nso": "so:r,p:all,a:all",  # 전체 기간
        "start": start,
    }
    try:
        resp = requests.get(
            NAVER_BLOG_SEARCH_URL,
            headers=_HEADERS,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("블로그 탭 요청 실패 (keyword=%s, start=%d): %s", keyword, start, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # 메인 결과 영역 한정 (사이드바/헤더 링크 제외)
    container = (
        soup.find(id="main_pack")
        or soup.find(id="ct")
        or soup.find(class_="lst_total")
        or soup
    )

    items = []
    seen: set[str] = set()

    for a in container.find_all("a", href=True):
        href = a["href"]
        if "blog.naver.com" not in href:
            continue
        if not _is_post_url(href):
            continue
        normalized = _normalize_url(href)
        if normalized in seen:
            continue
        seen.add(normalized)

        # 제목: 링크 텍스트 또는 가장 가까운 제목 요소
        title = a.get_text(" ", strip=True)
        if not title:
            parent = a.find_parent(["li", "div", "article"])
            if parent:
                h = parent.find(["strong", "span", "em", "b"])
                title = h.get_text(" ", strip=True) if h else ""

        # 설명: 주변 텍스트 블록
        description = ""
        parent = a.find_parent(["li", "div", "article"])
        if parent:
            dsc = parent.find(
                class_=lambda c: c and any(x in c for x in ("dsc", "desc", "text", "summary"))
            )
            if dsc:
                description = dsc.get_text(" ", strip=True)

        items.append({
            "title": title,
            "url": normalized,
            "description": description,
        })

    return items


def _contains_brand(result: dict) -> bool:
    """TARGET_URLS에 등록된 URL과 정확히 일치할 때만 오블리브 콘텐츠로 인식."""
    return result.get("url", "") in _TARGET_URLS_NORMALIZED


def _is_excluded(result: dict) -> bool:
    """제목 또는 본문에 경쟁사 키워드가 포함되면 True (제외 대상)."""
    text = result.get("title", "") + " " + result.get("description", "")
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def get_brand_rank(keyword: str, brand: str = TARGET_BRAND, depth: int = SEARCH_DEPTH) -> dict:
    """
    네이버 블로그 탭(관련도순) 기준 순위 반환.
    실제 사용자가 검색해서 보는 화면과 동일한 기준.

    반환:
        {
            "keyword": str,
            "brand": str,
            "rank": int | None,   # 최상위 순위
            "ranks": list[int],   # 전체 매칭 순위 목록
            "popular_rank": None,
            "popular_ranks": [],
            "title": str,
            "url": str,
            "checked_count": int,
        }
    """
    matched_ranks = []
    matched_title = ""
    matched_url = ""
    global_rank = 0
    page_start = 1

    while global_rank < depth:
        items = _scrape_blog_page(keyword, start=page_start)
        if not items:
            break
        for item in items:
            if global_rank >= depth:
                break
            global_rank += 1
            if _contains_brand(item) and not _is_excluded(item):
                if not matched_ranks:
                    matched_title = item["title"]
                    matched_url = item["url"]
                matched_ranks.append(global_rank)
        page_start += RESULTS_PER_PAGE
        if global_rank < depth and items:
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
