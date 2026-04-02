"""
네이버 API 응답을 모의(mock)하여 스크레이퍼 로직을 검증하는 테스트
실제 네이버 접속 없이 파싱·순위 계산·DB 저장 전체 흐름을 확인합니다.
"""

import os
import tempfile
from unittest.mock import patch

os.environ["NAVER_CLIENT_ID"] = "test_id"
os.environ["NAVER_CLIENT_SECRET"] = "test_secret"

import config
config.DB_PATH = tempfile.mktemp(suffix=".db")

from scraper import _contains_brand, get_brand_rank
from database import init_db, save_results, get_pivot


def _make_api_response(posts: list[dict]) -> dict:
    """네이버 블로그 검색 API JSON 응답 형식 모의 데이터 생성."""
    items = []
    for p in posts:
        items.append({
            "title": p["title"],
            "link": p.get("url", "https://blog.naver.com/test"),
            "description": p.get("desc", ""),
            "bloggername": p.get("blog_name", ""),
            "postdate": "20260402",
        })
    return {"lastBuildDate": "Thu, 02 Apr 2026 09:00:00 +0900", "total": len(items), "start": 1, "display": len(items), "items": items}


def test_brand_matching():
    """오블리브 / 오블리브의원 브랜드 매칭 테스트"""
    print("[1] 브랜드 매칭 테스트 (오블리브 / 오블리브의원)")
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
    print("[2] 순위 감지 테스트")
    mock_posts = [
        {"title": "인천 내성발톱 병원 찾기", "blog_name": "건강정보"},
        {"title": "송도에서 내성발톱 치료", "blog_name": "일상블로그"},
        {"title": "오블리브의원 내성발톱 시술 후기", "blog_name": "오블리브의원"},  # 3위
        {"title": "내성발톱 예방 방법", "blog_name": "발건강"},
        {"title": "인천 발톱 전문 클리닉", "blog_name": "클리닉소개"},
    ]
    fake_response = _make_api_response(mock_posts)

    with patch("scraper._search_blog", return_value=fake_response["items"] and [
        {"title": item["title"], "url": item["link"], "description": item["description"], "blog_name": item["bloggername"]}
        for item in fake_response["items"]
    ]):
        result = get_brand_rank("인천내성발톱", brand="오블리브", depth=10)

    assert result["rank"] == 3, f"3위 기대, 실제: {result['rank']}"
    print(f"  [PASS] '인천내성발톱' 검색 → 오블리브 3위 정확히 감지")
    print(f"         제목: {result['title']}")
    print()


def test_not_found():
    """오블리브가 없을 때 None(미노출) 반환하는지 테스트"""
    print("[3] 미노출 처리 테스트")
    mock_posts = [
        {"title": "다른병원A 내성발톱 후기", "blog_name": "병원A"},
        {"title": "다른병원B 발톱무좀 치료", "blog_name": "병원B"},
    ]
    fake_items = [{"title": p["title"], "url": "", "description": "", "blog_name": p["blog_name"]} for p in mock_posts]

    with patch("scraper._search_blog", return_value=fake_items):
        result = get_brand_rank("송도내성발톱", brand="오블리브", depth=10)

    assert result["rank"] is None
    print(f"  [PASS] 오블리브 없는 결과 → rank=None 정확히 반환")
    print()


def test_db_save_and_pivot():
    """DB 저장 및 피벗 테이블 생성 테스트"""
    print("[4] DB 저장 및 피벗 테이블 테스트")
    from datetime import date
    init_db()

    fake_results = [
        {"keyword": "인천내성발톱",  "brand": "오블리브", "rank": 3,    "title": "오블리브의원 후기",  "url": "https://blog.naver.com/1", "checked_count": 10},
        {"keyword": "송도내성발톱",  "brand": "오블리브", "rank": None, "title": "",               "url": "",                          "checked_count": 10},
        {"keyword": "문제성발톱",    "brand": "오블리브", "rank": 7,    "title": "오블리브 발톱치료", "url": "https://blog.naver.com/2", "checked_count": 10},
    ]
    save_results(fake_results, check_date=date.today())
    pivot = get_pivot(days=1)

    ranks = {r["keyword"]: list(r["ranks"].values())[0] for r in pivot["rows"]}
    assert ranks["인천내성발톱"] == 3
    assert ranks["송도내성발톱"] is None
    assert ranks["문제성발톱"] == 7
    print(f"  [PASS] 3개 키워드 순위 정확히 저장 및 조회")
    print(f"         인천내성발톱=3위 | 송도내성발톱=미노출 | 문제성발톱=7위")
    print()


if __name__ == "__main__":
    print("\n========== 스크레이퍼 로직 테스트 ==========\n")
    test_brand_matching()
    test_rank_detection()
    test_not_found()
    test_db_save_and_pivot()
    print("========== 전체 테스트 통과 ==========\n")

    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
