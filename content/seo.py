# -*- coding: utf-8 -*-
"""
SEO / AEO / GEO 검증 및 점수 산출.

세 축을 나눠서 봅니다.

  SEO (검색엔진 최적화)   - 구글·네이버가 '이 페이지가 무엇에 관한 글인지' 파악하게 함
                            메타 길이, 키워드 배치, 제목 구조, 슬러그, 내부링크
  AEO (답변엔진 최적화)   - 검색 결과 상단 답변·네이버 스마트블록에 발췌되게 함
                            질문형 소제목, 소제목 직후 직답, FAQ
  GEO (생성형엔진 최적화) - ChatGPT·구글 AI 개요 등이 '인용'하게 함
                            독립적으로 잘라도 뜻이 통하는 문장, 표·목록, 근거 기관,
                            고유명사(기관명) 일관성, 구조화 데이터

CMS 하드 리밋 (관리자 화면 안내 기준)
  MetaTitle       최대 40자
  MetaDescription 최대 80자
"""

import re

from content import clinic

META_TITLE_MAX = 40
META_DESC_MAX = 80

# 권장 범위
H1_RANGE = (25, 60)
BODY_MIN_CHARS = 1500
KEYWORD_DENSITY_RANGE = (0.005, 0.025)  # 0.5% ~ 2.5%
HASHTAG_RANGE = (8, 15)
MIN_H2 = 4
MIN_FAQ = 3

# 질문형 소제목 판별
_QUESTION = re.compile(r"[?？]|까요|나요|일까|무엇|어떻게|왜|언제|어디|어느|얼마")


def _text_of(doc: dict) -> str:
    """검사 대상 전체 텍스트를 하나로 합친다."""
    parts = [
        doc.get("h1", ""),
        doc.get("meta_title", ""),
        doc.get("meta_description", ""),
        doc.get("intro", ""),
        doc.get("answer_capsule", ""),
        doc.get("closing", ""),
    ]
    parts += doc.get("key_takeaways", []) or []
    for s in doc.get("sections", []) or []:
        parts.append(s.get("h2", ""))
        parts.append(s.get("answer", ""))
        for b in s.get("blocks", []) or []:
            parts.append(b.get("text", ""))
            parts += b.get("items", []) or []
            for row in b.get("rows", []) or []:
                parts += [str(c) for c in row]
            parts += b.get("headers", []) or []
    for f in doc.get("faq", []) or []:
        parts += [f.get("q", ""), f.get("a", "")]
    return "\n".join(p for p in parts if p)


def _body_text(doc: dict) -> str:
    """본문(메타 제외) 텍스트 - 분량·밀도 계산용."""
    parts = [doc.get("intro", ""), doc.get("answer_capsule", ""), doc.get("closing", "")]
    parts += doc.get("key_takeaways", []) or []
    for s in doc.get("sections", []) or []:
        parts.append(s.get("h2", ""))
        parts.append(s.get("answer", ""))
        for b in s.get("blocks", []) or []:
            parts.append(b.get("text", ""))
            parts += b.get("items", []) or []
    for f in doc.get("faq", []) or []:
        parts += [f.get("q", ""), f.get("a", "")]
    return "\n".join(p for p in parts if p)


def _squash(s: str) -> str:
    """공백을 지운 비교용 문자열.

    한국어 키워드는 띄어쓰기가 흔들려도 같은 검색어로 취급되므로
    ('발톱 무좀'과 '발톱무좀'), 포함 여부는 공백을 무시하고 판단한다.
    """
    return re.sub(r"\s+", "", s or "")


def _has(haystack: str, needle: str) -> bool:
    """공백을 무시한 포함 여부."""
    if not needle:
        return False
    return _squash(needle) in _squash(haystack)


def _count(haystack: str, needle: str) -> int:
    if not needle:
        return 0
    return _squash(haystack).count(_squash(needle))


def _check(ok: bool, weight: int, label: str, detail: str, fix: str = "") -> dict:
    return {
        "label": label,
        "passed": bool(ok),
        "weight": weight,
        "detail": detail,
        "fix": "" if ok else fix,
    }


