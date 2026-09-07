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
    url_for,
)

from content import (
    clinic,
    generator,
    medical_law,
    renderer,
    schema,
    seo,
    store,
    taxonomy,
)

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
    }


@app.route("/")
def index():
    return render_template(
        "content.html",
        view="form",
        posts=store.list_posts(30),
        used=store.used_keywords(),
        **_base_context(),
    )


@app.route("/generate", methods=["POST"])
def generate():
    form = request.form
    category = (form.get("category") or "").strip()
    primary = (form.get("primary_keyword") or "").strip()
    topic = (form.get("topic") or "").strip()

    if not category or not primary or not topic:
        return render_template(
            "content.html",
            view="form",
            error="카테고리·주키워드·주제는 필수입니다.",
            posts=store.list_posts(30),
            used=store.used_keywords(),
            **_base_context(),
        ), 400

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
        return render_template(
            "content.html",
            view="form",
            error=str(exc),
            posts=store.list_posts(30),
            used=store.used_keywords(),
            **_base_context(),
        ), 502

    post_id = store.save(result["doc"], result["reports"], topic)
    return redirect(url_for("post_detail", post_id=post_id))


@app.route("/post/<int:post_id>")
def post_detail(post_id: int):
    record = store.get(post_id)
    if not record:
        abort(404)

    doc = record["doc"]
    return render_template(
        "content.html",
        view="post",
        record=record,
        doc=doc,
        reports=record["reports"],
        cms=renderer.cms_fields(doc),
        body_html=renderer.render_body(doc, include_schema=False),
        plaintext=renderer.render_plaintext(doc),
        jsonld=schema.to_script_tag(doc),
        cost=generator.estimate_cost(doc.get("_usage", {})),
        **_base_context(),
    )


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
