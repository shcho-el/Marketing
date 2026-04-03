"""
키워드별 상위 결과 전체 출력 (디버깅용)

사용법:
  python test_rank.py 송도내성발톱 20
  python test_rank.py 인천내성발톱 30
"""

import sys
import re
from html import unescape

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scraper import _search_blog, _normalize_url, _TARGET_URLS_NORMALIZED
from config import EXCLUDE_KEYWORDS


def test_keyword(keyword: str, depth: int = 20):
    print(f"\n{'='*60}")
    print(f"  키워드: {keyword}  (상위 {depth}위 조회)")
    print(f"{'='*60}")
    print(f"{'순위':>4}  {'매칭':^4}  {'제목':<35}  URL")
    print(f"{'-'*100}")

    fetched = 0
    start = 1
    rank = 0

    while fetched < depth:
        display = min(depth - fetched, 100)
        items = _search_blog(keyword, start=start, display=display)
        if not items:
            break
        for item in items:
            rank += 1
            normalized = _normalize_url(item["url"])
            is_match = normalized in _TARGET_URLS_NORMALIZED
            excluded = any(kw in item["title"] + item["description"] for kw in EXCLUDE_KEYWORDS)

            if is_match and excluded:
                tag = "제외"
            elif is_match:
                tag = "★우리"
            else:
                tag = ""

            title = item["title"][:33]
            print(f"{rank:>4}  {tag:^6}  {title:<35}  {item['url']}")

        fetched += len(items)
        start += len(items)

    print(f"{'='*60}\n")


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "송도내성발톱"
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    test_keyword(keyword, depth)
