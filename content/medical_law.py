# -*- coding: utf-8 -*-
"""
의료광고 사전 점검기 - 의료법 제56조(의료광고의 금지 등) 기준.

생성된 문구를 발행 전에 기계적으로 훑어 위험 표현을 잡아냅니다.
법률 자문을 대체하지 않으며, 최종 판단과 의료광고 심의는 반드시 사람이 합니다.
목적은 '심의에서 걸릴 표현이 초안에 남지 않게' 하는 것입니다.

근거 조문 요약 (의료법 제56조 제2항 각 호):
  2호  치료효과를 보장하는 등 소비자를 현혹할 우려가 있는 내용
  3호  다른 의료인·의료기관을 비방하는 내용
  5호  의료인의 기능·진료방법과 관련해 심각한 부작용 등 중요정보를 누락한 광고
  6호  객관적 사실을 과장하는 내용
  7호  법적 근거가 없는 자격·명칭을 표방하는 내용
  8호  신문·방송 기사나 전문가 의견 형태로 표현되는 광고
  12호 환자의 치료경험담 등 소비자로 하여금 치료효과를 오인하게 할 우려가 있는 내용
  13호 심의받지 않았거나 심의 내용과 다른 광고
  14호 소비자를 속이거나 비급여 진료비용을 할인·면제해 환자를 유인하는 내용
"""

import re

BLOCK = "block"   # 발행 전 반드시 수정
WARN = "warn"     # 맥락에 따라 위반 소지, 검토 필요
INFO = "info"     # 표현 다듬기 권고


