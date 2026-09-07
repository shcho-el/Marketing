"""
카테고리 / 키워드 세트 / 해시태그 풀.

키워드 세트는 순위 모니터링(config.KEYWORDS)과 짝을 이룹니다.
모니터링 중인 키워드로 글을 만들면 순위 대시보드에서 바로 성과를 추적할 수 있습니다.
"""

from content import clinic

# CMS '카테고리' 드롭다운과 동일한 값이어야 합니다.
CATEGORIES = [
    "발톱무좀치료",
    "내성발톱치료",
    "문제성발톱",
    "발톱관리",
]

# 카테고리별 대표 키워드(주키워드 후보). 지역명 조합은 build_keyword_set()이 만듭니다.
CORE_KEYWORDS = {
    "발톱무좀치료": [
        "발톱무좀",
        "발톱무좀치료",
        "발톱무좀병원",
        "발톱무좀레이저",
        "조갑진균증",
        "두꺼워진발톱",
    ],
    "내성발톱치료": [
        "내성발톱",
        "내성발톱치료",
        "내성발톱병원",
        "발톱이살을파고들때",
        "함입조갑",
    ],
    "문제성발톱": [
        "문제성발톱",
        "문제성발톱병원",
        "발톱변형",
        "발톱변색",
    ],
    "발톱관리": [
        "발톱관리",
        "발톱깎는법",
        "무좀재발방지",
    ],
}

# 지역 수식어 - 로컬 SEO 조합용
LOCAL_MODIFIERS = ["송도", "인천", "연수구", "인천송도"]

# 해시태그 고정 풀. 생성기가 여기서 고르고, 본문 주제어 몇 개를 더합니다.
HASHTAG_POOL = [
    "#송도발톱무좀",
    "#인천발톱무좀",
    "#연수구발톱무좀",
    "#송도동무좀치료",
    "#인천논현동발톱무좀",
    "#배곧발톱무좀",
    "#송도내성발톱",
    "#인천내성발톱",
    "#문제성발톱",
    "#문제성발톱병원",
    "#인천문제성발톱",
    "#송도문제성발톱",
    "#발톱무좀레이저",
    "#두꺼워진발톱",
    "#조갑진균증",
    "#발톱무좀병원",
]


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