# ── SEO ─────────────────────────────────────────────────────────────
def _seo_checks(doc: dict, primary: str) -> list:
    h1 = doc.get("h1", "") or ""
    mt = doc.get("meta_title", "") or ""
    md = doc.get("meta_description", "") or ""
    slug = doc.get("post_url", "") or ""
    tags = doc.get("hashtags", []) or []
    body = _body_text(doc)
    sections = doc.get("sections", []) or []

    # 밀도도 공백을 지운 기준으로 맞춘다(카운트와 분모의 기준을 일치시킴).
    squashed_body = _squash(body)
    density = (
        _count(body, primary) * len(_squash(primary)) / len(squashed_body)
        if squashed_body and primary
        else 0.0
    )
    lo, hi = KEYWORD_DENSITY_RANGE

    checks = [
        _check(
            0 < len(mt) <= META_TITLE_MAX,
            10, "MetaTitle 길이",
            f"{len(mt)}자 / 최대 {META_TITLE_MAX}자",
            f"{META_TITLE_MAX}자 이내로 줄이세요. CMS가 초과분을 잘라냅니다.",
        ),
        _check(
            _has(mt, primary),
            10, "MetaTitle 주키워드",
            f"'{primary}' {'포함' if _has(mt, primary) else '누락'}",
            "MetaTitle 앞쪽에 주키워드를 넣으세요.",
        ),
        _check(
            0 < len(md) <= META_DESC_MAX,
            10, "MetaDescription 길이",
            f"{len(md)}자 / 최대 {META_DESC_MAX}자",
            f"{META_DESC_MAX}자 이내로 줄이세요.",
        ),
        _check(
            _has(md, primary),
            8, "MetaDescription 주키워드",
            f"'{primary}' {'포함' if _has(md, primary) else '누락'}",
            "설명문에도 주키워드를 자연스럽게 넣으세요.",
        ),
        _check(
            H1_RANGE[0] <= len(h1) <= H1_RANGE[1],
            8, "H1 길이",
            f"{len(h1)}자 (권장 {H1_RANGE[0]}~{H1_RANGE[1]}자)",
            "너무 짧으면 정보가 부족하고 너무 길면 검색결과에서 잘립니다.",
        ),
        _check(
            _has(h1, primary),
            10, "H1 주키워드",
            f"'{primary}' {'포함' if _has(h1, primary) else '누락'}",
            "제목에 주키워드를 반드시 포함하세요.",
        ),
        _check(
            any(m in h1 for m in ("송도", "인천", "연수구")),
            8, "H1 지역명",
            "지역 키워드 " + ("포함" if any(m in h1 for m in ("송도", "인천", "연수구")) else "누락"),
            "지역 검색 노출을 위해 '송도' 또는 '인천'을 제목에 넣으세요.",
        ),
        _check(
            bool(slug) and _has(slug.replace("-", ""), primary),
            8, "포스트URL 키워드",
            slug[:50] + ("…" if len(slug) > 50 else ""),
            "슬러그에 주키워드가 들어가도록 제목을 조정하세요.",
        ),
        _check(
            HASHTAG_RANGE[0] <= len(tags) <= HASHTAG_RANGE[1],
            6, "해시태그 개수",
            f"{len(tags)}개 (권장 {HASHTAG_RANGE[0]}~{HASHTAG_RANGE[1]}개)",
            "너무 적으면 노출 경로가 좁고 너무 많으면 스팸으로 처리될 수 있습니다.",
        ),
        _check(
            len(body) >= BODY_MIN_CHARS,
            10, "본문 분량",
            f"{len(body)}자 (최소 {BODY_MIN_CHARS}자)",
            "정보량이 적으면 상위 노출이 어렵습니다. 섹션을 보강하세요.",
        ),
        _check(
            lo <= density <= hi,
            6, "주키워드 밀도",
            f"{density * 100:.2f}% (권장 {lo * 100:.1f}~{hi * 100:.1f}%)",
            "과하면 남용으로, 부족하면 주제 신호 부족으로 판단됩니다.",
        ),
        _check(
            len(sections) >= MIN_H2,
            6, "H2 섹션 수",
            f"{len(sections)}개 (최소 {MIN_H2}개)",
            "주제를 소제목으로 충분히 나누세요.",
        ),
    ]
    return checks