# ── 규칙 정의 ────────────────────────────────────────────────────────
# pattern    : 탐지 정규식
# severity   : block / warn / info
# article    : 근거 조항
# reason     : 왜 문제인지
# suggestion : 대체 표현 방향
RULES = [
    # ── 2호: 치료효과 보장·단정 ──────────────────────────────────
    {
        "id": "guarantee_cure",
        "pattern": r"완치\s*(?:됩니다|됨|가능|보장|율|를\s*보장)|100\s*%|100퍼센트|재발\s*(?:없|제로|0)",
        "severity": BLOCK,
        "article": "제56조 제2항 제2호",
        "reason": "치료효과를 보장·단정하는 표현은 소비자 현혹 광고로 금지됩니다.",
        "suggestion": "'치료 경과에는 개인차가 있습니다' 등 결과를 단정하지 않는 서술로 바꾸세요.",
    },
    {
        "id": "guarantee_verb",
        "pattern": r"(?:반드시|무조건|틀림없이|확실히)\s*(?:낫|좋아|개선|호전|해결|사라)",
        "severity": BLOCK,
        "article": "제56조 제2항 제2호",
        "reason": "결과를 단정하는 부사 표현은 치료효과 보장 광고에 해당합니다.",
        "suggestion": "'개선을 기대할 수 있습니다', '경과를 관찰합니다' 등으로 완화하세요.",
    },
    {
        "id": "guarantee_noun",
        "pattern": r"(?:효과|결과|완치)\s*(?:보장|확실|만점)|보장\s*(?:해\s*드립니다|합니다|제)",
        "severity": BLOCK,
        "article": "제56조 제2항 제2호",
        "reason": "효과 보장 문구는 금지 대상입니다.",
        "suggestion": "보장 표현을 삭제하고 치료 과정 설명으로 대체하세요.",
    },
    {
        "id": "pain_free_absolute",
        "pattern": r"(?<!거의 )(?:무통|통증\s*(?:제로|없습니다|없어요|없음))|부작용\s*(?:없|제로|0)",
        "severity": BLOCK,
        "article": "제56조 제2항 제2호·제6호",
        "reason": "통증·부작용이 전혀 없다는 단정은 객관적 근거가 없는 과장 광고입니다.",
        "suggestion": "'통증이 적은 편입니다', '개인에 따라 열감이 느껴질 수 있습니다'로 서술하세요.",
    },

    # ── 6호: 과장 / 최상급 / 배타성 ──────────────────────────────
    {
        "id": "superlative",
        "pattern": r"최고|최상|최상급|가장\s*(?:좋은|뛰어난|우수한|효과적)|넘버\s*원|No\.?\s*1|1위|톱\s*클래스",
        "severity": BLOCK,
        "article": "제56조 제2항 제6호",
        "reason": "객관적으로 입증되지 않은 최상급 표현은 과장 광고입니다.",
        "suggestion": "최상급을 빼고 '어떤 절차를 어떻게 진행하는지'를 구체적으로 쓰세요.",
    },
    {
        "id": "exclusivity",
        "pattern": r"유일(?:한|하게)?|국내\s*(?:유일|최초|최대)|(?:지역|인천|송도)\s*유일|독보적|타의\s*추종",
        "severity": BLOCK,
        "article": "제56조 제2항 제6호",
        "reason": "배타적 표현은 객관적 입증이 어려워 과장 광고로 판단됩니다.",
        "suggestion": "'본원에서는 ~를 시행합니다'처럼 사실 서술로 바꾸세요.",
    },
    {
        "id": "first_ever",
        "pattern": r"최초\s*(?:도입|시행|개발)|국내\s*최초|세계\s*최초",
        "severity": WARN,
        "article": "제56조 제2항 제6호",
        "reason": "'최초' 주장은 객관적 근거 자료가 없으면 과장 광고가 됩니다.",
        "suggestion": "공신력 있는 근거가 없다면 삭제하세요.",
    },
    {
        "id": "authority_claim",
        "pattern": r"권위자|명의|대가(?:로 손꼽|로 유명)|손꼽히는|정평이\s*나",
        "severity": BLOCK,
        "article": "제56조 제2항 제6호",
        "reason": "의료인의 권위를 과장하는 표현은 금지됩니다.",
        "suggestion": "경력·자격은 사실만 담백하게 기재하세요.",
    },
    {
        "id": "fabricated_stats",
        "pattern": r"만족도\s*\d{2,3}\s*%|성공률\s*\d{1,3}\s*%|치료율\s*\d{1,3}\s*%|\d{1,3}\s*%\s*(?:완치|개선\s*보장)",
        "severity": BLOCK,
        "article": "제56조 제2항 제2호·제6호",
        "reason": "출처 없는 성공률·만족도 수치는 소비자 오인을 유발합니다.",
        "suggestion": "출처를 제시할 수 없다면 수치를 삭제하세요.",
    },

    # ── 7호: 법적 근거 없는 명칭 ─────────────────────────────────
    {
        "id": "specialty_hospital",
        "pattern": r"전문병원|특화병원|전문\s*센터|전문의\s*병원",
        "severity": BLOCK,
        "article": "제56조 제2항 제7호",
        "reason": "보건복지부 지정 전문병원이 아닌 기관은 '전문병원' 명칭을 쓸 수 없습니다.",
        "suggestion": "'문제성발톱클리닉', '중점 진료' 등 지정 명칭이 아닌 표현을 쓰세요.",
    },
    {
        "id": "unofficial_title",
        "pattern": r"공식\s*지정(?:병원|기관)|인증\s*(?:병원|의료기관)|보건복지부\s*(?:인증|지정)",
        "severity": WARN,
        "article": "제56조 제2항 제7호·제13호",
        "reason": "실제 지정·인증 사실이 없으면 허위 표시가 됩니다.",
        "suggestion": "지정·인증 사실과 근거를 확인할 수 없으면 삭제하세요.",
    },

    # ── 12호: 치료경험담 / 후기 ──────────────────────────────────
    {
        "id": "testimonial",
        "pattern": r"환자\s*(?:후기|리뷰|경험담|체험담)|치료\s*(?:후기|경험담)|실제\s*후기|생생한\s*후기",
        "severity": BLOCK,
        "article": "제56조 제2항 제12호",
        "reason": "환자 치료경험담은 치료효과 오인 우려로 광고에 사용할 수 없습니다.",
        "suggestion": "후기 대신 치료 원리와 절차를 의학적으로 설명하세요.",
    },
    {
        "id": "testimonial_quote",
        "pattern": r"[\"“'][^\"”']{4,60}(?:나았|좋아졌|깨끗해졌|만족)[^\"”']{0,20}[\"”']",
        "severity": WARN,
        "article": "제56조 제2항 제12호",
        "reason": "인용 형식의 체험 진술은 치료경험담으로 해석될 수 있습니다.",
        "suggestion": "환자 발화 인용을 삭제하거나 일반적 증상 설명으로 바꾸세요.",
    },

    # ── 14호: 환자 유인 (비급여 할인·면제·이벤트) ─────────────────
    {
        "id": "price_inducement",
        "pattern": r"할인|무료(?!\s*상담\s*전화)|이벤트\s*가|특가|반값|공짜|사은품|경품|\d+\s*\+\s*\d+\s*(?:이벤트|행사)|선착순",
        "severity": BLOCK,
        "article": "제56조 제2항 제14호",
        "reason": "비급여 진료비 할인·면제나 금품 제공은 환자 유인 행위로 금지됩니다.",
        "suggestion": "가격 유인 문구를 모두 삭제하고 진료 내용 안내만 남기세요.",
    },
    {
        "id": "price_disclosure",
        "pattern": r"\d{1,3}\s*만\s*원|\d{2,3},\d{3}\s*원|비용은?\s*\d",
        "severity": WARN,
        "article": "제56조 제2항 제14호",
        "reason": "구체적 진료비 표기는 유인성 판단을 받을 수 있어 신중해야 합니다.",
        "suggestion": "'비용은 상태에 따라 달라 진료 후 안내드립니다'로 대체하세요.",
    },
    {
        "id": "insurance_claim",
        "pattern": r"실(?:손|비)\s*(?:보험\s*)?(?:청구|적용)\s*(?:가|이|를|은|는)?\s*가능",
        "severity": WARN,
        "article": "제56조 제2항 제2호·제14호",
        "reason": "실손보험 적용을 단정하면 오인·유인 소지가 있습니다.",
        "suggestion": "'가입하신 보험 약관에 따라 다르므로 보험사에 확인이 필요합니다'를 함께 쓰세요.",
    },

    # ── 3호: 비교 / 비방 ────────────────────────────────────────
    {
        "id": "comparison",
        "pattern": r"타\s*(?:병원|의원|기관)(?:보다|와\s*달리|과\s*달리)|다른\s*병원(?:보다|과\s*달리|와\s*달리)|일반\s*병원(?:과|보다)\s*(?:다르|달리)",
        "severity": BLOCK,
        "article": "제56조 제2항 제3호",
        "reason": "다른 의료기관과의 비교·비방은 금지됩니다.",
        "suggestion": "타 기관 언급 없이 본원 진료 절차만 설명하세요.",
    },

    # ── 8호: 기사형 광고 / 전문가 의견 형식 ───────────────────────
    {
        "id": "news_style",
        "pattern": r"기자|취재(?:진|결과)|보도(?:에\s*따르면|자료)|인터뷰\s*에서\s*밝[혔히]|[가-힣]{2,4}\s*기자",
        "severity": WARN,
        "article": "제56조 제2항 제8호",
        "reason": "신문·방송 기사 형식을 빌린 광고는 금지됩니다.",
        "suggestion": "기사체 표현을 없애고 병원 안내 문체로 바꾸세요.",
    },
    {
        "id": "media_endorsement",
        "pattern": r"방송\s*출연|TV\s*출연|[A-Z]{2,4}\s*방송에?\s*(?:소개|출연)|매스컴",
        "severity": WARN,
        "article": "제56조 제2항 제8호·제13호",
        "reason": "방송 출연 이력을 광고에 활용하면 보증·추천 광고로 볼 수 있습니다.",
        "suggestion": "삭제하거나 사실 확인 가능한 범위로 한정하세요.",
    },

    # ── 13호: 인증·추천·상장 표시 ────────────────────────────────
    {
        "id": "endorsement",
        "pattern": r"수상|감사장|표창|공식\s*(?:인증|후원|파트너)|추천\s*(?:병원|1위)|보증",
        "severity": WARN,
        "article": "제56조 제2항 제13호",
        "reason": "상장·감사장·추천 표시는 광고에 사용할 수 없습니다.",
        "suggestion": "삭제하세요.",
    },

    # ── 4호: 수술 장면 등 직접적 시술 노출 ──────────────────────
    {
        "id": "procedure_visual",
        "pattern": r"시술\s*(?:장면|영상)|수술\s*장면|전\s*후\s*사진|비포\s*애프터|before\s*&?\s*after",
        "severity": WARN,
        "article": "제56조 제2항 제4호·제5호",
        "reason": "시술 장면이나 전후 사진은 노출 방식과 중요정보 기재 여부에 따라 제한됩니다.",
        "suggestion": "이미지 사용 시 부작용·주의사항을 반드시 함께 표기하고 심의 기준을 확인하세요.",
    },

    # ── 기타: 오인 유발 표현 ─────────────────────────────────────
    {
        "id": "safe_absolute",
        "pattern": r"(?:절대|전혀)\s*안전|안전(?:성)?\s*(?:보장|100)|위험\s*(?:제로|없)",
        "severity": BLOCK,
        "article": "제56조 제2항 제2호·제6호",
        "reason": "절대적 안전성 주장은 과장 광고입니다.",
        "suggestion": "'시술 전 상태를 확인해 진행합니다'처럼 절차 중심으로 서술하세요.",
    },
    {
        # 실제 발행 원고에서 자주 나오는 형태:
        # "소아, 노약자, 임신부 분들도 부담 없이 치료받으실 수 있습니다"
        "id": "vulnerable_group_safety",
        "pattern": r"(?:임(?:신|산)부|수유부|소아|노약자|고령\s*환자|기저질환자)[^.\n]{0,40}"
                   r"(?:부담\s*없이|안전(?:하게|합니다)|걱정\s*없이|문제\s*없)",
        "severity": WARN,
        "article": "제56조 제2항 제2호·제6호",
        "reason": "임신부·소아 등 특수 대상군에 대한 안전성 단정은 근거 없이 쓰면 "
                  "소비자를 오인하게 할 수 있습니다.",
        "suggestion": "'상태에 따라 시행 여부를 진료로 판단합니다'처럼 개별 판단이 "
                      "필요하다는 점을 함께 쓰세요.",
    },
    {
        "id": "low_pain_claim",
        "pattern": r"통증(?:이|은)?\s*거의\s*없|아프지\s*않(?:습니다|아요)|마취\s*없이",
        "severity": INFO,
        "article": "제56조 제2항 제5호",
        "reason": "통증이 적다는 서술 자체는 가능하나, 개인차와 이상반응을 함께 "
                  "적지 않으면 중요정보 누락으로 볼 수 있습니다.",
        "suggestion": "'통증에는 개인차가 있습니다'를 같은 문단에 덧붙이세요.",
    },
    {
        "id": "urgency_push",
        "pattern": r"지금\s*(?:바로\s*)?(?:전화|예약|신청)|서두르|마감\s*임박|기회를\s*놓치",
        "severity": WARN,
        "article": "제56조 제2항 제14호",
        "reason": "즉시 행동을 압박하는 문구는 유인성으로 해석될 수 있습니다.",
        "suggestion": "'궁금한 점은 진료 시 문의해 주세요' 정도로 낮추세요.",
    },
    {
        "id": "self_diagnosis_push",
        "pattern": r"집에서\s*(?:직접\s*)?(?:치료|제거|뽑)|스스로\s*(?:잘라|제거|뽑)",
        "severity": WARN,
        "article": "환자 안전",
        "reason": "자가 처치를 권유하는 것으로 읽히면 안전상 문제가 됩니다.",
        "suggestion": "자가 처치의 위험을 알리고 진료를 권하는 문장으로 바꾸세요.",
    },
]

