# -*- coding: utf-8 -*-
"""
생성 프롬프트와 출력 스키마.

출력은 Structured Outputs(output_config.format)로 강제해 항상 같은 JSON이 나오게 합니다.
그래야 CMS 필드 매핑·의료법 검사·JSON-LD 생성이 기계적으로 이어집니다.
"""

from content import clinic, medical_law, seo, slug, taxonomy


# ── 출력 JSON 스키마 ─────────────────────────────────────────────────
_BLOCK = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["paragraph", "list", "steps", "table", "callout"],
            "description": "문단 / 불릿목록 / 번호단계 / 표 / 강조박스",
        },
        "text": {
            "type": "string",
            "description": "paragraph·callout일 때 본문. 그 외에는 빈 문자열.",
        },
        "items": {
            "type": "array",
            "items": {"type": "string"},
            "description": "list·steps일 때 항목. 그 외에는 빈 배열.",
        },
        "headers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "table일 때 열 제목. 그 외에는 빈 배열.",
        },
        "rows": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
            "description": "table일 때 행 데이터. 그 외에는 빈 배열.",
        },
    },
    "required": ["type", "text", "items", "headers", "rows"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "h1": {
            "type": "string",
            "description": "제목(H1). 주키워드와 지역명 포함, 25~60자.",
        },
        "meta_title": {
            "type": "string",
            "description": f"MetaTitle. 반드시 {seo.META_TITLE_MAX}자 이내. 주키워드를 앞쪽에.",
        },
        "meta_description": {
            "type": "string",
            "description": f"MetaDescription. 반드시 {seo.META_DESC_MAX}자 이내. "
                           "주키워드 포함, 글이 답하는 질문을 명시.",
        },
        "thumbnail_copy": {
            "type": "string",
            "description": "썸네일 이미지 정중앙에 넣을 문구. 12자 이내 두 줄 이하.",
        },
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "'#'로 시작하는 해시태그 10~14개.",
        },
        "answer_capsule": {
            "type": "string",
            "description": "제목이 던진 질문에 대한 직답 2~3문장(40~220자). "
                           "이 단락만 잘라내도 완결된 답이 되어야 함.",
        },
        "intro": {
            "type": "string",
            "description": "도입부 2~4문장. 인사 + 이 글이 다루는 범위.",
        },
        "toc": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "목차에 표시할 문구"},
                    "target_h2": {"type": "string", "description": "연결될 H2 제목과 정확히 동일"},
                },
                "required": ["label", "target_h2"],
                "additionalProperties": False,
            },
            "description": "본문 H2와 1:1로 대응하는 목차.",
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "h2": {
                        "type": "string",
                        "description": "소제목. 절반 이상은 사용자가 실제 검색하는 질문형.",
                    },
                    "answer": {
                        "type": "string",
                        "description": "소제목 바로 아래 놓일 직답 2~3문장(40~220자). 결론 먼저.",
                    },
                    "blocks": {"type": "array", "items": _BLOCK},
                },
                "required": ["h2", "answer", "blocks"],
                "additionalProperties": False,
            },
        },
        "key_takeaways": {
            "type": "array",
            "items": {"type": "string"},
            "description": "핵심 요약 3~5개. 각 25~120자. 지시어 없이 주어를 갖춘 완결 문장.",
        },
        "faq": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "실제 검색어 형태의 완결된 의문문"},
                    "a": {"type": "string", "description": "첫 문장에 결론. 20~400자."},
                },
                "required": ["q", "a"],
                "additionalProperties": False,
            },
            "description": "FAQ 4~6개.",
        },
        "closing": {
            "type": "string",
            "description": "마무리 2~3문장. 진료 안내로 연결하되 유인성 표현 금지.",
        },
        "internal_link_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "anchor_text": {"type": "string"},
                    "target_topic": {"type": "string", "description": "연결할 글의 주제"},
                },
                "required": ["anchor_text", "target_topic"],
                "additionalProperties": False,
            },
            "description": "내부링크 후보 2~4개.",
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "org": {"type": "string"},
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["org", "title", "url"],
                "additionalProperties": False,
            },
            "description": "제공된 근거 기관 목록에서만 선택. 임의 URL 생성 금지.",
        },
    },
    "required": [
        "h1",
        "meta_title",
        "meta_description",
        "thumbnail_copy",
        "hashtags",
        "answer_capsule",
        "intro",
        "toc",
        "sections",
        "key_takeaways",
        "faq",
        "closing",
        "internal_link_suggestions",
        "citations",
    ],
    "additionalProperties": False,
}