# ── AEO ─────────────────────────────────────────────────────────────
def _aeo_checks(doc: dict) -> list:
    sections = doc.get("sections", []) or []
    faq = doc.get("faq", []) or []
    capsule = doc.get("answer_capsule", "") or ""

    q_heads = [s for s in sections if _QUESTION.search(s.get("h2", ""))]
    answered = [s for s in sections if (s.get("answer") or "").strip()]
    good_answers = [
        s for s in answered if 40 <= len((s.get("answer") or "").strip()) <= 220
    ]
    q_faq = [f for f in faq if _QUESTION.search(f.get("q", ""))]

    return [
        _check(
            40 <= len(capsule) <= 220,
            14, "핵심 답변 캡슐",
            f"{len(capsule)}자 (권장 40~220자)",
            "글 첫머리에 질문에 대한 직답 2~3문장을 두세요. 발췌 답변으로 뽑히는 자리입니다.",
        ),
        _check(
            sections and len(q_heads) / len(sections) >= 0.5,
            12, "질문형 소제목 비율",
            f"{len(q_heads)}/{len(sections)}개 (권장 50% 이상)",
            "소제목을 사용자가 실제로 검색하는 질문 형태로 바꾸세요.",
        ),
        _check(
            sections and len(answered) == len(sections),
            14, "소제목 직후 직답",
            f"{len(answered)}/{len(sections)}개 섹션에 직답 존재",
            "각 소제목 바로 아래 결론 문장을 먼저 두고 설명을 이어가세요.",
        ),
        _check(
            answered and len(good_answers) / len(answered) >= 0.7,
            8, "직답 길이 적정성",
            f"{len(good_answers)}/{len(answered)}개가 40~220자",
            "직답은 2~3문장으로 자르세요. 너무 길면 발췌되지 않습니다.",
        ),
        _check(
            len(faq) >= MIN_FAQ,
            12, "FAQ 개수",
            f"{len(faq)}개 (최소 {MIN_FAQ}개)",
            "FAQ는 FAQPage 구조화 데이터로 변환되어 검색결과에 직접 노출됩니다.",
        ),
        _check(
            faq and len(q_faq) == len(faq),
            6, "FAQ 질문 형식",
            f"{len(q_faq)}/{len(faq)}개가 질문형",
            "FAQ 질문은 실제 검색어 형태의 완결된 의문문으로 쓰세요.",
        ),
        _check(
            all(20 <= len(f.get("a", "")) <= 400 for f in faq) if faq else False,
            6, "FAQ 답변 길이",
            "모든 답변 20~400자" if faq else "FAQ 없음",
            "FAQ 답변은 첫 문장에서 결론을 내고 400자를 넘기지 마세요.",
        ),
    ]


