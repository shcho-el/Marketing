# -*- coding: utf-8 -*-
"""
콘텐츠 자동 생성 웹앱.

  python main.py content        → http://localhost:5001

화면
  /                생성 폼 + 생성 이력
  /post/<id>       생성 결과 (CMS 필드 · 본문 HTML · 점수 · 의료법 리포트 · JSON-LD)
  /lint            기존 원고 붙여넣기 검사 (생성 없이 의료법·표현만 점검)
"""

import logging
import os

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

import pipeline
from content import (
    clinic,
    generator,
    medical_law,
    renderer,
    schema,
    seo,
    store,
    taxonomy,
    title_parser,
)
from publisher import config as cms_config
from publisher import publish as cms_publish
from publisher import thumbnail as cms_thumbnail

logger = logging.getLogger(__name__)

app = Flask(__name__)

CONTENT_HOST = os.getenv("CONTENT_HOST", "0.0.0.0")
CONTENT_PORT = int(os.getenv("CONTENT_PORT", "5001"))


def _base_context() -> dict:
    return {
        "clinic_name": clinic.FULL_NAME,
        "categories": taxonomy.CATEGORIES,
        "core_keywords": taxonomy.CORE_KEYWORDS,
        "nap": clinic.nap_completeness(),
        "cms": cms_config.status(),
    }


def _form_view(**extra):
    return render_template(
        "content.html",
        view="form",
        posts=store.list_posts(30),
        used=store.used_keywords(),
        **_base_context(),
        **extra,
    )


@app.route("/")
def index():
    return _form_view()


@app.route("/auto", methods=["POST"])
def auto():
    """제목만 받아 생성부터 업로드까지 한 번에 처리한다."""
    raw = (request.form.get("titles") or "").strip()
    titles = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not titles:
        return _form_view(error="제목을 한 줄에 하나씩 입력하세요."), 400

    upload = request.form.get("upload") == "on"
    expose = request.form.get("expose") == "on"

    if upload and not cms_config.status()["ready"]:
        return _form_view(
            error="CMS 업로드 설정이 끝나지 않았습니다. "
                  "터미널에서 python main.py inspect-cms 를 먼저 실행하세요."
        ), 400

    outcomes = pipeline.run_many(titles, upload=upload, expose=expose, dry_run=False)
    return render_template(
        "content.html",
        view="auto_result",
        outcomes=outcomes,
        summary=pipeline.summarize(outcomes),
        **_base_context(),
    )


@app.route("/api/preview-title")
def api_preview_title():
    """제목을 어떻게 해석했는지 미리 보여 준다(생성 전 확인용)."""
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({"error": "title 파라미터가 필요합니다."}), 400
    try:
        parsed = title_parser.parse(title)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({**parsed, "summary": title_parser.describe(parsed)})


@app.route("/generate", methods=["POST"])
def generate():
    form = request.form
    category = (form.get("category") or "").strip()
    primary = (form.get("primary_keyword") or "").strip()
    topic = (form.get("topic") or "").strip()

    if not category or not primary or not topic:
        return _form_view(error="카테고리·주키워드·주제는 필수입니다."), 400

    try:
        result = generator.generate(
            category=category,
            primary_keyword=primary,
            topic=topic,
            angle=(form.get("angle") or "").strip(),
            audience=(form.get("audience") or "").strip(),
            extra_notes=(form.get("extra_notes") or "").strip(),
            auto_repair=form.get("auto_repair") == "on",
        )
    except generator.GenerationError as exc:
        logger.exception("생성 실패")
        return _form_view(error=str(exc)), 502

    post_id = store.save(result["doc"], result["reports"], topic)
    return redirect(url_for("post_detail", post_id=post_id))


@app.route("/post/<int:post_id>")
def post_detail(post_id: int):
    record = store.get(post_id)
    if not record:
        abort(404)

    return _post_view(record)


@app.route("/post/<int:post_id>/status", methods=["POST"])
def post_status(post_id: int):
    store.set_status(post_id, request.form.get("status", "draft"))
    return redirect(url_for("post_detail", post_id=post_id))


@app.route("/post/<int:post_id>/delete", methods=["POST"])
def post_delete(post_id: int):
    store.delete(post_id)
    return redirect(url_for("index"))


