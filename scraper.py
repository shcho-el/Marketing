"""
네이버 블로그 검색 결과에서 특정 키워드의 순위를 추출하는 스크레이퍼
"""

import time
import logging
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from config import TARGET_BRAND, SEARCH_DEPTH, REQUEST_DELAY

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://search.naver.com/",
}

NAVER_BLOG_URL = "https://search.naver.com/search.naver?where=blog&query={query}&start={start}"


def _fetch(url: str) -> BeautifulSoup | None:
    """URL을 가져와 BeautifulSoup 객체 반환. 실패 시 None 반환."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return BeautifulSoup(resp.text, "lxml")
    except requests.RequestException as e:
        logger.warning("요청 실패 (%s): %s", url, e)
        return None


def _extract_blog_results(soup: BeautifulSoup) -> list[dict]:
    """
    BeautifulSoup 파싱 결과에서 블로그 결과 목록을 추출.
    반환: [{"title": str, "url": str, "description": str, "blog_name": str}]
    """
    results = []

    # 네이버 블로그 결과 컨테이너 후보 셀렉터 (구조 변경 대응)
    list_items = (
        soup.select("ul.lst_total > li")
        or soup.select("div.total_wrap ul > li")
        or soup.select(".api_subject_bx li")
        or soup.select("li.bx")
    )

    for item in list_items:
        # 제목 추출
        title_tag = (
            item.select_one(".api_txt_lines.total_tit a")
            or item.select_one(".total_tit a")
            or item.select_one(".title_area a")
            or item.select_one("a.title")
            or item.select_one("a[class*='title']")
        )

        # 설명 추출
        desc_tag = (
            item.select_one(".api_txt_lines:not(.total_tit)")
            or item.select_one(".dsc_area")
            or item.select_one(".desc")
        )

        # 블로그명 추출
        blog_name_tag = (
            item.select_one(".sub_txt.sub_name")
            or item.select_one(".name")
            or item.select_one(".blog_name")
            or item.select_one(".user_info a")
        )

        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        url = title_tag.get("href", "")
        description = desc_tag.get_text(strip=True) if desc_tag else ""
        blog_name = blog_name_tag.get_text(strip=True) if blog_name_tag else ""

        results.append({
            "title": title,
            "url": url,
            "description": description,
            "blog_name": blog_name,
        })

    return results


def _contains_brand(result: dict, brand: str) -> bool:
    """결과 항목이 브랜드명을 포함하는지 확인 (대소문자 무시)."""
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
            "title": str,         # 해당 결과 제목 (없으면 "")
            "url": str,           # 해당 결과 URL (없으면 "")
            "checked_count": int, # 확인한 총 결과 수
        }
    """
    rank = None
    matched_title = ""
    matched_url = ""
    global_rank = 0

    pages_per_check = 10  # 네이버 블로그는 한 페이지 10건
    start_values = list(range(1, depth + 1, pages_per_check))

    for start in start_values:
        url = NAVER_BLOG_URL.format(query=quote(keyword), start=start)
        soup = _fetch(url)

        if soup is None:
            logger.error("키워드 '%s' start=%d 페이지 로드 실패", keyword, start)
            break

        items = _extract_blog_results(soup)

        if not items:
            logger.debug("키워드 '%s' start=%d 결과 없음 또는 파싱 실패", keyword, start)
            # 결과가 없으면 더 이상 페이지가 없는 것
            break

        for item in items:
            global_rank += 1
            if _contains_brand(item, brand):
                rank = global_rank
                matched_title = item["title"]
                matched_url = item["url"]
                break

        if rank is not None:
            break

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
    """
    모든 키워드에 대해 순위를 조회하고 결과 리스트를 반환.
    """
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
