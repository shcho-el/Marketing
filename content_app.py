# -*- coding: utf-8 -*-
"""
콘텐츠 콘솔 — 사내 PC에서 띄워 여럿이 함께 쓰는 웹앱.

  python main.py content      또는  serve.bat / ./serve.sh

설계
  · Claude API 키와 CMS 로그인 정보는 서버(.env)에만 있고 브라우저로 내려가지
    않습니다. 생성·업로드는 전부 서버가 수행합니다.
  · 의료법·포지셔닝·SEO 규칙은 content/ 모듈 하나만 씁니다.
    화면은 결과를 받아 그리기만 하므로 규칙이 두 곳으로 갈라지지 않습니다.
  · 사내망에 열어 두므로 비밀번호를 걸 수 있습니다(APP_PASSWORD).
"""

import json
import logging
import os
import queue
import secrets
import socket
import threading
import time
from functools import wraps

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    stream_with_context,
    url_for,
)

import console
import pipeline
from content import (
    build,
    clinic,
    generator,
    importer,
    medical_law,
    positioning,
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
# 세션 서명 키. 지정하지 않으면 매 기동마다 새로 만들어 로그인만 풀린다.
app.secret_key = os.getenv("APP_SECRET", "") or secrets.token_hex(16)

HOST = os.getenv("CONTENT_HOST", "0.0.0.0")
PORT = int(os.getenv("CONTENT_PORT", "5001"))
PASSWORD = os.getenv("APP_PASSWORD", "")


# ── 접근 제어 ────────────────────────────────────────────────────────
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if PASSWORD and not session.get("ok"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "로그인이 필요합니다."}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if not PASSWORD:
        return redirect(url_for("index"))
    error = ""
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), PASSWORD):
            session["ok"] = True
            session.permanent = True
            return redirect(request.args.get("next") or url_for("index"))
        error = "비밀번호가 맞지 않습니다."
    page = render_template("login.html", clinic=clinic.FULL_NAME, error=error)
    return (page, 401) if error else page


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login") if PASSWORD else url_for("index"))


# ── 뷰 모델 ──────────────────────────────────────────────────────────
def lan_url() -> str:
    """같은 네트워크의 다른 PC가 접속할 주소."""
    ip = "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
    except Exception:
        pass
    return f"http://{ip}:{PORT}"


def _cms_field_rows(doc: dict) -> list:
    limits = {"MetaTitle": seo.META_TITLE_MAX, "MetaDescription": seo.META_DESC_MAX}
    rows = []
    for key, value in renderer.cms_fields(doc).items():
        row = {"key": key, "value": value}
        if key in limits:
            row["len"] = len(value)
            row["max"] = limits[key]
        elif key == "제목(H1)":
            row["len"] = len(value)
        rows.append(row)
    return rows


def view_model(doc: dict, reports: dict, post_id=None, is_sample=False) -> dict:
    return {
        "post_id": post_id,
        "is_sample": is_sample,
        "doc": doc,
        "reports": reports,
        "cms_fields": _cms_field_rows(doc),
        "body_html": renderer.render_body(doc, include_schema=False),
        "plaintext": renderer.render_plaintext(doc),
        "jsonld": schema.to_script_tag(doc),
        "logo": cms_thumbnail.logo_status(),
        "cms": cms_config.status(),
        # 키 자체는 절대 내려보내지 않는다. 있는지 여부만 알린다.
        "api_key_ready": generator.has_api_key(),
    }


def sample_view() -> dict:
    """화면이 빈 껍데기로 열리지 않도록, 가장 최근 글이나 예시를 보여 준다."""
    rows = store.list_posts(1)
    if rows:
        rec = store.get(rows[0]["id"])
        if rec:
            return view_model(rec["doc"], rec["reports"], rec["id"])

    from test_content import FIXTURE

    doc = generator._normalize(dict(FIXTURE), FIXTURE["category"], FIXTURE["primary_keyword"])
    text = generator._full_text(doc)
    reports = {
        "law": medical_law.review(text),
        "positioning": positioning.review(text),
        "seo": seo.audit(doc, doc["primary_keyword"]),
    }
    return view_model(doc, reports, None, is_sample=True)


# ── 화면 ─────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template(
        "console.html",
        clinic=clinic.FULL_NAME,
        boot=sample_view(),
        lan_url=lan_url(),
        auth_on=bool(PASSWORD),
        build=build.stamp(refresh=True),
    )