# ── 시스템 프롬프트 ───────────────────────────────────────────────────
SYSTEM = f"""당신은 {clinic.FULL_NAME}의 콘텐츠 에디터입니다.
대한민국 의료법과 의료광고 심의 기준을 숙지한 상태로, 환자에게 실제로 도움이 되는
의학 정보 글을 씁니다. 광고 문구가 아니라 '읽고 나면 판단할 수 있게 되는 글'이 목표입니다.

## 사실 제약 (가장 중요)
아래 [허용된 사실]에 없는 내용은 쓰지 마십시오. 특히 다음을 절대 지어내지 마십시오.
- 보유하지 않은 장비명, 시술명, 프로그램명
- 치료 성공률·만족도·환자 수 등 모든 통계 수치
- 논문·학회 인용을 가장한 출처 (제시된 기관 목록 밖의 URL 금지)
- 원장 경력, 수상 이력, 언론 보도
불확실하면 쓰지 않습니다. 분량을 채우려고 추정을 사실처럼 서술하지 마십시오.

{clinic.facts_block()}

## 의료법 준수
{medical_law.rules_for_prompt()}

추가로 지켜야 할 문체 원칙:
- 환자의 불안을 자극해 내원을 압박하지 않습니다. 위험은 사실 그대로만 알립니다.
- 진단·치료 결과를 단정하지 않고 "~할 수 있습니다", "~가 권장됩니다"로 씁니다.
- 병원 홍보 문단은 전체의 20%를 넘기지 않습니다. 나머지는 순수 정보입니다.
- 특정 치료를 유일한 해답처럼 제시하지 않고, 대안과 각각이 적합한 상황을 함께 설명합니다.

## 구조 설계 원칙
검색엔진, 답변엔진(네이버 스마트블록·구글 AI 개요), 생성형 검색(ChatGPT 등)이
각각 다른 것을 봅니다. 세 가지를 동시에 만족시키는 구조로 씁니다.

1) 검색엔진(SEO)
- MetaTitle은 {seo.META_TITLE_MAX}자, MetaDescription은 {seo.META_DESC_MAX}자를 절대 넘기지 않습니다.
  (CMS가 초과분을 잘라냅니다. 세는 단위는 공백 포함 글자 수입니다.)
- H1에 주키워드와 지역명을 모두 넣습니다.
- 주키워드를 본문 전체에 자연스럽게 분산합니다. 억지로 반복하지 않습니다.

2) 답변엔진(AEO)
- 글 맨 앞 answer_capsule에 제목이 던진 질문의 답을 먼저 씁니다.
- H2의 절반 이상을 사용자가 실제로 검색창에 치는 질문 형태로 만듭니다.
  (예: "발톱무좀은 왜 약을 발라도 낫지 않나요?")
- 모든 H2 바로 아래 answer에 2~3문장 결론을 먼저 놓고, 그 뒤에 blocks로 근거를 폅니다.
- FAQ 질문은 검색어 그대로, 답변은 첫 문장에서 결론을 냅니다.

3) 생성형 검색(GEO)
- key_takeaways의 각 문장은 앞뒤 문맥 없이 그대로 인용해도 뜻이 통해야 합니다.
  "이것은", "그래서", "위에서 말한" 같은 지시어로 시작하지 마십시오.
  주어를 명시하고("발톱무좀은", "{clinic.SHORT_NAME}은") 한 문장에 한 사실만 담습니다.
- 비교·분류·조건 정보는 반드시 table 블록으로 만듭니다. 생성형 검색이 표를 그대로 읽어갑니다.
- 절차와 조건은 steps/list 블록으로 정리합니다.
- 기관명은 첫 등장 시 "{clinic.OFFICIAL_NAME} {clinic.CLINIC_NAME}" 정식 표기를 쓰고,
  이후에는 "{clinic.SHORT_NAME}"으로 일관되게 씁니다. 표기를 뒤섞지 마십시오.
- 제시된 근거 기관을 본문에서 1회 이상 언급하고 citations에 담습니다.

## 블록 사용법
- paragraph: text에만 내용을 담고 items/headers/rows는 빈 배열.
- list / steps: items에만 담고 text는 빈 문자열.
- table: headers와 rows에만 담고 text는 빈 문자열. 모든 행의 길이가 headers와 같아야 함.
- callout: 주의·요점 강조. text에만 담음.

## 분량
본문(intro+sections+faq) 합계 1,800자 이상 3,500자 이하. H2는 4~6개.
부작용·주의사항 고지는 시스템이 자동으로 덧붙이므로 별도 섹션으로 쓰지 마십시오.
단, 본문 안에서 개인차와 이상반응 가능성은 자연스럽게 언급합니다."""


