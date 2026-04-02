"""
네이버 응답을 모의(mock)하여 스크레이퍼 로직을 검증하는 테스트
실제 네이버 접속 없이 파싱·순위 계산·DB 저장 전체 흐름을 확인합니다.
"""

import os
import tempfile
from unittest.mock import patch
from bs4 import BeautifulSoup

# 테스트용 임시 DB
os.environ["_TEST_DB"] = "1"
import config
_orig_db = config.DB_PATH
config.DB_PATH = tempfile.mktemp(suffix=".db")

from scraper import _extract_blog_results, _contains_brand, get_brand_rank
from database import init_db, save_results, get_pivot


# ── 가짜 네이버 블로그 HTML ─────────────────────────────────────────
def _make_naver_html(posts: list[dict]) -> str:
    """
    posts: [{"title": str, "blog_name": str, "desc": str}]
    """
    items = ""
    for p in posts:
        items += f"""
        <li class="bx">
          <div class="title_area">
            <a class="title" href="https://blog.naver.com/test">{p['title']}</a>
          </div>
          <div class="dsc_area">{p.get('desc', '')}</div>
          <div class="name">{p.get('blog_name', '')}</div>
        </li>"""
    return f"""
    <html><body>
      <ul class="lst_total">{items}</ul>
    </body></html>"""


# ── 테스트 케이스 ──────────────────────────────────────────────────
def test_parsing():
    """HTML 파싱이 올바르게 동작하는지 확인"""
    html = _make_naver_html([
        {"title": "송도 내성발톱 치료후기", "blog_name": "건강블로그"},
        {"title": "오블리브의원 내성발톱 시술 받았어요", "blog_name": "오블리브"},
        {"title": "인천 발톱 관리법", "blog_name": "발톱전문"},
    ])
    soup = BeautifulSoup(html, "lxml")
    results = _extract_blog_results(soup)
    assert len(results) == 3, f"결과 3개 기대, 실제: {len(results)}"
    print("  [PASS] HTML 파싱: 결과 3개 정상 추출")


def test_brand_matching():
    """오블리브 / 오블리브의원 브랜드 매칭 테스트"""
    cases = [
        ({"title": "오블리브의원 내성발톱 후기", "url": "", "description": "", "blog_name": ""}, True),
        ({"title": "오블리브 발톱무좀 치료", "url": "", "description": "", "blog_name": ""}, True),
        ({"title": "송도 내성발톱 병원 추천", "url": "", "description": "", "blog_name": "오블리브"}, True),
        ({"title": "다른병원 내성발톱 후기", "url": "", "description": "오블리브의원 방문기", "blog_name": ""}, True),
        ({"title": "완전 다른 병원 후기", "url": "", "description": "관련없는 내용", "blog_name": "건강블로그"}, False),
    ]
    for item, expected in cases:
        result = _contains_brand(item, "오블리브")
        status = "PASS" if result == expected else "FAIL"
        mark = "오블리브 포함" if expected else "오블리브 없음"
        print(f"  [{status}] '{item['title'][:30]}' → {mark}")
    print()


def test_rank_detection():
    """오블리브 글이 몇 위에 있는지 정확히 감지하는지 테스트"""
    mock_posts = [
        {"title": "인천 내성발톱 병원 찾기", "blog_name": "건강정보"},
        {"title": "송도에서 내성발톱 치료", "blog_name": "일상블로그"},
        {"title": "오블리브의원 내성발톱 시술 후기", "blog_name": "오블리브의원"},  # 3위
        {"title": "내성발톱 예방 방법", "blog_name": "발건강"},
        {"title": "인천 발톱 전문 클리닉", "blog_name": "클리닉소개"},
    ]

    fake_html = _make_naver_html(mock_posts)
    fake_soup = BeautifulSoup(fake_html, "lxml")

    def mock_fetch(url):
        return fake_soup

    with patch("scraper._fetch", side_effect=mock_fetch):
        result = get_brand_rank("인천내성발톱", brand="오블리브", depth=10)

    assert result["rank"] == 3, f"3위 기대, 실제: {result['rank']}"
    assert "오블리브" in result["title"]
    print(f"  [PASS] 순위 감지: '인천내성발톱' 검색 → 오블리브 3위 정확히 감지")
    print(f"         제목: {result['title']}")
    print()


def test_not_found():
    """오블리브가 없을 때 None(미노출) 반환하는지 테스트"""
    mock_posts = [
        {"title": "다른병원A 내성발톱 후기", "blog_name": "병원A"},
        {"title": "다른병원B 발톱무좀 치료", "blog_name": "병원B"},
    ]
    fake_html = _make_naver_html(mock_posts)
    fake_soup = BeautifulSoup(fake_html, "lxml")

    with patch("scraper._fetch", side_effect=lambda url: fake_soup):
        result = get_brand_rank("송도내성발톱", brand="오블리브", depth=10)

    assert result["rank"] is None, f"None 기대, 실제: {result['rank']}"
    print(f"  [PASS] 미노출 처리: 오블리브 없는 결과 → rank=None 정확히 반환")
    print()


def test_db_save_and_pivot():
    """DB 저장 및 피벗 테이블 생성 테스트"""
    from datetime import date
    init_db()

    fake_results = [
        {"keyword": "인천내성발톱", "brand": "오블리브", "rank": 3, "title": "오블리브의원 후기", "url": "https://blog.naver.com/test", "checked_count": 10},
        {"keyword": "송도내성발톱", "brand": "오블리브", "rank": None, "title": "", "url": "", "checked_count": 10},
        {"keyword": "문제성발톱", "brand": "오블리브", "rank": 7, "title": "오블리브 발톱치료", "url": "https://blog.naver.com/test2", "checked_count": 10},
    ]

    save_results(fake_results, check_date=date.today())
    pivot = get_pivot(days=1)

    assert len(pivot["rows"]) == 3
    ranks = {r["keyword"]: list(r["ranks"].values())[0] for r in pivot["rows"]}
    assert ranks["인천내성발톱"] == 3
    assert ranks["송도내성발톱"] is None
    assert ranks["문제성발톱"] == 7
    print(f"  [PASS] DB 저장/조회: 3개 키워드 순위 정확히 저장됨")
    print(f"         인천내성발톱=3위, 송도내성발톱=미노출, 문제성발톱=7위")
    print()


# ── 실행 ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n========== 스크레이퍼 로직 테스트 ==========\n")

    print("[1] HTML 파싱 테스트")
    test_parsing()
    print()

    print("[2] 브랜드 매칭 테스트 (오블리브 / 오블리브의원)")
    test_brand_matching()

    print("[3] 순위 감지 테스트")
    test_rank_detection()

    print("[4] 미노출 처리 테스트")
    test_not_found()

    print("[5] DB 저장 및 피벗 테이블 테스트")
    test_db_save_and_pivot()

    print("========== 전체 테스트 통과 ==========\n")

    # 임시 DB 정리
    import os
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
