"""
Flask 기반 순위 현황 대시보드
"""

import logging
from flask import Flask, render_template, jsonify

from config import DASHBOARD_HOST, DASHBOARD_PORT, TARGET_BRAND
from database import init_db, get_pivot, get_recent_rankings

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/")
def index():
    pivot = get_pivot(days=14)
    return render_template("index.html", pivot=pivot, brand=TARGET_BRAND)


@app.route("/api/rankings")
def api_rankings():
    """최근 14일 데이터를 JSON으로 반환."""
    pivot = get_pivot(days=14)
    return jsonify(pivot)


@app.route("/api/today")
def api_today():
    """오늘 수집 결과 JSON."""
    rows = get_recent_rankings(days=1)
    return jsonify(rows)


def run_dashboard():
    init_db()
    logger.info("대시보드 시작: http://%s:%d", DASHBOARD_HOST, DASHBOARD_PORT)
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)