@app.route("/post/<int:post_id>/thumbnail.jpg")
@login_required
def post_thumbnail(post_id: int):
    record = store.get(post_id)
    if not record:
        abort(404)
    doc = dict(record["doc"])
    copy = request.args.get("copy", "")
    if copy:
        doc["thumbnail_copy"] = copy
    try:
        path = cms_thumbnail.generate_for(doc, layout=request.args.get("layout", ""))
    except cms_thumbnail.ThumbnailError as exc:
        logger.warning("썸네일 생성 실패: %s", exc)
        abort(500, description=str(exc))
    return send_file(os.path.abspath(path), mimetype="image/jpeg", max_age=0)


# ── JSON API ─────────────────────────────────────────────────────────
@app.route("/api/preview-title")
@login_required
def api_preview_title():
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({"error": "제목이 비어 있습니다."}), 400
    parsed = title_parser.parse(title)
    return jsonify({**parsed, "summary": title_parser.describe(parsed)})


@app.route("/api/generate", methods=["POST"])
@login_required
def api_generate():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "제목을 입력하세요."}), 400

    try:
        result = generator.generate_from_title(title)
    except generator.GenerationError as exc:
        logger.warning("생성 실패: %s", exc)
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:
        logger.exception("생성 실패")
        return jsonify({"error": f"생성하지 못했습니다: {exc}"}), 500

    doc, reports = result["doc"], result["reports"]
    post_id = store.save(doc, reports, result["parsed"]["topic"])
    return jsonify(view_model(doc, reports, post_id))


@app.route("/api/generate/stream")
@login_required
def api_generate_stream():
    """생성 진행 상황을 흘려보낸다(Server-Sent Events).

    1~3분이 걸리는데 화면에 아무 표시가 없으면 멈춘 것처럼 보입니다.
    생성은 별도 스레드에서 돌리고, 단계가 바뀔 때마다 큐로 받아 내보냅니다.
    """
    title = (request.args.get("title") or "").strip()
    if not title:
        return jsonify({"error": "제목을 입력하세요."}), 400
    if not generator.has_api_key():
        return jsonify({"error": generator.NO_KEY_MESSAGE}), 400

    events: "queue.Queue" = queue.Queue()

    def report(stage, state, detail=""):
        events.put({"type": "stage", "stage": stage, "state": state, "detail": detail})

    def work():
        try:
            result = generator.generate_from_title(title, on_progress=report)
            doc, reports = result["doc"], result["reports"]
            report("save", "start", "")
            post_id = store.save(doc, reports, result["parsed"]["topic"])
            report("save", "done", "")
            events.put({"type": "done", "view": view_model(doc, reports, post_id)})
        except generator.GenerationError as exc:
            events.put({"type": "error", "error": str(exc)})
        except Exception as exc:  # 예상 못 한 오류도 화면까지 전달한다
            logger.exception("생성 실패")
            events.put({"type": "error", "error": f"생성하지 못했습니다: {exc}"})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        yield "retry: 10000\n\n"
        yield f"data: {json.dumps({'type': 'stages', 'stages': [{'key': k, 'label': v} for k, v in generator.STAGES]}, ensure_ascii=False)}\n\n"
        last = time.time()
        while True:
            try:
                item = events.get(timeout=10)
            except queue.Empty:
                # 프록시가 끊지 않도록 주기적으로 신호를 보낸다
                yield ": keep-alive\n\n"
                continue
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            last = time.time()

    return app.response_class(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/import", methods=["POST"])
@login_required
def api_import():
    """클라우드 웹앱에서 만든 원고를 받아 발행 가능한 상태로 저장한다.

    API 요금 없이 생성한 원고를 CMS 업로드까지 잇는 통로입니다.
    """
    payload = request.get_json(silent=True) or {}
    try:
        result = importer.load(payload.get("text") or payload.get("doc") or "")
    except importer.ImportError_ as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("가져오기 실패")
        return jsonify({"error": f"가져오지 못했습니다: {exc}"}), 500

    doc, reports = result["doc"], result["reports"]
    post_id = store.save(doc, reports, result["topic"])
    view = view_model(doc, reports, post_id)
    view["warnings"] = result["warnings"]
    return jsonify(view)


@app.route("/api/post/<int:post_id>")
@login_required
def api_post(post_id: int):
    record = store.get(post_id)
    if not record:
        return jsonify({"error": "글을 찾을 수 없습니다."}), 404
    return jsonify(view_model(record["doc"], record["reports"], post_id))


@app.route("/api/posts")
@login_required
def api_posts():
    return jsonify(store.list_posts(30))


@app.route("/api/lint", methods=["POST"])
@login_required
def api_lint():
    text = (request.get_json(silent=True) or {}).get("text", "")
    return jsonify({"law": medical_law.review(text), "positioning": positioning.review(text)})


@app.route("/api/publish", methods=["POST"])
@login_required
def api_publish():
    payload = request.get_json(silent=True) or {}
    record = store.get(int(payload.get("post_id") or 0))
    if not record:
        return jsonify({"error": "글을 찾을 수 없습니다."}), 404

    doc, reports = record["doc"], record["reports"]
    expose = bool(payload.get("expose"))
    dry_run = bool(payload.get("dry_run"))

    try:
        thumb = cms_thumbnail.generate_for(doc)
        result = cms_publish.publish(
            doc=doc,
            body_html=renderer.render_body(doc, include_schema=True),
            reports=reports,
            expose=expose,
            dry_run=dry_run,
            thumbnail_path=thumb,
        )
    except cms_publish.ComplianceBlocked as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("업로드 실패")
        return jsonify({"error": f"업로드하지 못했습니다: {exc}"}), 500

    if result.get("saved"):
        store.set_status(record["id"], "published" if expose else "uploaded")

    # "캡처를 확인하세요"라고만 하고 볼 방법을 주지 않으면 안내가 아니다.
    # 파일 이름만 내려보내고, 그림은 아래 /shot 으로 받아 화면에 띄운다.
    result["shot_names"] = [os.path.basename(p) for p in result.get("shots", []) if p]
    return jsonify(result)


@app.route("/shot/<name>")
@login_required
def cms_shot(name: str):
    """업로드 과정에서 남긴 화면 캡처를 보여 준다."""
    # 파일 이름만 받는다. 경로가 섞여 들어오면 폴더 밖 파일을 읽을 수 있다.
    safe = os.path.basename(name)
    if safe != name or not safe.endswith(".png"):
        abort(404)
    path = os.path.join(cms_publish.SHOT_DIR, safe)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="image/png")


