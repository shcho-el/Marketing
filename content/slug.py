"""
포스트 URL 슬러그 생성.

CMS 규칙(화면 안내문):
  - 키워드 위주로 작성
  - 단어 단위로 '-' 연결
  - 한 번 정한 URL은 수정 금지

실제 발행 사례:
  제목 "두꺼워진 발톱, 겉에만 '약' 바르는 건 '밑 빠진 독에 물 붓기'인 이유_인천발톱무좀"
  → "두꺼워진-발톱-겉에만-약-바르는-건-밑-빠진-독에-물-붓기인-이유인천발톱무좀"
즉 구두점은 제거하고 공백만 '-'로 바꿉니다.
"""

import re

# 한글(음절·자모), 영문, 숫자, 공백만 남긴다.
_KEEP = re.compile(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ\s]")
_SPACES = re.compile(r"\s+")
_DASHES = re.compile(r"-{2,}")

# URL 길이 상한. 너무 길면 검색결과에서 잘리고 공유 시 가독성이 떨어진다.
MAX_SLUG_CHARS = 80


def slugify(title: str, max_chars: int = MAX_SLUG_CHARS) -> str:
    """제목(H1)에서 발행용 슬러그를 만든다."""
    s = _KEEP.sub("", title or "")
    s = _SPACES.sub(" ", s).strip()
    s = s.replace(" ", "-")
    s = _DASHES.sub("-", s).strip("-")

    if len(s) <= max_chars:
        return s

    # 단어(하이픈) 경계에서 자른다.
    cut = s[:max_chars]
    if "-" in cut:
        cut = cut.rsplit("-", 1)[0]
    return cut.strip("-")


def is_valid(slug: str) -> bool:
    """발행 가능한 슬러그인지 확인."""
    if not slug or slug.startswith("-") or slug.endswith("-"):
        return False
    if "--" in slug or " " in slug:
        return False
    return bool(re.fullmatch(r"[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ-]+", slug))
