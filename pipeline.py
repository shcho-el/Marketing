# -*- coding: utf-8 -*-
"""
제목 → 원고 → 썸네일 → CMS 업로드까지 한 번에.

  python main.py auto "송도 발톱무좀 병원 선택 기준"
  python main.py auto titles.txt          # 한 줄에 제목 하나씩, 여러 편

단계
  1. 제목에서 카테고리·주키워드 추론
  2. 생성 (의료법 위반이 남으면 통과할 때까지 다시 씀)
  3. 하드 게이트 - 의료법을 통과하지 못하면 업로드하지 않고 사유를 남김
  4. 썸네일 생성 (사진 배경 + 제목)
  5. CMS 업로드

3번은 설정으로 끌 수 없습니다. 자동화의 값어치는 "잘못된 글을 안 올리는 것"에 있고,
그 판단을 사람이 매번 하지 않아도 되게 만드는 것이 이 파이프라인의 목적입니다.
"""

import logging
import time

from content import generator, renderer, store, title_parser
from publisher import publish as cms
from publisher import thumbnail

logger = logging.getLogger(__name__)


def run_one(
    title: str,
    expose: bool = True,
    dry_run: bool = False,
    upload: bool = True,
    layout: str = "",
) -> dict:
    """제목 하나를 글로 만들어 업로드까지 진행한다."""
    started = time.time()
    outcome = {
        "title": title,
        "uploaded": False,
        "exposed": False,
        "blocked": False,
        "error": "",
    }

    # 1~2. 추론 + 생성
    try:
        result = generator.generate_from_title(title)
    except Exception as exc:
        outcome["error"] = f"생성 실패: {exc}"
        logger.exception("생성 실패: %s", title)
        return outcome

    doc, reports = result["doc"], result["reports"]
    parsed = result["parsed"]

    post_id = store.save(doc, reports, parsed["topic"])
    outcome.update(
        {
            "post_id": post_id,
            "parsed": parsed,
            "h1": doc.get("h1", ""),
            "post_url": doc.get("post_url", ""),
            "scores": reports["seo"]["scores"],
            "law": reports["law"],
            "attempts": doc.get("_attempts", 1),
            "cost": generator.estimate_cost(doc.get("_usage", {})),
        }
    )

    outcome["positioning"] = reports["positioning"]

    # 3. 하드 게이트 - 의료법 위반이나 미시행 시술 언급이 남으면 올리지 않는다
    gate_reasons = []
    if not reports["law"]["passed"]:
        gate_reasons.append(f"의료법 {reports['law']['summary']}")
    if not reports["positioning"]["passed"]:
        gate_reasons.append(
            f"하지 않는 시술 언급 {reports['positioning']['block_count']}건"
        )

    if gate_reasons:
        outcome["blocked"] = True
        outcome["error"] = (
            f"검사 미통과 - {' · '.join(gate_reasons)}. "
            "재작성을 반복했지만 해결되지 않아 업로드하지 않았습니다."
        )
        store.set_status(post_id, "blocked")
        logger.warning("업로드 차단: %s (%s)", title, reports["law"]["summary"])
        outcome["elapsed"] = round(time.time() - started, 1)
        return outcome

    if not upload:
        store.set_status(post_id, "draft")
        outcome["elapsed"] = round(time.time() - started, 1)
        return outcome

    # 4~5. 썸네일 + 업로드
    try:
        thumb = thumbnail.generate_for(doc, layout=layout)
        outcome["thumbnail"] = thumb

        upload_result = cms.publish(
            doc=doc,
            body_html=renderer.render_body(doc, include_schema=True),
            reports=reports,
            expose=expose,
            dry_run=dry_run,
            thumbnail_path=thumb,
        )
        outcome["uploaded"] = bool(upload_result.get("saved"))
        outcome["exposed"] = outcome["uploaded"] and expose
        outcome["shots"] = upload_result.get("shots", [])
        outcome["cms_alert"] = upload_result.get("alert", "")
        outcome["message"] = upload_result.get("message", "")

        if outcome["uploaded"]:
            store.set_status(post_id, "published" if expose else "uploaded")
    except cms.ComplianceBlocked as exc:
        outcome["blocked"] = True
        outcome["error"] = str(exc)
        store.set_status(post_id, "blocked")
    except Exception as exc:
        outcome["error"] = f"업로드 실패: {exc}"
        logger.exception("업로드 실패: %s", title)

    outcome["elapsed"] = round(time.time() - started, 1)
    return outcome


