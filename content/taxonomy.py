"""
카테고리 / 키워드 세트 / 해시태그 풀.

키워드 세트는 순위 모니터링(config.KEYWORDS)과 짝을 이룹니다.
모니터링 중인 키워드로 글을 만들면 순위 대시보드에서 바로 성과를 추적할 수 있습니다.
"""

from content import clinic, services

_SVC = services.current()


def _cms_categories() -> list:
    """CMS에서 읽어 온 실제 카테고리 목록이 있으면 그것을 쓴다.

    inspect-cms가 만든 매핑에 카테고리 드롭다운 값이 담겨 있습니다.
    실물과 어긋난 카테고리로 생성하면 업로드 단계에서 실패하므로
    있으면 실물을 우선합니다.
    """
    try:
        import json
        import os

        path = os.getenv("CMS_MAPPING_PATH", "cms_mapping.json")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fp:
            mapping = json.load(fp)
        options = (mapping.get("_notes", {}).get("category", {}) or {}).get("options", [])
        return [o for o in options if o and o.strip()]
    except Exception:
        return []


# CMS '카테고리' 드롭다운과 동일한 값이어야 합니다.
# inspect-cms를 돌렸다면 실제 CMS 목록으로 자동 대체됩니다.
CATEGORIES = _cms_categories() or list(_SVC["categories"])

# 카테고리별 대표 키워드(주키워드 후보). 지역명 조합은 build_keyword_set()이 만듭니다.
CORE_KEYWORDS = _SVC["core_keywords"]

# 지역 수식어 - 로컬 SEO 조합용
LOCAL_MODIFIERS = ["송도", "인천", "연수구", "인천송도"]

# 해시태그 고정 풀. 생성기가 여기서 고르고, 본문 주제어 몇 개를 더합니다.
HASHTAG_POOL = _SVC["hashtags"]


def build_keyword_set(category: str, primary: str) -> dict:
    """주키워드를 중심으로 보조·롱테일 키워드 묶음을 만든다.

    primary  : 본문 H1/MetaTitle에 반드시 들어갈 주키워드
    secondary: 본문 H2·소제목에 자연스럽게 분산할 보조 키워드
    longtail : FAQ·본문 문장에 녹일 질의형 롱테일
    """
    core = CORE_KEYWORDS.get(category, [])
    secondary = [k for k in core if k != primary][:5]

    # 지역 조합 롱테일 - 주키워드에 지역명이 없을 때만 붙인다.
    local = []
    if not any(m in primary for m in LOCAL_MODIFIERS):
        base = core[0] if core else primary
        local = [f"{m}{base}" for m in LOCAL_MODIFIERS[:2]]

    longtail = [
        f"{primary} 비용",
        f"{primary} 기간",
        f"{primary} 후 관리",
        f"{primary} 어느 병원",
    ]
    return {
        "primary": primary,
        "secondary": secondary,
        "local": local,
        "longtail": longtail,
    }


def suggest_hashtags(category: str, primary: str, limit: int = 12) -> list:
    """카테고리·주키워드와 관련도가 높은 해시태그를 우선 정렬해 반환한다."""
    def score(tag: str) -> int:
        body = tag.lstrip("#")
        s = 0
        if primary and primary in body:
            s += 3
        for k in CORE_KEYWORDS.get(category, []):
            if k in body:
                s += 2
                break
        for m in LOCAL_MODIFIERS:
            if m in body:
                s += 1
                break
        return s

    ranked = sorted(HASHTAG_POOL, key=score, reverse=True)
    return ranked[:limit]


def category_url_segment(category: str) -> str:
    """블로그 URL의 카테고리 세그먼트. CMS가 한글 카테고리를 그대로 사용한다."""
    return category


def post_url(category: str, slug: str) -> str:
    """발행 후 최종 URL을 조립한다(정규 URL/JSON-LD·목차 앵커에 사용)."""
    return f"{clinic.BLOG_BASE}/{category_url_segment(category)}/{slug}"