_COMPILED = [(r, re.compile(r["pattern"])) for r in RULES]


# ── 필수 기재 사항 ───────────────────────────────────────────────────
# 제56조 제2항 제5호: 심각한 부작용 등 중요정보 누락 금지
REQUIRED_TOPICS = [
    {
        "id": "side_effects",
        "label": "부작용 안내",
        "pattern": r"부작용|열감|홍반|화끈거림|이상반응",
        "hint": "가열성 레이저의 열감·홍반 등 발생 가능한 이상반응을 명시해야 합니다.",
    },
    {
        "id": "individual_variation",
        "label": "치료 결과의 개인차",
        "pattern": r"개인(?:마다\s*)?차|개인에\s*따라|차이가?\s*있",
        "hint": "치료 기간·경과에 개인차가 있다는 점을 명시해야 합니다.",
    },
    {
        "id": "consult_notice",
        "label": "진료 상담 안내",
        "pattern": r"진료(?:를 통해|후)|상담(?:을 통해|이 필요)|의료진(?:과|의)\s*(?:상담|진료|판단)",
        "hint": "정확한 진단·치료는 의료진 진료로 결정된다는 안내가 필요합니다.",
    },
]

_COMPILED_REQUIRED = [(t, re.compile(t["pattern"])) for t in REQUIRED_TOPICS]


