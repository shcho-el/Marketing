# -*- coding: utf-8 -*-
"""
생성 결과(JSON) → 발행용 HTML 본문.

CMS 본문 편집기에 그대로 붙여 넣을 수 있는 형태로 만듭니다.
의료법 필수 고지와 JSON-LD는 여기서 자동으로 덧붙습니다(모델이 빠뜨려도 항상 들어감).

소제목에는 id를 남겨 둡니다. 목차는 넣지 않지만 다른 글에서 특정 절로
바로 연결할 때 쓸 수 있습니다.
"""

import html
import urllib.parse

from content import clinic, schema, taxonomy


def _esc(s) -> str:
    return html.escape(str(s or ""), quote=False)


def _anchor_id(index: int) -> str:
    return f"s{index + 1}"


def _render_block(block: dict) -> str:
    btype = block.get("type", "paragraph")

    if btype == "paragraph":
        return f"<p>{_esc(block.get('text'))}</p>"

    if btype == "callout":
        return (
            '<blockquote class="callout">'
            f"<p>{_esc(block.get('text'))}</p>"
            "</blockquote>"
        )

    if btype == "list":
        items = "".join(f"<li>{_esc(i)}</li>" for i in block.get("items", []) or [])
        return f"<ul>{items}</ul>" if items else ""

    if btype == "steps":
        items = "".join(f"<li>{_esc(i)}</li>" for i in block.get("items", []) or [])
        return f"<ol>{items}</ol>" if items else ""

    if btype == "table":
        headers = block.get("headers", []) or []
        rows = block.get("rows", []) or []
        if not headers or not rows:
            return ""
        head = "".join(f"<th scope=\"col\">{_esc(h)}</th>" for h in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>"
            for row in rows
        )
        return (
            '<div class="table-wrap"><table>'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody>"
            "</table></div>"
        )

    return ""


def _render_notice() -> str:
    """의료법 제56조 제2항 제5호 대응 - 부작용 등 중요정보 고지."""
    items = "".join(f"<li>{_esc(i)}</li>" for i in clinic.MANDATORY_NOTICE["items"])
    review_no = ""
    if clinic.AD_REVIEW_NUMBER:
        review_no = f'<p class="review-no">의료광고 심의번호: {_esc(clinic.AD_REVIEW_NUMBER)}</p>'
    return (
        '<section class="medical-notice">'
        f"<h2>{_esc(clinic.MANDATORY_NOTICE['heading'])}</h2>"
        f"<ol>{items}</ol>"
        f"{review_no}"
        "</section>"
    )


def _render_location() -> str:
    """찾아오시는 길 - NAP 일관성 확보용. 값이 없으면 생략한다."""
    rows = []
    location = " ".join(
        p for p in (clinic.ADDRESS_REGION, clinic.ADDRESS_LOCALITY, clinic.ADDRESS_STREET) if p
    )
    if clinic.ADDRESS_STREET:
        rows.append(("주소", location))
    if clinic.PHONE:
        rows.append(("전화", clinic.PHONE))
    if clinic.OPENING_HOURS:
        rows.append(("진료시간", clinic.OPENING_HOURS))
    if not rows:
        return ""
    body = "".join(f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in rows)
    return (
        '<section class="location">'
        f"<h2>{_esc(clinic.FULL_NAME)} 찾아오시는 길</h2>"
        f"<dl>{body}</dl>"
        "</section>"
    )


def _render_author() -> str:
    """E-E-A-T 신호 - 작성/감수 표기."""
    author = clinic.AUTHOR
    if not author["name"]:
        return ""
    line = f"{author['name']} {author['job_title']}"
    reviewer = clinic.REVIEWER
    if reviewer["name"] and reviewer["name"] != author["name"]:
        line += f" 작성 · {reviewer['name']} {reviewer['job_title']} 감수"
    else:
        line += " 작성·감수"
    return f'<p class="byline">{_esc(clinic.FULL_NAME)} | {_esc(line)}</p>'


def _render_citations(doc: dict) -> str:
    cites = doc.get("citations", []) or []
    if not cites:
        return ""
    lis = []
    for c in cites:
        label = c.get("title") or c.get("org", "")
        org = c.get("org", "")
        url = c.get("url", "")
        text = f"{_esc(org)} — {_esc(label)}" if org and label != org else _esc(label or org)
        if url:
            lis.append(f'<li>{text} <a href="{_esc(url)}" rel="nofollow noopener" target="_blank">바로가기</a></li>')
        else:
            lis.append(f"<li>{text}</li>")
    return '<section class="citations"><h2>참고 자료</h2><ul>' + "".join(lis) + "</ul></section>"


