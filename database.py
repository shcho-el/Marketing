"""
SQLite 기반 순위 데이터 저장소
"""

import json
import sqlite3
import logging
from datetime import date, datetime
from contextlib import contextmanager

from config import DB_PATH

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rankings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT    NOT NULL,
    keyword           TEXT    NOT NULL,
    brand             TEXT    NOT NULL,
    rank              INTEGER,
    ranks_all         TEXT    DEFAULT '',
    popular_rank      INTEGER,
    popular_ranks_all TEXT    DEFAULT '',
    title             TEXT    DEFAULT '',
    url               TEXT    DEFAULT '',
    checked_count     INTEGER DEFAULT 0,
    created_at        TEXT    NOT NULL
);
"""

CREATE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_date_keyword_brand
    ON rankings (date, keyword, brand);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """데이터베이스 및 테이블 초기화."""
    with _conn() as con:
        con.execute(CREATE_TABLE_SQL)
        con.execute(CREATE_INDEX_SQL)
        cols = [r[1] for r in con.execute("PRAGMA table_info(rankings)").fetchall()]
        if "ranks_all" not in cols:
            con.execute("ALTER TABLE rankings ADD COLUMN ranks_all TEXT DEFAULT ''")
        if "popular_rank" not in cols:
            con.execute("ALTER TABLE rankings ADD COLUMN popular_rank INTEGER")
        if "popular_ranks_all" not in cols:
            con.execute("ALTER TABLE rankings ADD COLUMN popular_ranks_all TEXT DEFAULT ''")
    logger.info("DB 초기화 완료: %s", DB_PATH)


def upsert_ranking(
    *,
    check_date: date,
    keyword: str,
    brand: str,
    rank: int | None,
    ranks_all: list = None,
    popular_rank: int | None = None,
    popular_ranks_all: list = None,
    title: str = "",
    url: str = "",
    checked_count: int = 0,
) -> None:
    """당일 순위를 저장 (이미 있으면 덮어쓰기)."""
    ranks_json = json.dumps(ranks_all or [], ensure_ascii=False)
    popular_ranks_json = json.dumps(popular_ranks_all or [], ensure_ascii=False)
    sql = """
        INSERT INTO rankings
            (date, keyword, brand, rank, ranks_all, popular_rank, popular_ranks_all,
             title, url, checked_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, keyword, brand) DO UPDATE SET
            rank              = excluded.rank,
            ranks_all         = excluded.ranks_all,
            popular_rank      = excluded.popular_rank,
            popular_ranks_all = excluded.popular_ranks_all,
            title             = excluded.title,
            url               = excluded.url,
            checked_count     = excluded.checked_count,
            created_at        = excluded.created_at
    """
    with _conn() as con:
        con.execute(sql, (
            check_date.isoformat(),
            keyword,
            brand,
            rank,
            ranks_json,
            popular_rank,
            popular_ranks_json,
            title,
            url,
            checked_count,
            datetime.now().isoformat(timespec="seconds"),
        ))


def save_results(results: list[dict], check_date: date | None = None) -> None:
    """scraper.run_all_keywords() 반환값을 DB에 저장."""
    if check_date is None:
        check_date = date.today()
    for r in results:
        upsert_ranking(
            check_date=check_date,
            keyword=r["keyword"],
            brand=r["brand"],
            rank=r.get("rank"),
            ranks_all=r.get("ranks", []),
            popular_rank=r.get("popular_rank"),
            popular_ranks_all=r.get("popular_ranks", []),
            title=r.get("title", ""),
            url=r.get("url", ""),
            checked_count=r.get("checked_count", 0),
        )
    logger.info("%d건 저장 완료 (날짜: %s)", len(results), check_date)


def get_recent_rankings(days: int = 7) -> list[dict]:
    sql = """
        SELECT date, keyword, brand, rank, ranks_all, title, url
        FROM rankings
        WHERE date >= date('now', ?)
        ORDER BY date DESC, keyword ASC
    """
    with _conn() as con:
        rows = con.execute(sql, (f"-{days} days",)).fetchall()
    return [dict(row) for row in rows]


def get_dates() -> list[str]:
    with _conn() as con:
        rows = con.execute(
            "SELECT DISTINCT date FROM rankings ORDER BY date DESC"
        ).fetchall()
    return [row["date"] for row in rows]


def get_pivot(days: int = 14) -> dict:
    data = get_recent_rankings(days)
    dates = sorted({r["date"] for r in data}, reverse=True)
    keywords_order: list[str] = []
    seen: set[str] = set()
    for r in sorted(data, key=lambda x: x["keyword"]):
        if r["keyword"] not in seen:
            keywords_order.append(r["keyword"])
            seen.add(r["keyword"])

    lookup: dict[tuple, int | None] = {}
    for r in data:
        lookup[(r["keyword"], r["date"])] = r["rank"]

    rows = []
    for kw in keywords_order:
        rows.append({
            "keyword": kw,
            "ranks": {d: lookup.get((kw, d)) for d in dates},
        })

    return {"dates": dates, "rows": rows}