def _context(text: str, start: int, end: int, width: int = 28) -> str:
    lo = max(0, start - width)
    hi = min(len(text), end + width)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{text[lo:hi]}{suffix}".replace("\n", " ")


def scan(text: str) -> list:
    """텍스트에서 위험 표현을 찾아 발견 목록을 돌려준다.

    같은 위치를 여러 규칙이 잡는 경우(예: "완치 보장"이 효과보장·완치단정에 모두 해당)
    가장 심각한 규칙 하나만 남깁니다. 같은 지적이 두 번 뜨면 검수자가 놓치기 쉽습니다.
    """
    order = {BLOCK: 0, WARN: 1, INFO: 2}
    if not text:
        return []

    by_span = {}
    for rule, regex in _COMPILED:
        for m in regex.finditer(text):
            finding = {
                "rule_id": rule["id"],
                "severity": rule["severity"],
                "article": rule["article"],
                "matched": m.group(0),
                "context": _context(text, m.start(), m.end()),
                "reason": rule["reason"],
                "suggestion": rule["suggestion"],
            }
            # 겹치는 구간은 더 심각한 쪽을, 같은 심각도면 더 긴 매치를 남긴다.
            key = None
            for span in list(by_span):
                if m.start() < span[1] and span[0] < m.end():
                    key = span
                    break
            if key is None:
                by_span[(m.start(), m.end())] = finding
                continue
            kept = by_span[key]
            challenger_better = (
                order[finding["severity"]],
                -len(finding["matched"]),
            ) < (order[kept["severity"]], -len(kept["matched"]))
            if challenger_better:
                del by_span[key]
                by_span[(min(key[0], m.start()), max(key[1], m.end()))] = finding

    findings = list(by_span.values())
    findings.sort(key=lambda f: (order[f["severity"]], f["rule_id"]))
    return findings


