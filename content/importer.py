# -*- coding: utf-8 -*-
"""
외부에서 만든 원고를 가져온다.

클라우드 웹앱(구독으로 동작)에서 원고를 만들고, CMS 업로드가 되는 로컬 앱으로
옮기기 위한 통로입니다. API 요금을 쓰지 않고 전 과정을 잇습니다.

붙여넣는 값은 사람이 손으로 옮긴 것이라 어디가 틀렸는지 정확히 알려 줘야 합니다.
"필요한 항목이 없습니다" 같은 뭉뚱그린 오류는 도움이 되지 않습니다.
"""

import json

from content import generator, taxonomy

# 없으면 글이 성립하지 않는 항목
REQUIRED = {
    "h1": "제목",
    "meta_title": "MetaTitle",
    "meta_description": "MetaDescription",
    "sections": "본문 섹션",
}

# 없어도 되지만 비어 있으면 점수가 깎이는 항목
EXPECTED = {
    "answer_capsule": "핵심 답변",
    "key_takeaways": "핵심 요약",
    "faq": "자주 묻는 질문",
    "hashtags": "해시태그",
    "toc": "목차",
    "intro": "도입부",
    "closing": "마무리",
    "citations": "출처",
}


class ImportError_(ValueError):
    """가져오기 실패. 메시지는 그대로 화면에 보여 준다."""


def _parse(raw):
    """붙여넣은 값을 딕셔너리로 만든다."""
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        raise ImportError_("붙여넣은 내용이 없습니다.")

    # 코드블록 표시를 함께 복사한 경우를 걷어낸다
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportError_(
            "JSON 형식이 아닙니다. 클라우드 웹앱의 '원고 내보내기' 버튼으로 "
            f"복사한 내용을 그대로 붙여넣어 주세요.\n(위치 {exc.lineno}행 {exc.colno}칸: {exc.msg})"
        ) from exc

    if not isinstance(data, dict):
        raise ImportError_("원고 한 편(JSON 객체)이 아닙니다.")
    return data


def _check_sections(sections):
    if not isinstance(sections, list) or not sections:
        raise ImportError_("본문 섹션이 비어 있습니다.")
    for i, s in enumerate(sections, 1):
        if not isinstance(s, dict) or not s.get("h2"):
            raise ImportError_(f"{i}번째 섹션에 소제목(h2)이 없습니다.")
        blocks = s.get("blocks")
        if blocks is not None and not isinstance(blocks, list):
            raise ImportError_(f"{i}번째 섹션의 blocks 형식이 올바르지 않습니다.")


def _fill_defaults(doc):
    """비어 있어도 렌더링이 깨지지 않도록 기본값을 채운다."""
    for key in ("key_takeaways", "hashtags", "toc", "faq", "citations",
                "internal_link_suggestions"):
        if not isinstance(doc.get(key), list):
            doc[key] = []
    for key in ("intro", "closing", "answer_capsule", "thumbnail_copy"):
        if not isinstance(doc.get(key), str):
            doc[key] = ""
    for s in doc.get("sections", []):
        s.setdefault("answer", "")
        blocks = s.setdefault("blocks", [])
        for b in blocks:
            b.setdefault("type", "paragraph")
            b.setdefault("text", "")
            for k in ("items", "headers", "rows"):
                if not isinstance(b.get(k), list):
                    b[k] = []
    if not doc["thumbnail_copy"]:
        doc["thumbnail_copy"] = doc.get("primary_keyword") or ""
    return doc


def load(raw) -> dict:
    """붙여넣은 원고를 검증하고 발행 가능한 형태로 만든다.

    돌려주는 값: {"doc": ..., "reports": ..., "warnings": [...]}
    """
    data = _parse(raw)

    missing = [label for key, label in REQUIRED.items() if not data.get(key)]
    if missing:
        raise ImportError_(
            "필수 항목이 비어 있습니다: " + ", ".join(missing) +
            "\n클라우드 웹앱에서 원고가 다 만들어진 뒤에 내보내기를 눌러 주세요."
        )

    _check_sections(data["sections"])

    # 카테고리·주키워드는 없으면 제목에서 추론한다.
    from content import title_parser

    parsed = title_parser.parse(data.get("h1", ""))
    category = data.get("category") or parsed["category"]
    if category not in taxonomy.CATEGORIES:
        raise ImportError_(
            f"'{category}' 는 CMS 카테고리 목록에 없습니다.\n"
            f"사용 가능: {', '.join(taxonomy.CATEGORIES)}"
        )
    keyword = data.get("primary_keyword") or parsed["primary_keyword"]

    doc = _fill_defaults(dict(data))
    doc = generator._normalize(doc, category, keyword)
    doc["_imported"] = True

    warnings = [
        label for key, label in EXPECTED.items() if not doc.get(key)
    ]
    reports = generator.evaluate(doc)
    return {"doc": doc, "reports": reports, "warnings": warnings, "topic": parsed["topic"]}
