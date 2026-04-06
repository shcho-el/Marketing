"""
키워드별 상위 결과 전체 출력 (디버깅용)
실제 브라우저 기준 (Selenium 렌더링)

사용법:
  python test_rank.py 송도내성발톱 20
  python test_rank.py 인천내성발톱 30
"""

import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scraper import _scrape_blog_page, _browser, _TARGET_URLS_NORMALIZED, RESULTS_PER_PAGE
from config import EXCLUDE_KEYWORDS, REQUEST_DELAY


def test_keyword(keyword: str, depth: int = 20):
    print(f"\n{'='*70}")
    print(f"  키워드: [{keyword}]  상위 {depth}위  (네이버 블로그 탭 관련도순 · Selenium)")
    print(f"{'='*70}")
    print(f"{'순위':>4}  {'구분':^6}  {'제목':<35}  URL")
    print(f"{'-'*110}")

    with _browser() as driver:
        global_rank = 0
        page_start = 1
        seen_urls: set = set()

        while global_rank < depth:
            items = _scrape_blog_page(driver, keyword, start=page_start)
            if not items:
                print("  (결과 없음 또는 스크래핑 실패)")
                break

            new_items = [it for it in items if it["url"] not in seen_urls]
            if not new_items:
                print(f"  (더 이상 새 결과 없음, 총 {global_rank}개)")
                break

            for item in new_items:
                if global_rank >= depth:
                    break
                seen_urls.add(item["url"])
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
            if global_rank < depth and new_items:
                time.sleep(REQUEST_DELAY)

    print(f"{'='*70}\n")


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "송도내성발톱"
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    test_keyword(keyword, depth)
