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


def _resolve_categories() -> list:
    """이 의원이 쓰는 카테고리 중, CMS에 실제로 있는 것만 남긴다.

    CMS 드롭다운에는 이 클리닉과 무관한 항목이 잔뜩 있습니다(보톡스,
    리쥬란, 재활의학…). 목록을 통째로 가져오면 생성기가 발톱과 상관없는
    카테고리로 글을 쓸 수 있습니다. 반대로 목록을 무시하면 CMS에 없는
    값을 골라 업로드에서 막힙니다.

    그래서 교집합을 씁니다. 고를 수 있는 범위는 이 의원의 진료 분야로
    한정하되, 표기는 CMS 실물을 따릅니다.
    """
    options = _cms_categories()
    ours = list(_SVC["categories"])
    if not options:
        return ours

    by_flat = {o.replace(" ", ""): o for o in options}
    resolved = [by_flat[c.replace(" ", "")] for c in ours if c.replace(" ", "") in by_flat]
    missing = [c for c in ours if c.replace(" ", "") not in by_flat]
    if missing:
        import logging

        logging.getLogger(__name__).warning(
            "CMS 카테고리에 없는 항목: %s — 업로드 시 선택할 수 없습니다.",
            ", ".join(missing),
        )
    return resolved or ours


# CMS '카테고리' 드롭다운과 겹치는 값만 씁니다.
CATEGORIES = _resolve_categories()

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
    """발행 후 최종 URL을 조립한다(정규 URL과 JSON-LD에 사용)."""
    return f"{clinic.BLOG_BASE}/{category_url_segment(category)}/{slug}"
