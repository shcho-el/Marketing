"""
키워드별 상위 결과 전체 출력 (디버깅용)
실제 사용자 검색 화면(네이버 블로그 탭 관련도순) 기준

사용법:
  python test_rank.py 송도내성발톱 20
  python test_rank.py 인천내성발톱 30
"""

import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scraper import _scrape_blog_page, _TARGET_URLS_NORMALIZED, _normalize_url, NAVER_BLOG_SEARCH_URL, _HEADERS, _is_post_url
from config import EXCLUDE_KEYWORDS, RESULTS_PER_PAGE
from bs4 import BeautifulSoup
import requests


def test_keyword(keyword: str, depth: int = 20):
    print(f"\n{'='*70}")
    print(f"  키워드: [{keyword}]  상위 {depth}위  (네이버 블로그 탭 관련도순)")
    print(f"{'='*70}")
    print(f"{'순위':>4}  {'구분':^6}  {'제목':<35}  URL")
    print(f"{'-'*110}")

    global_rank = 0
    page_start = 1

    while global_rank < depth:
        items = _scrape_blog_page(keyword, start=page_start)
        if not items:
            print("  (결과 없음 또는 스크래핑 실패)")
            break
        for item in items:
            if global_rank >= depth:
                break
            global_rank += 1
            is_match = item["url"] in _TARGET_URLS_NORMALIZED
            excluded = any(kw in item["title"] + item["description"] for kw in EXCLUDE_KEYWORDS)

            if is_match and excluded:
                tag = "제외"
            elif is_match:
                tag = "★우리"
            else:
                tag = ""

            title = item["title"][:33] if item["title"] else "(제목없음)"
            print(f"{global_rank:>4}  {tag:^6}  {title:<35}  {item['url']}")

        page_start += RESULTS_PER_PAGE

    print(f"{'='*70}\n")


def debug_raw_urls(keyword: str):
    """특정 키워드 1페이지의 모든 blog.naver.com 링크를 raw 그대로 출력."""
    params = {
        "where": "blog",
        "query": keyword,
        "sm": "tab_jum",
        "nso": "so:r,p:all,a:all",
        "start": 1,
    }
    resp = requests.get(NAVER_BLOG_SEARCH_URL, headers=_HEADERS, params=params, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    container = soup.find(id="main_pack") or soup.find(id="ct") or soup

    print(f"\n[RAW URL 목록] 키워드: {keyword}")
    print("-" * 80)
    seen = set()
    for a in container.find_all("a", href=True):
        href = a["href"]
        if "blog.naver.com" not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        is_post = _is_post_url(href)
        normalized = _normalize_url(href)
        matched = normalized in _TARGET_URLS_NORMALIZED
        print(f"  {'[포스트]' if is_post else '[기타]  '}  {'★매칭' if matched else '      '}  {href}")
    print()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "raw":
        keyword = sys.argv[2] if len(sys.argv) > 2 else "송도내성발톱"
        debug_raw_urls(keyword)
    else:
        keyword = sys.argv[1] if len(sys.argv) > 1 else "송도내성발톱"
        depth = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        test_keyword(keyword, depth)