def check_required(text: str) -> list:
    """필수 기재 사항이 빠졌는지 확인한다."""
    missing = []
    for topic, regex in _COMPILED_REQUIRED:
        if not regex.search(text or ""):
            missing.append(
                {
                    "topic_id": topic["id"],
                    "label": topic["label"],
                    "hint": topic["hint"],
                }
            )
    return missing


def review(text: str) -> dict:
    """발행 가능 여부까지 포함한 종합 판정."""
    findings = scan(text)
    missing = check_required(text)
    blocks = [f for f in findings if f["severity"] == BLOCK]
    warns = [f for f in findings if f["severity"] == WARN]
    return {
        "passed": not blocks and not missing,
        "block_count": len(blocks),
        "warn_count": len(warns),
        "findings": findings,
        "missing_required": missing,
        "summary": _summary(blocks, warns, missing),
    }


def _summary(blocks, warns, missing) -> str:
    if not blocks and not missing and not warns:
        return "자동 점검에서 걸린 표현이 없습니다. 최종 확인 후 심의 절차를 진행하세요."
    parts = []
    if blocks:
        parts.append(f"수정 필요 {len(blocks)}건")
    if missing:
        parts.append(f"필수 기재 누락 {len(missing)}건")
    if warns:
        parts.append(f"검토 권고 {len(warns)}건")
    return " · ".join(parts)


def rules_for_prompt() -> str:
    """생성 프롬프트에 주입할 금지 표현 지침."""
    lines = []
    for r in RULES:
        if r["severity"] == BLOCK:
            lines.append(f"  - [{r['article']}] {r['reason']} → {r['suggestion']}")
    required = "\n".join(f"  - {t['label']}: {t['hint']}" for t in REQUIRED_TOPICS)
    return (
        "절대 사용 금지 (의료법 제56조):\n"
        + "\n".join(lines)
        + "\n\n반드시 포함해야 하는 내용:\n"
        + required
    )