@app.route("/api/audit", methods=["POST"])
@login_required
def api_audit():
    doc = (request.get_json(silent=True) or {}).get("doc") or {}
    return jsonify(seo.audit(doc, doc.get("primary_keyword", "")))


# ── 기동 ─────────────────────────────────────────────────────────────
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "server.pid")


def _write_pid():
    """실행 중인 서버를 launch.bat이 찾아 끌 수 있게 PID를 남긴다.

    코드를 새로 받아도 옛 서버가 계속 떠 있으면 화면은 옛날 그대로다.
    바로가기가 알아서 껐다 켜려면 어느 프로세스인지 알아야 한다.
    """
    import atexit

    try:
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        with open(PID_FILE, "w", encoding="utf-8") as fp:
            fp.write(str(os.getpid()))
    except OSError:
        return  # PID를 못 남겨도 서버는 정상 동작한다

    def clear():
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    atexit.register(clear)


def run_app():
    console.use_utf8()
    store.init_db()
    _write_pid()
    stamp = build.stamp()
    url = lan_url()
    print()
    print("  " + "=" * 52)
    print(f"   {clinic.FULL_NAME} 콘텐츠 콘솔")
    print("  " + "=" * 52)
    print(f"   이 PC에서      http://localhost:{PORT}")
    print(f"   사내 다른 PC   {url}")
    if PASSWORD:
        print("   비밀번호       설정됨 (APP_PASSWORD)")
    else:
        print("   비밀번호       없음 — 같은 네트워크면 누구나 들어옵니다.")
        print("                  .env에 APP_PASSWORD를 넣어 잠그세요.")
    if not os.getenv("APP_SECRET"):
        print("   참고           APP_SECRET 미설정 — 재시작하면 로그인이 풀립니다.")
    if stamp["ok"]:
        print(f"   코드 버전      {stamp['commit']} ({stamp['date']})")
        if stamp["behind"]:
            print(f"   [!] 업데이트    {stamp['behind']}개 뒤처져 있습니다. update.bat 을 실행하세요.")
    print("  " + "=" * 52)
    print("   끄려면 Ctrl+C")
    print()
    app.run(host=HOST, port=PORT, debug=False, threaded=True)


if __name__ == "__main__":
    console.use_utf8()
    logging.basicConfig(level=logging.INFO)
    run_app()