# ── GEO ─────────────────────────────────────────────────────────────
def _geo_checks(doc: dict, primary: str) -> list:
    text = _text_of(doc)
    takeaways = doc.get("key_takeaways", []) or []
    sections = doc.get("sections", []) or []
    citations = doc.get("citations", []) or []
    internal = (
        doc.get("internal_link_suggestions")
        or doc.get("internal_links")
        or []
    )

    has_table = any(
        b.get("type") == "table"
        for s in sections
        for b in (s.get("blocks") or [])
    )
    has_list = any(
        b.get("type") in ("list", "steps")
        for s in sections
        for b in (s.get("blocks") or [])
    )
    entity_hits = _count(text, clinic.OFFICIAL_NAME) + _count(text, clinic.SHORT_NAME)
    known_orgs = [s["org"] for s in clinic.AUTHORITATIVE_SOURCES]
    org_mentions = [o for o in known_orgs if o.split()[0] in text]
    nap = clinic.nap_completeness()

    # 인용 친화 문장: 25~120자, 지시어로 시작하지 않는 독립 문장
    standalone = [t for t in takeaways if 25 <= len(t) <= 120 and not t.startswith(("이", "그", "저"))]

    return [
        _check(
            len(takeaways) >= 3,
            14, "핵심 요약 블록",
            f"{len(takeaways)}개 항목",
            "AI가 통째로 인용할 수 있는 요약 불릿 3개 이상을 두세요.",
        ),
        _check(
            takeaways and len(standalone) / len(takeaways) >= 0.7,
            12, "인용 가능한 독립 문장",
            f"{len(standalone)}/{len(takeaways)}개가 문맥 없이 성립",
            "'이것은', '그래서' 같은 지시어를 빼고 주어를 명시한 완결 문장으로 쓰세요.",
        ),
        _check(
            has_table,
            10, "표 형식 데이터",
            "표 " + ("포함" if has_table else "없음"),
            "비교·분류 내용을 표로 만들면 생성형 검색이 구조를 그대로 읽어갑니다.",
        ),
        _check(
            has_list,
            8, "목록/단계 구조",
            "목록 " + ("포함" if has_list else "없음"),
            "절차와 조건은 번호 목록으로 정리하세요.",
        ),
        _check(
            entity_hits >= 3,
            12, "기관명 일관성",
            f"기관명 {entity_hits}회 언급",
            f"'{clinic.OFFICIAL_NAME}' 정식 표기를 본문에 3회 이상 일관되게 쓰세요.",
        ),
        _check(
            len(org_mentions) >= 1,
            12, "공신력 있는 출처 언급",
            f"{len(org_mentions)}개 기관 인용" if org_mentions else "없음",
            "질병관리청·식약처 등 공신력 있는 기관을 근거로 언급하면 인용 확률이 올라갑니다.",
        ),
        _check(
            len(citations) >= 1,
            8, "출처 목록",
            f"{len(citations)}건",
            "본문 하단에 참고 출처를 URL과 함께 명시하세요.",
        ),
        _check(
            len(internal) >= 2,
            8, "내부링크",
            f"{len(internal)}개",
            "관련 글로 이어지는 내부링크 2개 이상을 넣어 주제 클러스터를 만드세요.",
        ),
        _check(
            nap["complete"],
            16, "NAP·E-E-A-T 정보",
            "완비" if nap["complete"] else "누락: " + ", ".join(nap["missing"]),
            ".env에 병원 주소·전화·진료시간·작성 의료진을 채우세요. "
            "구글 건강 콘텐츠 평가와 지역 검색에 직접 영향을 줍니다.",
        ),
    ]


def _score(checks: list) -> int:
    total = sum(c["weight"] for c in checks) or 1
    got = sum(c["weight"] for c in checks if c["passed"])
    return round(got / total * 100)


def audit(doc: dict, primary: str = "") -> dict:
    """생성 결과를 세 축으로 평가한다."""
    primary = primary or doc.get("primary_keyword", "") or ""
    seo = _seo_checks(doc, primary)
    aeo = _aeo_checks(doc)
    geo = _geo_checks(doc, primary)

    scores = {"seo": _score(seo), "aeo": _score(aeo), "geo": _score(geo)}
    scores["total"] = round((scores["seo"] + scores["aeo"] + scores["geo"]) / 3)

    failed = [c for c in (seo + aeo + geo) if not c["passed"]]
    failed.sort(key=lambda c: -c["weight"])

    return {
        "scores": scores,
        "checks": {"seo": seo, "aeo": aeo, "geo": geo},
        "top_fixes": failed[:6],
        "grade": _grade(scores["total"]),
    }


def _grade(score: int) -> str:
    if score >= 90:
        return "발행 가능"
    if score >= 75:
        return "보완 후 발행 권장"
    if score >= 60:
        return "보완 필요"
    return "재작성 권장"
