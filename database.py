"""
SQLite 기반 순위 데이터 저장소
"""

import sqlite3
import logging
from datetime import date, datetime
from contextlib import contextmanager

from config import DB_PATH

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rankings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,           -- YYYY-MM-DD
    keyword     TEXT    NOT NULL,
    brand       TEXT    NOT NULL,
    rank        INTEGER,                    -- NULL = 미노출 (블로그)
    title       TEXT    DEFAULT '',
    url         TEXT    DEFAULT '',
    checked_count INTEGER DEFAULT 0,
    powerlink_rank  INTEGER,               -- NULL = 미노출 (파워링크)
    powerlink_title TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL
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
    """데이터베이스 및 테이블 초기화 (기존 DB 마이그레이션 포함)."""
    with _conn() as con:
        con.execute(CREATE_TABLE_SQL)
        con.execute(CREATE_INDEX_SQL)
        # 기존 DB에 파워링크 컬럼 추가 (없으면)
        cols = [r[1] for r in con.execute("PRAGMA table_info(rankings)").fetchall()]
        if "powerlink_rank" not in cols:
            con.execute("ALTER TABLE rankings ADD COLUMN powerlink_rank INTEGER")
        if "powerlink_title" not in cols:
            con.execute("ALTER TABLE rankings ADD COLUMN powerlink_title TEXT DEFAULT ''")
    logger.info("DB 초기화 완료: %s", DB_PATH)


def upsert_ranking(
    *,
    check_date: date,
    keyword: str,
    brand: str,
    rank: int | None,
    title: str = "",
    url: str = "",
    checked_count: int = 0,
    powerlink_rank: int | None = None,
    powerlink_title: str = "",
) -> None:
    """당일 순위를 저장 (이미 있으면 덮어쓰기)."""
    sql = """
        INSERT INTO rankings
            (date, keyword, brand, rank, title, url, checked_count, powerlink_rank, powerlink_title, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, keyword, brand) DO UPDATE SET
            rank            = excluded.rank,
            title           = excluded.title,
            url             = excluded.url,
            checked_count   = excluded.checked_count,
            powerlink_rank  = excluded.powerlink_rank,
            powerlink_title = excluded.powerlink_title,
            created_at      = excluded.created_at
    """
    with _conn() as con:
        con.execute(sql, (
            check_date.isoformat(),
            keyword,
            brand,
            rank,
            title,
            url,
            checked_count,
            powerlink_rank,
            powerlink_title,
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
            title=r.get("title", ""),
            url=r.get("url", ""),
            checked_count=r.get("checked_count", 0),
            powerlink_rank=r.get("powerlink_rank"),
            powerlink_title=r.get("powerlink_title", ""),
        )
    logger.info("%d건 저장 완료 (날짜: %s)", len(results), check_date)


def get_recent_rankings(days: int = 7) -> list[dict]:
    """
    최근 N일치 순위 데이터를 반환.
    반환: [{"date", "keyword", "brand", "rank", "title", "url"}, ...]
    """
    sql = """
        SELECT date, keyword, brand, rank, title, url
        FROM rankings
        WHERE date >= date('now', ?)
        ORDER BY date DESC, keyword ASC
    """
    with _conn() as con:
        rows = con.execute(sql, (f"-{days} days",)).fetchall()
    return [dict(row) for row in rows]


def get_dates() -> list[str]:
    """저장된 날짜 목록 (최신순)."""
    with _conn() as con:
        rows = con.execute(
            "SELECT DISTINCT date FROM rankings ORDER BY date DESC"
        ).fetchall()
    return [row["date"] for row in rows]


def get_pivot(days: int = 14) -> dict:
    """
    키워드 × 날짜 피벗 테이블 반환.
    {
      "dates": ["2025-04-02", ...],           # 최신순
      "rows": [
          {"keyword": "...", "ranks": {"2025-04-02": 3, "2025-04-01": None, ...}},
          ...
      ]
    }
    """
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