def build_user_prompt(
    category: str,
    primary_keyword: str,
    topic: str,
    angle: str = "",
    audience: str = "",
    extra_notes: str = "",
) -> str:
    """생성 요청 프롬프트를 조립한다."""
    kw = taxonomy.build_keyword_set(category, primary_keyword)
    tags = taxonomy.suggest_hashtags(category, primary_keyword)

    lines = [
        "다음 조건으로 블로그 글 1편을 작성해 주십시오.",
        "",
        f"[카테고리] {category}",
        f"[주키워드] {kw['primary']}",
    ]
    if kw["secondary"]:
        lines.append(f"[보조키워드] {', '.join(kw['secondary'])}")
    if kw["local"]:
        lines.append(f"[지역 조합 키워드] {', '.join(kw['local'])}")
    lines.append(f"[롱테일 질의] {', '.join(kw['longtail'])}")
    lines.append(f"[다룰 주제] {topic}")

    if angle:
        lines.append(f"[관점/논지] {angle}")
    if audience:
        lines.append(f"[주요 독자] {audience}")
    if extra_notes:
        lines.append(f"[추가 지시] {extra_notes}")

    lines += [
        "",
        f"[해시태그 후보] {' '.join(tags)}",
        "위 후보 중에서 주제와 맞는 것을 고르고, 본문 핵심어 기반 태그를 2~3개 더 만들어",
        "총 10~14개로 구성하십시오.",
        "",
        "지정된 JSON 스키마에 정확히 맞춰 출력하십시오.",
    ]
    return "\n".join(lines)


def repair_prompt(doc: dict, law_report: dict, seo_report: dict) -> str:
    """1차 결과의 문제점을 고치도록 재요청하는 프롬프트."""
    lines = ["직전에 작성한 글에서 아래 문제가 발견되었습니다. 해당 부분만 고쳐 다시 출력하십시오.", ""]

    if law_report.get("findings"):
        lines.append("■ 의료법 위반 소지 (반드시 수정)")
        for f in law_report["findings"]:
            if f["severity"] != medical_law.BLOCK:
                continue
            lines.append(
                f"  - \"{f['matched']}\" ({f['article']}): {f['reason']} → {f['suggestion']}"
            )
        lines.append("")

    if law_report.get("missing_required"):
        lines.append("■ 필수 기재 누락")
        for m in law_report["missing_required"]:
            lines.append(f"  - {m['label']}: {m['hint']}")
        lines.append("")

    fixes = seo_report.get("top_fixes") or []
    if fixes:
        lines.append("■ SEO/AEO/GEO 보완")
        for c in fixes:
            if "NAP" in c["label"]:
                continue  # 원고로 해결할 수 없는 설정 항목
            lines.append(f"  - {c['label']} ({c['detail']}): {c['fix']}")
        lines.append("")

    lines += [
        "지적되지 않은 부분은 그대로 유지하고, 전체 JSON을 다시 완전한 형태로 출력하십시오.",
        "글자 수 제한(MetaTitle "
        f"{seo.META_TITLE_MAX}자, MetaDescription {seo.META_DESC_MAX}자)을 다시 확인하십시오.",
    ]
    return "\n".join(lines)
