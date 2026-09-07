# -*- coding: utf-8 -*-
"""
Claude API 기반 콘텐츠 생성기.

파이프라인
  1) 생성      Structured Outputs로 고정 스키마 JSON을 받는다
  2) 후처리    슬러그·카테고리·해시태그 정규화, 글자수 하드컷 확인
  3) 의료법 검사
  4) SEO/AEO/GEO 채점
  5) 자동 교정  위반 또는 점수 미달이면 지적사항을 담아 재요청 (기본 1회)

시스템 프롬프트는 매 요청 동일하므로 프롬프트 캐싱을 걸어 비용을 줄입니다.
"""

import json
import logging
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from content import (
    medical_law,
    positioning,
    prompts,
    seo,
    slug as slug_mod,
    taxonomy,
)

logger = logging.getLogger(__name__)

MODEL = os.getenv("CONTENT_MODEL", "claude-opus-5")
MAX_TOKENS = int(os.getenv("CONTENT_MAX_TOKENS", "32000"))
EFFORT = os.getenv("CONTENT_EFFORT", "high")

# 자동 교정을 시도할 최소 점수. 이 아래면 한 번 더 고쳐 쓴다.
REPAIR_SCORE_THRESHOLD = int(os.getenv("CONTENT_MIN_SCORE", "80"))
MAX_REPAIRS = int(os.getenv("CONTENT_MAX_REPAIRS", "2"))
# 의료법 위반이 남아 있으면 점수와 무관하게 여기까지 더 시도한다.
MAX_LAW_RETRIES = int(os.getenv("CONTENT_MAX_LAW_RETRIES", "3"))


class GenerationError(RuntimeError):
    pass


# 화면이 미리 단계 목록을 그릴 수 있도록 순서를 고정해 둔다.
STAGES = [
    ("parse", "제목 분석"),
    ("draft", "원고 작성"),
    ("check", "의료법·포지셔닝 검사"),
    ("repair", "자동 교정"),
    ("save", "저장"),
]


def _noop(*_args, **_kwargs):
    pass


NO_KEY_MESSAGE = (
    "Claude API 키가 없어 원고를 생성할 수 없습니다.\n"
    "프로젝트 폴더의 .env 파일을 메모장으로 열어 아래 한 줄을 채운 뒤 저장하고,\n"
    "서버 창을 닫았다가 다시 켜 주세요.\n\n"
    "    ANTHROPIC_API_KEY=sk-ant-...\n\n"
    "키는 console.anthropic.com 에서 발급합니다.\n"
    "(원고 검사와 미리보기는 키 없이도 그대로 쓸 수 있습니다.)"
)


def has_api_key() -> bool:
    """생성을 시도하기 전에 키가 있는지 본다."""
    return bool(
        os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("ANTHROPIC_AUTH_TOKEN")
    )


def _is_auth_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "authentication" in text
        or "api_key" in text
        or "api key" in text
        or "unauthorized" in text
        or "401" in text
    )


def _client():
    try:
        import anthropic
    except ImportError as exc:
        raise GenerationError(
            "anthropic 패키지가 없습니다. pip install -r requirements.txt 를 실행하세요."
        ) from exc

    if not has_api_key():
        raise GenerationError(NO_KEY_MESSAGE)

    try:
        return anthropic.Anthropic()
    except Exception as exc:
        if _is_auth_error(exc):
            raise GenerationError(NO_KEY_MESSAGE) from exc
        raise GenerationError(f"Claude 클라이언트를 만들지 못했습니다: {exc}") from exc


def _call(messages: list) -> dict:
    """Claude를 호출해 스키마에 맞는 JSON을 받는다."""
    client = _client()
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": prompts.SYSTEM,
                    # 시스템 프롬프트는 요청마다 동일하므로 캐시 대상으로 지정
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            thinking={"type": "adaptive"},
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": prompts.OUTPUT_SCHEMA},
            },
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
    except Exception as exc:
        if _is_auth_error(exc):
            raise GenerationError(NO_KEY_MESSAGE) from exc
        raise GenerationError(f"Claude 호출 실패: {exc}") from exc

    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise GenerationError(
            f"모델이 생성을 거부했습니다: {getattr(detail, 'explanation', '사유 미상')}"
        )

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        raise GenerationError("모델 응답에서 본문을 찾지 못했습니다.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GenerationError(f"JSON 파싱 실패: {exc}") from exc

    usage = response.usage
    data["_usage"] = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cache_write": getattr(usage, "cache_creation_input_tokens", 0) or 0,
    }
    return data