def render_body(doc: dict, include_schema: bool = True) -> str:
    """CMS 본문에 넣을 HTML 전체."""
    parts = [f"<h1>{_esc(doc.get('h1'))}</h1>"]

    byline = _render_author()
    if byline:
        parts.append(byline)

    if doc.get("intro"):
        parts.append(f"<p>{_esc(doc['intro'])}</p>")

    # 답변 캡슐 - 발췌 대상 1순위. 본문 맨 앞에 둔다.
    if doc.get("answer_capsule"):
        parts.append(
            '<section class="answer-capsule"><h2>한눈에 보는 답</h2>'
            f"<p>{_esc(doc['answer_capsule'])}</p></section>"
        )

    for i, section in enumerate(doc.get("sections", []) or []):
        parts.append(f'<h2 id="{_anchor_id(i)}">{_esc(section.get("h2"))}</h2>')
        if section.get("answer"):
            parts.append(f'<p class="direct-answer">{_esc(section["answer"])}</p>')
        for block in section.get("blocks", []) or []:
            rendered = _render_block(block)
            if rendered:
                parts.append(rendered)

    takeaways = doc.get("key_takeaways", []) or []
    if takeaways:
        items = "".join(f"<li>{_esc(t)}</li>" for t in takeaways)
        parts.append(
            '<section class="key-takeaways"><h2>핵심 요약</h2>'
            f"<ul>{items}</ul></section>"
        )

    faq = doc.get("faq", []) or []
    if faq:
        blocks = "".join(
            f"<h3>Q. {_esc(f.get('q'))}</h3><p>A. {_esc(f.get('a'))}</p>" for f in faq
        )
        parts.append(f'<section class="faq"><h2>자주 묻는 질문</h2>{blocks}</section>')

    if doc.get("closing"):
        parts.append(f"<p>{_esc(doc['closing'])}</p>")

    parts.append(_render_notice())

    cites = _render_citations(doc)
    if cites:
        parts.append(cites)

    location = _render_location()
    if location:
        parts.append(location)

    tags = doc.get("hashtags", []) or []
    if tags:
        parts.append(f'<p class="hashtags">{_esc(" ".join(tags))}</p>')

    if include_schema:
        parts.append(schema.to_script_tag(doc))

    return "\n".join(parts)


def render_plaintext(doc: dict) -> str:
    """네이버 블로그 등 HTML을 못 쓰는 곳에 붙일 평문 버전."""
    out = [doc.get("h1", ""), ""]
    if doc.get("intro"):
        out += [doc["intro"], ""]
    if doc.get("answer_capsule"):
        out += ["[한눈에 보는 답]", doc["answer_capsule"], ""]

    for i, s in enumerate(doc.get("sections", []) or [], 1):
        out.append(f"{i}. {s.get('h2', '')}")
        if s.get("answer"):
            out.append(s["answer"])
        for b in s.get("blocks", []) or []:
            t = b.get("type")
            if t in ("paragraph", "callout") and b.get("text"):
                out.append(b["text"])
            elif t == "list":
                out += [f"  · {i}" for i in b.get("items", []) or []]
            elif t == "steps":
                out += [f"  {n}) {v}" for n, v in enumerate(b.get("items", []) or [], 1)]
            elif t == "table":
                headers = b.get("headers", []) or []
                if headers:
                    out.append("  | " + " | ".join(headers) + " |")
                    for row in b.get("rows", []) or []:
                        out.append("  | " + " | ".join(str(c) for c in row) + " |")
        out.append("")

    takeaways = doc.get("key_takeaways", []) or []
    if takeaways:
        out.append("핵심 요약")
        out += [f"  · {t}" for t in takeaways]
        out.append("")

    faq = doc.get("faq", []) or []
    if faq:
        out.append("자주 묻는 질문")
        for f in faq:
            out += [f"Q. {f.get('q', '')}", f"A. {f.get('a', '')}", ""]

    if doc.get("closing"):
        out += [doc["closing"], ""]

    out.append(clinic.MANDATORY_NOTICE["heading"])
    out += [f"  {i + 1}. {v}" for i, v in enumerate(clinic.MANDATORY_NOTICE["items"])]
    out.append("")

    tags = doc.get("hashtags", []) or []
    if tags:
        out.append(" ".join(tags))

    return "\n".join(out)


def cms_fields(doc: dict) -> dict:
    """CMS '기본 정보' 폼에 그대로 옮겨 담을 값."""
    return {
        "노출여부": "미노출 (검수 후 노출로 변경)",
        "카테고리": doc.get("category", ""),
        "제목(H1)": doc.get("h1", ""),
        "포스트URL": doc.get("post_url", ""),
        "MetaTitle": doc.get("meta_title", ""),
        "MetaDescription": doc.get("meta_description", ""),
        "해시태그": "\n".join(doc.get("hashtags", []) or []),
        "썸네일 문구": doc.get("thumbnail_copy", ""),
        "발행 예정 URL": doc.get("published_url", ""),
    }
