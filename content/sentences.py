# -*- coding: utf-8 -*-
"""
지적된 표현이 들어 있는 문장 하나를 잘라 낸다.

검사 결과에 "이 문장" 을 함께 실어 보내면, 검수자가 원고 전체를 뒤지지
않고 그 자리에서 고칠 수 있습니다. 문맥 미리보기(앞뒤 30자, 말줄임표)는
읽기용이라 그대로 고쳐 쓸 수 없습니다.
"""

import re

_END = re.compile(r"[.!?\n]")
_MAX = 400  # 문장 구분이 없는 글에서 너무 길게 잡히지 않도록


def around(text: str, start: int, end: int) -> str:
    """[start, end) 를 품은 문장. 앞뒤 문장 부호까지만 자른다."""
    lo = 0
    for m in _END.finditer(text, 0, start):
        lo = m.end()
    tail = _END.search(text, end)
    hi = tail.end() if tail else len(text)
    lo = max(lo, start - _MAX)
    hi = min(hi, end + _MAX)
    return text[lo:hi].strip()