# ── 후처리 ───────────────────────────────────────────────────────────
def _normalize(doc: dict, category: str, primary: str) -> dict:
    """CMS 발행에 필요한 필드를 채우고 하드 리밋을 강제한다."""
    doc["category"] = category
    doc["primary_keyword"] = primary

    # 포스트 URL은 제목에서 기계적으로 생성한다(모델에게 맡기지 않음).
    doc["post_url"] = slug_mod.slugify(doc.get("h1", ""))

    # CMS 하드 리밋. 넘치면 잘라서 저장 사고를 막고, 검사 리포트에 남긴다.
    doc["meta_title_overflow"] = max(0, len(doc.get("meta_title", "")) - seo.META_TITLE_MAX)
    doc["meta_desc_overflow"] = max(0, len(doc.get("meta_description", "")) - seo.META_DESC_MAX)

    # 해시태그 정규화: '#' 보정, 공백 제거, 중복 제거
    seen, tags = set(), []
    for t in doc.get("hashtags", []) or []:
        t = t.strip().replace(" ", "")
        if not t:
            continue
        if not t.startswith("#"):
            t = "#" + t
        if t not in seen:
            seen.add(t)
            tags.append(t)
    doc["hashtags"] = tags

    # 표 정합성: 행 길이를 헤더에 맞춘다.
    for section in doc.get("sections", []) or []:
        for block in section.get("blocks", []) or []:
            if block.get("type") != "table":
                continue
            width = len(block.get("headers", []) or [])
            fixed = []
            for row in block.get("rows", []) or []:
                row = list(row)[:width] + [""] * max(0, width - len(row))
                fixed.append(row)
            block["rows"] = fixed

    doc["published_url"] = taxonomy.post_url(category, doc["post_url"])
    return doc


def _full_text(doc: dict) -> str:
    """의료법 검사 대상 텍스트(메타·해시태그·썸네일 문구 포함)."""
    parts = [
        doc.get("h1", ""),
        doc.get("meta_title", ""),
        doc.get("meta_description", ""),
        doc.get("thumbnail_copy", ""),
        doc.get("intro", ""),
        doc.get("answer_capsule", ""),
        doc.get("closing", ""),
        " ".join(doc.get("hashtags", []) or []),
    ]
    parts += doc.get("key_takeaways", []) or []
    for s in doc.get("sections", []) or []:
        parts += [s.get("h2", ""), s.get("answer", "")]
        for b in s.get("blocks", []) or []:
            parts.append(b.get("text", ""))
            parts += b.get("items", []) or []
            parts += b.get("headers", []) or []
            for row in b.get("rows", []) or []:
                parts += [str(c) for c in row]
    for f in doc.get("faq", []) or []:
        parts += [f.get("q", ""), f.get("a", "")]
    return "\n".join(p for p in parts if p)


def evaluate(doc: dict) -> dict:
    """생성 결과를 검사한다(의료법 + SEO/AEO/GEO)."""
    text = _full_text(doc)
    law = medical_law.review(text)
    pos = positioning.review(text)
    audit = seo.audit(doc, doc.get("primary_keyword", ""))
    return {"law": law, "positioning": pos, "seo": audit}


def _needs_repair(reports: dict) -> bool:
    if reports["law"]["block_count"] > 0:
        return True
    if reports["law"]["missing_required"]:
        return True
    # 하지 않는 시술을 언급했거나 지양 표현이 남아 있으면 다시 쓴다.
    if reports["positioning"]["block_count"] > 0:
        return True
    if reports["positioning"]["warn_count"] > 0:
        return True
    if reports["seo"]["scores"]["total"] < REPAIR_SCORE_THRESHOLD:
        return True
    return False


def _hard_issues(reports: dict) -> int:
    """반드시 없애야 하는 문제의 개수 - 의료법 위반, 필수 누락, 미시행 시술."""
    return (
        reports["law"]["block_count"]
        + len(reports["law"]["missing_required"])
        + reports["positioning"]["block_count"]
    )


