# -*- coding: utf-8 -*-
"""
제목에서 카테고리와 주키워드를 추론한다.

제목 하나만 받아 글을 만들려면 이 둘을 먼저 정해야 합니다.
순위 모니터링 중인 키워드(config.KEYWORDS)를 우선 후보로 삼습니다.
그래야 생성한 글의 성과를 기존 순위 대시보드에서 바로 추적할 수 있습니다.
"""

import re

from content import services, taxonomy

# 카테고리 판별 신호는 진료 분야 카탈로그에서 가져온다.
_CATEGORY_SIGNALS = services.current()["category_signals"]

# 어느 신호에도 걸리지 않으면 카탈로그의 마지막(포괄) 카테고리를 쓴다.
DEFAULT_CATEGORY = services.current()["categories"][-1]


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def infer_category(title: str) -> str:
    """제목에서 카테고리를 정한다."""
    flat = _squash(title)
    for category, signals in _CATEGORY_SIGNALS:
        if any(_squash(s) in flat for s in signals):
            return category
    return DEFAULT_CATEGORY


def _monitored_keywords() -> list:
    """순위 모니터링 중인 키워드 목록. config를 못 읽어도 동작해야 한다."""
    try:
        from config import KEYWORDS

        return list(KEYWORDS)
    except Exception:
        return []


def infer_keyword(title: str, category: str = "") -> str:
    """제목에서 주키워드를 정한다.

    우선순위
      1. 제목에 그대로 들어 있는 모니터링 키워드 중 가장 긴 것
         (지역명이 붙은 '송도발톱무좀' 같은 형태가 먼저 잡힌다)
      2. 제목에 들어 있는 카테고리 대표 키워드 중 가장 긴 것
      3. 제목의 지역명 + 카테고리 대표 키워드를 조합
      4. 카테고리 대표 키워드
    """
    category = category or infer_category(title)
    flat = _squash(title)

    monitored = [k for k in _monitored_keywords() if _squash(k) in flat]
    if monitored:
        return max(monitored, key=len)

    core = taxonomy.CORE_KEYWORDS.get(category, [])
    hits = [k for k in core if _squash(k) in flat]
    if hits:
        return max(hits, key=len)

    # 제목에 지역명이 있으면 대표 키워드와 붙여 지역 키워드를 만든다.
    base = core[0] if core else category
    for region in taxonomy.LOCAL_MODIFIERS:
        if region in flat:
            combined = f"{region}{base}"
            # 모니터링 목록에 있는 형태면 그걸 쓴다.
            for k in _monitored_keywords():
                if _squash(k) == _squash(combined):
                    return k
            return combined

    return base


def _clean_topic(title: str) -> str:
    """제목을 주제 문장으로 다듬는다.

    발행 제목에는 '_송도발톱무좀' 같은 키워드 꼬리표가 붙는 관행이 있어
    주제 설명에서는 떼어냅니다.
    """
    topic = re.split(r"[_|]", title)[0].strip()
    return topic or title.strip()


def parse(title: str) -> dict:
    """제목 하나로 생성에 필요한 입력을 모두 만든다."""
    title = (title or "").strip()
    if not title:
        raise ValueError("제목이 비어 있습니다.")

    category = infer_category(title)
    keyword = infer_keyword(title, category)
    topic = _clean_topic(title)

    # 지역 신호가 제목에 없으면 본문에서라도 지역을 다루도록 알려 준다.
    has_region = any(r in _squash(title) for r in taxonomy.LOCAL_MODIFIERS)

    return {
        "title": title,
        "category": category,
        "primary_keyword": keyword,
        "topic": topic,
        "has_region": has_region,
        "monitored": keyword in _monitored_keywords(),
    }


def describe(parsed: dict) -> str:
    """무엇을 어떻게 잡았는지 사람이 확인할 수 있게 한 줄로."""
    mark = "모니터링 중" if parsed["monitored"] else "모니터링 목록 밖"
    region = "지역 키워드 포함" if parsed["has_region"] else "지역 키워드 없음"
    return (
        f"카테고리 {parsed['category']} · 주키워드 {parsed['primary_keyword']} "
        f"({mark}) · {region}"
    )