def run_many(titles: list, **kwargs) -> list:
    """제목 여러 개를 차례로 처리한다. 하나가 실패해도 나머지는 계속한다."""
    outcomes = []
    total = len(titles)
    for i, title in enumerate(titles, 1):
        logger.info("[%d/%d] %s", i, total, title)
        outcomes.append(run_one(title, **kwargs))
    return outcomes


def format_outcome(outcome: dict, verbose: bool = True) -> str:
    """결과를 사람이 읽을 형태로."""
    lines = []
    if outcome.get("error") and not outcome.get("post_id"):
        return f"  ❌ {outcome['title']}\n     {outcome['error']}"

    if outcome.get("blocked"):
        mark = "🚫"
    elif outcome.get("exposed"):
        mark = "✅"
    elif outcome.get("uploaded"):
        mark = "📝"
    elif outcome.get("error"):
        mark = "❌"
    else:
        mark = "💾"

    lines.append(f"  {mark} {outcome.get('h1') or outcome['title']}")

    parsed = outcome.get("parsed")
    if parsed and verbose:
        lines.append(f"     {title_parser.describe(parsed)}")

    scores = outcome.get("scores")
    if scores:
        lines.append(
            f"     SEO {scores['seo']} · AEO {scores['aeo']} · GEO {scores['geo']}"
            f" → 종합 {scores['total']}"
        )

    law = outcome.get("law")
    if law:
        lines.append(f"     의료법: {law['summary']}")
        for f in law.get("findings", [])[:3]:
            if f["severity"] in ("block", "warn"):
                lines.append(f"       [{f['severity']}] \"{f['matched']}\"")

    if outcome.get("attempts", 1) > 1:
        lines.append(f"     자동 교정 {outcome['attempts'] - 1}회")

    if outcome.get("error"):
        lines.append(f"     {outcome['error']}")
    elif outcome.get("uploaded"):
        state = "노출" if outcome.get("exposed") else "미노출"
        lines.append(f"     업로드 완료 ({state}) · {outcome.get('post_url', '')}")

    if outcome.get("cms_alert"):
        lines.append(f"     CMS 알림: {outcome['cms_alert']}")

    lines.append(
        f"     {outcome.get('elapsed', 0)}초 · 약 ${outcome.get('cost', 0)}"
        f" · id={outcome.get('post_id', '-')}"
    )
    return "\n".join(lines)


def summarize(outcomes: list) -> str:
    exposed = sum(1 for o in outcomes if o.get("exposed"))
    uploaded = sum(1 for o in outcomes if o.get("uploaded") and not o.get("exposed"))
    blocked = sum(1 for o in outcomes if o.get("blocked"))
    failed = sum(1 for o in outcomes if o.get("error") and not o.get("blocked"))
    saved = len(outcomes) - exposed - uploaded - blocked - failed
    cost = round(sum(o.get("cost", 0) for o in outcomes), 3)

    parts = []
    if exposed:
        parts.append(f"노출 {exposed}건")
    if uploaded:
        parts.append(f"미노출 저장 {uploaded}건")
    if saved:
        parts.append(f"원고만 생성 {saved}건")
    if blocked:
        parts.append(f"의료법 차단 {blocked}건")
    if failed:
        parts.append(f"실패 {failed}건")
    return f"{' · '.join(parts)} · 총 약 ${cost}"