@app.route("/lint", methods=["GET", "POST"])
def lint():
    """이미 써 둔 원고를 붙여 넣어 의료법 표현만 점검한다."""
    text = ""
    report = None
    if request.method == "POST":
        text = request.form.get("text", "")
        report = medical_law.review(text)
    return render_template(
        "content.html",
        view="lint",
        lint_text=text,
        lint_report=report,
        **_base_context(),
    )


@app.route("/post/<int:post_id>/thumbnail.jpg")
def post_thumbnail(post_id: int):
    """썸네일 미리보기. 업로드 전에 눈으로 확인할 수 있어야 합니다."""
    record = store.get(post_id)
    if not record:
        abort(404)

    layout = request.args.get("layout", "")
    try:
        path = cms_thumbnail.generate_for(record["doc"], layout=layout)
    except cms_thumbnail.ThumbnailError as exc:
        logger.warning("썸네일 생성 실패: %s", exc)
        abort(500, description=str(exc))
    return send_file(os.path.abspath(path), mimetype="image/jpeg", max_age=0)


@app.route("/post/<int:post_id>/publish", methods=["POST"])
def post_publish(post_id: int):
    """CMS에 업로드한다. 기본은 미노출 저장."""
    record = store.get(post_id)
    if not record:
        abort(404)

    doc = record["doc"]
    reports = record["reports"]
    dry_run = request.form.get("dry_run") == "on"
    # 노출 전환은 사람이 CMS에서 확인하고 누르도록 기본값을 미노출로 둔다.
    expose = request.form.get("expose") == "on"
    layout = request.form.get("layout", "")

    try:
        thumb = cms_thumbnail.generate_for(doc, layout=layout)
        result = cms_publish.publish(
            doc=doc,
            body_html=renderer.render_body(doc, include_schema=True),
            reports=reports,
            expose=expose,
            dry_run=dry_run,
            thumbnail_path=thumb,
        )
    except cms_publish.ComplianceBlocked as exc:
        return _post_view(record, publish_error=str(exc), blocked=True)
    except Exception as exc:
        logger.exception("CMS 업로드 실패")
        return _post_view(record, publish_error=str(exc))

    if result.get("saved"):
        store.set_status(post_id, "published" if expose else "uploaded")
    return _post_view(store.get(post_id) or record, publish_result=result)


def _post_view(record, **extra):
    """결과 화면 렌더링 - 발행 결과/오류를 함께 표시한다."""
    doc = record["doc"]
    return render_template(
        "content.html",
        view="post",
        record=record,
        doc=doc,
        reports=record["reports"],
        cms_fields=renderer.cms_fields(doc),
        body_html=renderer.render_body(doc, include_schema=False),
        plaintext=renderer.render_plaintext(doc),
        jsonld=schema.to_script_tag(doc),
        cost=generator.estimate_cost(doc.get("_usage", {})),
        thumb_layout=extra.pop("thumb_layout", request.args.get("layout", "")),
        thumb_ready=bool(cms_thumbnail.list_photos(doc.get("category", ""))),
        thumb_photo_dir=cms_thumbnail.PHOTO_DIR,
        thumb_has_logo=os.path.exists(cms_thumbnail.LOGO_PATH),
        **_base_context(),
        **extra,
    )


# ── JSON API ─────────────────────────────────────────────────────────
@app.route("/api/posts")
def api_posts():
    return jsonify(store.list_posts(100))


@app.route("/api/post/<int:post_id>")
def api_post(post_id: int):
    record = store.get(post_id)
    if not record:
        return jsonify({"error": "not found"}), 404
    return jsonify(
        {
            "cms_fields": renderer.cms_fields(record["doc"]),
            "body_html": renderer.render_body(record["doc"]),
            "json_ld": schema.build(record["doc"]),
            "reports": record["reports"],
        }
    )


@app.route("/api/lint", methods=["POST"])
def api_lint():
    payload = request.get_json(silent=True) or {}
    return jsonify(medical_law.review(payload.get("text", "")))


@app.route("/api/audit", methods=["POST"])
def api_audit():
    """외부에서 만든 문서(JSON)를 점수만 매겨 본다."""
    payload = request.get_json(silent=True) or {}
    doc = payload.get("doc") or {}
    return jsonify(seo.audit(doc, doc.get("primary_keyword", "")))


def run_app():
    store.init_db()
    logger.info("콘텐츠 생성 앱 시작: http://%s:%d", CONTENT_HOST, CONTENT_PORT)
    app.run(host=CONTENT_HOST, port=CONTENT_PORT, debug=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_app()
