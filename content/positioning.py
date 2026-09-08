# -*- coding: utf-8 -*-
"""
포지셔닝 검사 - 본원이 하지 않는 시술과 쓰지 않을 표현을 잡아낸다.

의료법 검사와 분리한 이유
  의료법 검사는 어느 병원에나 공통으로 적용되는 법령 기준입니다.
  이쪽은 "이 병원이 무엇을 하는 곳인가"에 대한 기준이라 병원마다 다릅니다.
  content/services.py만 고치면 다른 진료 분야에도 그대로 씁니다.

다만 심각도는 다릅니다.
  not_performed  하지 않는 시술을 하는 것처럼 쓰면 허위광고(의료법 위반) → block
  avoid_terms    브랜드 표현 문제. 법 위반은 아니지만 포지셔닝을 흐림 → warn
"""

import re

from content import sentences

from content import clinic

BLOCK = "block"
WARN = "warn"

# 다른 병원 얘기를 하는 문맥에서는 '수술' 언급이 정당하다.
# 이런 표현이 근처에 있으면 본원이 한다는 주장으로 보지 않는다.
_THIRD_PARTY = re.compile(
    r"정형외과|일반외과|외과\s*(?:진료|방문|에서)|타\s*병원|다른\s*병원|"
    r"필요한\s*경우|해당하지\s*않|시행하지\s*않|하지\s*않습니다|권유하지\s*않|"
    r"본원(?:은|에서는)\s*[^.\n]{0,30}(?:않|없)|"
    r"아니라|아닌\b|아닙니다|대신"
)
_NEAR = 90  # 앞뒤로 살펴볼 글자 수

# 한국어의 부정은 서술어 바로 뒤에 붙는다. "발톱을 뽑지 않고", "발톱 제거 없이"
# 처럼 표현 직후에 부정이 오면 하지 않는다는 말이므로 위반이 아니다.
# 넓은 창에서 '않'을 찾으면 "절개를 시행합니다. 다른 건 하지 않습니다" 같은
# 문장까지 통과해 버리므로, 바로 뒤 몇 글자만 본다.
_NEGATED_AFTER = re.compile(r"^\s*(?:지|하지|을|를|은|는)?\s*(?:않|말|없)")
_NEGATION_REACH = 14


def _context(text: str, start: int, end: int, width: int = 30) -> str:
    lo, hi = max(0, start - width), min(len(text), end + width)
    return (
        ("…" if lo else "") + text[lo:hi].replace("\n", " ") + ("…" if hi < len(text) else "")
    )


def _negated_right_after(text: str, end: int) -> bool:
    """표현 바로 뒤에 부정이 붙었는지 본다."""
    return bool(_NEGATED_AFTER.match(text[end:end + _NEGATION_REACH]))


def _sentence_around(text: str, start: int, end: int) -> str:
    """판단은 같은 문장 안에서만 한다.

    앞뒤 90자를 통째로 보면 "발톱 제거술을 진행합니다. 다른 병원은 하지
    않습니다." 처럼 뒷문장의 부정까지 끌어와 위반을 놓칩니다. 부정은 같은
    문장 안에 있어야 그 표현을 부정하는 것입니다.
    """
    return sentences.around(text, start, end)


def _third_party_nearby(text: str, start: int, end: int) -> bool:
    """'본원은 하지 않는다'거나 '외과로 가라'는 문맥인지 확인."""
    if _negated_right_after(text, end):
        return True
    return bool(_THIRD_PARTY.search(_sentence_around(text, start, end)))


def _scan_group(text: str, group: list, severity: str, kind: str) -> list:
    """겹치는 구간은 가장 긴 표현 하나만 남긴다.

    '내성발톱 절개'와 '발톱 절개'가 같은 자리에서 둘 다 잡히면
    검수자가 같은 지적을 두 번 읽게 됩니다.
    """
    hits = []
    for entry in group:
        for term in entry["terms"]:
            for m in re.finditer(re.escape(term), text):
                # 본원이 하지 않는다고 명시한 문맥이면 넘어간다.
                if severity == BLOCK and _third_party_nearby(text, m.start(), m.end()):
                    continue
                hits.append((m.start(), m.end(), term, entry))
                break  # 같은 표현은 한 번만 보고

    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    kept = []
    for start, end, term, entry in hits:
        if any(start < k[1] and k[0] < end for k in kept):
            continue
        kept.append((start, end, term, entry))

    return [
        {
            "kind": kind,
            "severity": severity,
            "matched": term,
            "context": _context(text, start, end),
            # 검수자가 그 자리에서 고칠 수 있도록 문장 원문을 함께 싣는다.
            "sentence": sentences.around(text, start, end),
            "reason": entry["reason"],
            "suggestion": entry["instead"],
        }
        for start, end, term, entry in kept
    ]


def review(text: str) -> dict:
    """포지셔닝 관점에서 원고를 점검한다."""
    text = text or ""
    findings = _scan_group(text, clinic.NOT_PERFORMED, BLOCK, "미시행 시술")
    findings += _scan_group(text, clinic.AVOID_TERMS, WARN, "지양 표현")

    blocks = [f for f in findings if f["severity"] == BLOCK]
    warns = [f for f in findings if f["severity"] == WARN]

    if not findings:
        summary = "포지셔닝 문제 없음"
    else:
        parts = []
        if blocks:
            parts.append(f"미시행 시술 언급 {len(blocks)}건")
        if warns:
            parts.append(f"지양 표현 {len(warns)}건")
        summary = " · ".join(parts)

    return {
        "passed": not blocks,
        "block_count": len(blocks),
        "warn_count": len(warns),
        "findings": findings,
        "summary": summary,
    }


def rules_for_prompt() -> str:
    """생성 프롬프트에 넣을 지침."""
    lines = ["본원에서 시행하지 않는 시술 (본원이 하는 것처럼 쓰면 허위광고):"]
    for entry in clinic.NOT_PERFORMED:
        lines.append(f"  - {', '.join(entry['terms'])} → {entry['instead']}")
    lines.append("")
    lines.append("쓰지 않을 표현:")
    for entry in clinic.AVOID_TERMS:
        lines.append(f"  - {', '.join(entry['terms'])} → {entry['instead']}")
    lines.append("")
    lines.append(
        "수술적 처치가 필요한 상태를 설명할 때는 '외과 진료가 필요할 수 있습니다'처럼 "
        "다른 진료과를 안내하는 형태로만 쓰고, 본원이 그 시술을 하는 것처럼 쓰지 마십시오."
    )
    return "\n".join(lines)
