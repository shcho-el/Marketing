# -*- coding: utf-8 -*-
"""
원고의 한 문장을 고쳐 넣는다.

검사가 "이 표현은 못 씁니다"라고만 하고 고칠 자리를 주지 않으면, 검수자는
클라우드로 돌아가 다시 만들거나 원고를 통째로 다시 붙여넣어야 합니다.
지적된 문장 하나만 바꿔 다시 검사하는 길을 둡니다.

문장이 원고의 어느 칸에 있는지는 모릅니다. 그래서 글자를 담는 칸을 전부
훑어 처음 만나는 곳 한 군데만 바꿉니다. 여러 곳을 한꺼번에 바꾸면 의도치
않은 자리까지 건드립니다.
"""


class EditError(ValueError):
    """고치지 못한 이유. 그대로 화면에 보여 준다."""


def _squash(s: str) -> str:
    return " ".join(str(s or "").split())


def _swap(value, old: str, new: str, state: dict):
    """문자열이면 바꾸고, 목록·사전이면 안쪽까지 내려간다."""
    if state["done"]:
        return value

    if isinstance(value, str):
        if old in value:
            state["done"] = True
            return value.replace(old, new, 1)
        # 줄바꿈·공백만 다른 경우까지 받아 준다. 화면에서 옮겨 적으며 흔히 생긴다.
        if _squash(old) and _squash(old) in _squash(value):
            state["done"] = True
            return _squash(value).replace(_squash(old), new, 1)
        return value

    if isinstance(value, list):
        return [_swap(v, old, new, state) for v in value]

    if isinstance(value, dict):
        return {k: _swap(v, old, new, state) for k, v in value.items()}

    return value


# 사람이 읽는 글이 들어가는 칸만 훑는다. post_url·category 는 건드리지 않는다.
TEXT_FIELDS = (
    "h1",
    "meta_title",
    "meta_description",
    "thumbnail_copy",
    "answer_capsule",
    "intro",
    "closing",
    "key_takeaways",
    "sections",
    "faq",
)


def replace_sentence(doc: dict, old: str, new: str) -> dict:
    """원고에서 old 를 new 로 한 군데 바꾼 사본을 돌려준다."""
    old, new = str(old or "").strip(), str(new or "").strip()
    if not old:
        raise EditError("고칠 문장이 비어 있습니다.")
    if not new:
        raise EditError("새 문장이 비어 있습니다. 문장을 지우려면 원고를 다시 만드세요.")
    if old == new:
        raise EditError("내용이 그대로입니다.")

    fixed = dict(doc)
    state = {"done": False}
    for key in TEXT_FIELDS:
        if key not in fixed:
            continue
        fixed[key] = _swap(fixed[key], old, new, state)
        if state["done"]:
            break

    if not state["done"]:
        raise EditError(
            "원고에서 그 문장을 찾지 못했습니다.\n"
            "문장을 옮겨 적는 과정에서 글자가 달라졌을 수 있습니다."
        )
    return fixed
