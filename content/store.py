# -*- coding: utf-8 -*-
"""
생성 이력 저장소 (SQLite).

같은 키워드로 중복 생성하는 것을 막고, 어떤 글이 어떤 점수로 나갔는지 남깁니다.
순위 모니터링 DB(rankings.db)와 파일을 분리해 서로 영향을 주지 않게 합니다.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("CONTENT_DB_PATH", "content.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    primary_keyword TEXT    NOT NULL,
    topic           TEXT    DEFAULT '',
    h1              TEXT    NOT NULL,
    post_url        TEXT    NOT NULL,
    meta_title      TEXT    DEFAULT '',
    meta_desc       TEXT    DEFAULT '',
    score_seo       INTEGER DEFAULT 0,
    score_aeo       INTEGER DEFAULT 0,
    score_geo       INTEGER DEFAULT 0,
    score_total     INTEGER DEFAULT 0,
    law_blocks      INTEGER DEFAULT 0,
    law_warns       INTEGER DEFAULT 0,
    status          TEXT    DEFAULT 'draft',
    doc_json        TEXT    NOT NULL,
    reports_json    TEXT    NOT NULL
);
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_posts_keyword ON posts(primary_keyword);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_url ON posts(post_url);",
]


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.execute(CREATE_TABLE_SQL)
        for sql in CREATE_INDEX_SQL:
            conn.execute(sql)


def save(doc: dict, reports: dict, topic: str = "") -> int:
    """생성 결과를 저장하고 id를 돌려준다. 같은 URL이면 덮어쓴다."""
    init_db()
    scores = reports["seo"]["scores"]
    law = reports["law"]
    payload = (
        datetime.now().isoformat(timespec="seconds"),
        doc.get("category", ""),
        doc.get("primary_keyword", ""),
        topic,
        doc.get("h1", ""),
        doc.get("post_url", ""),
        doc.get("meta_title", ""),
        doc.get("meta_description", ""),
        scores["seo"],
        scores["aeo"],
        scores["geo"],
        scores["total"],
        law["block_count"],
        law["warn_count"],
        "draft",
        json.dumps(doc, ensure_ascii=False),
        json.dumps(reports, ensure_ascii=False),
    )
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO posts (
                created_at, category, primary_keyword, topic, h1, post_url,
                meta_title, meta_desc, score_seo, score_aeo, score_geo,
                score_total, law_blocks, law_warns, status, doc_json, reports_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(post_url) DO UPDATE SET
                created_at      = excluded.created_at,
                category        = excluded.category,
                primary_keyword = excluded.primary_keyword,
                topic           = excluded.topic,
                h1              = excluded.h1,
                meta_title      = excluded.meta_title,
                meta_desc       = excluded.meta_desc,
                score_seo       = excluded.score_seo,
                score_aeo       = excluded.score_aeo,
                score_geo       = excluded.score_geo,
                score_total     = excluded.score_total,
                law_blocks      = excluded.law_blocks,
                law_warns       = excluded.law_warns,
                doc_json        = excluded.doc_json,
                reports_json    = excluded.reports_json
            """,
            payload,
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM posts WHERE post_url = ?", (doc.get("post_url", ""),)
        ).fetchone()
        return row["id"] if row else 0


def get(post_id: int):
    init_db()
    with _conn() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["doc"] = json.loads(data.pop("doc_json"))
    data["reports"] = json.loads(data.pop("reports_json"))
    return data


def list_posts(limit: int = 50) -> list:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, category, primary_keyword, h1, post_url,
                   score_seo, score_aeo, score_geo, score_total,
                   law_blocks, law_warns, status
            FROM posts ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_status(post_id: int, status: str) -> None:
    init_db()
    with _conn() as conn:
        conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))


def used_keywords() -> list:
    """이미 글을 쓴 주키워드 목록 - 중복 주제 방지용."""
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT primary_keyword, COUNT(*) AS n FROM posts GROUP BY primary_keyword"
        ).fetchall()
    return [{"keyword": r["primary_keyword"], "count": r["n"]} for r in rows]


def delete(post_id: int) -> None:
    init_db()
    with _conn() as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