# ── 진입점 ───────────────────────────────────────────────────────────
def generate(
    category: str,
    primary_keyword: str,
    topic: str,
    angle: str = "",
    audience: str = "",
    extra_notes: str = "",
    auto_repair: bool = True,
    on_progress=None,
) -> dict:
    """글 1편을 생성하고 검사까지 마쳐 돌려준다.

    on_progress(stage, state, detail) 를 넘기면 진행 상황을 알려 준다.
    state 는 "start" / "done" 중 하나다.
    """
    progress = on_progress or _noop

    user_prompt = prompts.build_user_prompt(
        category, primary_keyword, topic, angle, audience, extra_notes
    )
    messages = [{"role": "user", "content": user_prompt}]

    logger.info("생성 시작: %s / %s", category, primary_keyword)
    progress("draft", "start", "Claude가 본문을 쓰고 있습니다")
    doc = _call(messages)
    doc = _normalize(doc, category, primary_keyword)
    progress("draft", "done", f"{len(_full_text(doc))}자 초안 완성")

    progress("check", "start", "")
    reports = evaluate(doc)
    progress("check", "done", _check_summary(reports))

    attempts = 1
    usage_total = dict(doc.get("_usage", {}))

    while auto_repair and _needs_repair(reports):
        law_dirty = bool(_hard_issues(reports))
        # 의료법 문제는 점수 문제보다 더 오래 물고 늘어진다.
        limit = MAX_LAW_RETRIES if law_dirty else MAX_REPAIRS
        if attempts > limit:
            break

        logger.info(
            "자동 교정 %d회차 (위반 %d건 / 필수누락 %d건 / 점수 %d)",
            attempts,
            reports["law"]["block_count"],
            len(reports["law"]["missing_required"]),
            reports["seo"]["scores"]["total"],
        )
        progress(
            "repair", "start",
            f"{attempts}차 — {_check_summary(reports)}",
        )
        messages = messages + [
            {"role": "assistant", "content": json.dumps(
                {k: v for k, v in doc.items() if not k.startswith("_")},
                ensure_ascii=False,
            )},
            {"role": "user", "content": prompts.repair_prompt(
                doc, reports["law"], reports["seo"], reports["positioning"]
            )},
        ]
        repaired = _call(messages)
        repaired = _normalize(repaired, category, primary_keyword)
        new_reports = evaluate(repaired)

        for k, v in repaired.get("_usage", {}).items():
            usage_total[k] = usage_total.get(k, 0) + v

        old_law = _hard_issues(reports)
        new_law = _hard_issues(new_reports)

        if law_dirty:
            # 의료법을 고치는 중에는 위반 건수만 본다.
            # 점수가 조금 내려가도 위반이 줄면 그쪽이 낫다.
            better = new_law < old_law or (
                new_law == 0
                and new_reports["seo"]["scores"]["total"]
                >= reports["seo"]["scores"]["total"] - 5
            )
        else:
            better = (
                new_law <= old_law
                and new_reports["seo"]["scores"]["total"]
                >= reports["seo"]["scores"]["total"]
            )

        if better or new_law < old_law:
            # 점수가 조금 나빠져도 위반이 줄면 그쪽을 택한다.
            doc, reports = repaired, new_reports
            progress("repair", "done", _check_summary(reports))
        else:
            logger.info("교정 결과가 개선되지 않아 이전 버전을 유지합니다.")
            progress("repair", "done", "더 나아지지 않아 이전 버전을 유지합니다")
            break
        attempts += 1

    if attempts == 1:
        progress("repair", "skip", "고칠 것이 없었습니다")

    doc["_usage"] = usage_total
    doc["_attempts"] = attempts
    return {"doc": doc, "reports": reports}


def _check_summary(reports: dict) -> str:
    """검사 결과를 한 줄로. 화면에 그대로 띄운다."""
    law, pos = reports["law"], reports["positioning"]
    hard = law["block_count"] + len(law["missing_required"]) + pos["block_count"]
    score = reports["seo"]["scores"]["total"]
    if hard:
        return f"고칠 곳 {hard}건 · 점수 {score}"
    return f"통과 · 점수 {score}"


def generate_from_title(title: str, auto_repair: bool = True, on_progress=None) -> dict:
    """제목 하나로 글을 만든다. 카테고리·주키워드는 제목에서 추론한다."""
    from content import title_parser

    progress = on_progress or _noop
    progress("parse", "start", "")
    parsed = title_parser.parse(title)
    progress("parse", "done", title_parser.describe(parsed))

    notes = [
        f"주어진 제목을 그대로 쓰지 말고, 이 주제를 다루되 h1은 SEO 규칙"
        f"(주키워드 '{parsed['primary_keyword']}'와 지역명 포함, 25~60자)에 맞게 다듬으십시오.",
        f"원래 제목: {parsed['title']}",
    ]
    if not parsed["has_region"]:
        notes.append(
            "제목에 지역 신호가 없습니다. h1과 본문에 '송도' 또는 '인천'을 "
            "자연스럽게 넣어 지역 검색에 걸리게 하십시오."
        )

    result = generate(
        category=parsed["category"],
        primary_keyword=parsed["primary_keyword"],
        topic=parsed["topic"],
        extra_notes="\n".join(notes),
        auto_repair=auto_repair,
        on_progress=on_progress,
    )
    result["parsed"] = parsed
    return result


def estimate_cost(usage: dict) -> float:
    """대략적인 비용(USD). Claude Opus 5 기준 $5/$25 per 1M tokens."""
    if not usage:
        return 0.0
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cached = usage.get("cache_read", 0)
    return round(inp / 1e6 * 5 + cached / 1e6 * 0.5 + out / 1e6 * 25, 4)
