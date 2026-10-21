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


CELL_SEP = "|"  # generator.CELL_SEP 의 구분 기호. 앞뒤 공백은 사람이 지워도 된다.


def _split_cells(text: str) -> list:
    return [c.strip() for c in text.split(CELL_SEP)]


def _swap_cells(cells: list, olds: list, news: list):
    """행 안에서 olds 와 이어지는 칸들을 찾아 news 로 바꾼 행. 못 찾으면 None.

    지적 문장은 마침표에서 잘리므로 첫 칸은 뒷부분만, 끝 칸은 앞부분만
    들어 있을 수 있다. 가운데 칸은 통째로 같아야 한다.
    """
    n = len(olds)
    for i in range(len(cells) - n + 1):
        out = list(cells)
        for k, (o, w) in enumerate(zip(olds, news)):
            cell = str(cells[i + k]).strip()
            if _squash(cell) == _squash(o):
                out[i + k] = w
            elif k == 0 and n > 1 and cell.endswith(o):
                out[i + k] = cell[: len(cell) - len(o)] + w
            elif k == n - 1 and n > 1 and cell.startswith(o):
                out[i + k] = w + cell[len(o):]
            else:
                break
        else:
            return out
    return None


def _replace_row(doc: dict, old: str, new: str) -> dict:
    """표의 한 행에 걸친 지적 문장을 칸 단위로 바꾼다."""
    olds, news = _split_cells(old), _split_cells(new)
    if len(olds) != len(news):
        raise EditError(
            f"표의 칸 수가 달라졌습니다(원래 {len(olds)}칸, 지금 {len(news)}칸).\n"
            "칸을 나누는 '|' 표시는 지우거나 더하지 말고 칸 안의 글자만 고치세요."
        )

    fixed = dict(doc)
    sections = []
    done = False
    for s in doc.get("sections", []) or []:
        s = dict(s)
        blocks = []
        for b in s.get("blocks", []) or []:
            b = dict(b)
            if not done and b.get("type") == "table":
                swapped = _swap_cells(b.get("headers") or [], olds, news)
                if swapped is not None:
                    b["headers"], done = swapped, True
                else:
                    rows = []
                    for row in b.get("rows") or []:
                        swapped = None if done else _swap_cells(row, olds, news)
                        if swapped is not None:
                            row, done = swapped, True
                        rows.append(row)
                    b["rows"] = rows
            blocks.append(b)
        s["blocks"] = blocks
        sections.append(s)
    if not done:
        raise EditError(
            "원고의 표에서 그 행을 찾지 못했습니다.\n"
            "칸 안의 글자만 고치고 '|' 표시는 그대로 두세요."
        )
    fixed["sections"] = sections
    return fixed


def replace_sentence(doc: dict, old: str, new: str) -> dict:
    """원고에서 old 를 new 로 한 군데 바꾼 사본을 돌려준다."""
    old, new = str(old or "").strip(), str(new or "").strip()
    if not old:
        raise EditError("고칠 문장이 비어 있습니다.")
    if not new:
        raise EditError("새 문장이 비어 있습니다. 문장을 지우려면 원고를 다시 만드세요.")
    if old == new:
        raise EditError("내용이 그대로입니다.")

    # 표의 한 행에서 나온 지적이면 칸 단위로 바꾼다. 칸 하나에 담긴 글이
    # 아니라서 아래의 문자열 찾기로는 찾을 수 없다.
    if f" {CELL_SEP} " in old:
        return _replace_row(doc, old, new)

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
