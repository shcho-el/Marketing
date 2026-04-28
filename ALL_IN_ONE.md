# 네이버 블로그 순위 모니터링 — 전체 설치 가이드

> 네이버 블로그 탭 관련도순 기준, 지정 키워드 상위 20위를 매일 자동 수집 → 슬랙 전송

---

## STEP 1. 폴더 및 파일 준비

아래 경로에 폴더를 만들고, 각 파일을 생성합니다.

```
C:\Users\사용자명\marketing\
├── config.py
├── scraper.py
├── database.py
├── notifier.py
├── scheduler.py
├── main.py
├── test_rank.py
├── .env
└── logs\          ← 빈 폴더 생성
```

---

## STEP 2. 패키지 설치

```powershell
pip install selenium webdriver-manager requests schedule python-dotenv beautifulsoup4
```

---

## STEP 3. .env 파일 생성

`marketing\.env` 파일을 만들고 슬랙 Webhook URL 입력:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

> 슬랙 Webhook URL: Slack 앱 관리 → Incoming Webhooks → 새 Webhook 추가

---

## STEP 4. 코드 파일 생성

아래 내용을 각 파일명으로 저장하세요.

---

### `config.py`

```python
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── 모니터링 키워드 ───────────────────────────────────────────────
KEYWORDS = [
    "송도내성발톱",
    "인천내성발톱",
    "인천문제성발톱",
    "송도문제성발톱",
    "인천내성발톱병원",
    "인천발톱무좀",
    "인천발톱무좀병원",
    "송도발톱무좀",
    "송도발톱무좀병원",
    "문제성발톱병원",
    "문제성발톱",
    "인천문제성발톱병원",
]

TARGET_BRAND = "오블리브"  # 슬랙/DB 표시용

# ── 우리 브랜드 블로그 포스트 URL ───────────────────────────────
TARGET_URLS = [
    "https://blog.naver.com/아이디/포스트번호",
    # 형식: https://blog.naver.com/블로그아이디/포스트번호
    # m.blog.naver.com 또는 PostView 형식도 자동 변환됨
]

# ── 경쟁사 제외 키워드 ──────────────────────────────────────────
# 포스트 제목/설명에 이 단어가 있으면 경쟁사로 간주하여 제외
EXCLUDE_KEYWORDS = [
    "경쟁사명1",
    "경쟁사명2",
]

# ── URL 매칭 실패 시 보조 브랜드명 ─────────────────────────────
BRAND_ALIASES = [
    "오블리브",
    "오블리브의원",
]

SEARCH_DEPTH = 20        # 상위 몇 위까지 확인
RESULTS_PER_PAGE = 10    # 네이버 블로그 탭 1페이지 결과 수
REQUEST_DELAY = 1.0      # 요청 간 딜레이(초) - 차단 방지
DB_PATH = "rankings.db"
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
SCHEDULE_TIME = "08:20"  # 매일 자동 수집 시각 (24시간)
```

---

### `scraper.py`

```python
"""
Selenium으로 네이버 블로그 탭을 실제 브라우저와 동일하게 렌더링하여
키워드 순위를 추출하는 스크레이퍼
"""

import re
import time
import logging
from contextlib import contextmanager

from config import TARGET_BRAND, TARGET_URLS, SEARCH_DEPTH, REQUEST_DELAY, EXCLUDE_KEYWORDS

logger = logging.getLogger(__name__)

NAVER_BLOG_SEARCH_URL = "https://search.naver.com/search.naver"
RESULTS_PER_PAGE = 10

_POSTVIEW_RE = re.compile(r"blogId=([^&]+)&logNo=(\d+)", re.IGNORECASE)
_LOGNO_RE = re.compile(r"logNo=(\d+)", re.IGNORECASE)
_BLOGID_PATH_RE = re.compile(r"blog\.naver\.com/([^/?]+)", re.IGNORECASE)


def _normalize_url(url: str) -> str:
    if "PostView.naver" in url or "PostView.nhn" in url:
        m = _POSTVIEW_RE.search(url)
        if m:
            return f"https://blog.naver.com/{m.group(1)}/{m.group(2)}"
    if "logNo=" in url and "blog.naver.com" in url:
        bid = _BLOGID_PATH_RE.search(url)
        lno = _LOGNO_RE.search(url)
        if bid and lno:
            return f"https://blog.naver.com/{bid.group(1)}/{lno.group(1)}"
    return (
        url.replace("https://m.blog.naver.com/", "https://blog.naver.com/")
           .replace("http://m.blog.naver.com/", "https://blog.naver.com/")
           .replace("http://blog.naver.com/", "https://blog.naver.com/")
           .split("?")[0]
           .rstrip("/")
    )


_TARGET_URLS_NORMALIZED = {_normalize_url(u) for u in TARGET_URLS}


def _is_post_url(url: str) -> bool:
    if "logNo=" in url and "blog.naver.com" in url:
        return bool(_LOGNO_RE.search(url))
    normalized = _normalize_url(url)
    parts = normalized.replace("https://blog.naver.com/", "").split("/")
    return len(parts) == 2 and parts[1].isdigit() and len(parts[1]) > 6


def _contains_brand(result: dict) -> bool:
    return result.get("url", "") in _TARGET_URLS_NORMALIZED


def _is_excluded(result: dict) -> bool:
    text = result.get("title", "") + " " + result.get("description", "")
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


@contextmanager
def _browser():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--lang=ko-KR")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options,
            )
        except Exception:
            driver = webdriver.Chrome(options=options)

        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        yield driver
    finally:
        if driver:
            driver.quit()


def _scrape_blog_page(driver, keyword: str, start: int = 1) -> list[dict]:
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.by import By

    url = (
        f"{NAVER_BLOG_SEARCH_URL}"
        f"?where=blog&query={keyword}"
        f"&sm=tab_jum&nso=so:r,p:all,a:all&start={start}"
    )
    driver.get(url)

    def _post_links_loaded(d):
        elems = d.find_elements(By.CSS_SELECTOR, "a[href*='blog.naver.com/']")
        for e in elems[:30]:
            href = e.get_attribute("href") or ""
            if _is_post_url(href):
                return True
        return False

    try:
        WebDriverWait(driver, 15).until(_post_links_loaded)
        time.sleep(0.5)
    except Exception:
        time.sleep(5.0)

    items = []
    seen_urls: set[str] = set()

    try:
        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='blog.naver.com/']")
    except Exception:
        logger.warning("Selenium find_elements 실패: %s (start=%d)", keyword, start)
        return []

    for a_elem in anchors:
        try:
            href = a_elem.get_attribute("href") or ""
        except Exception:
            continue
        if not href or not _is_post_url(href):
            continue
        normalized = _normalize_url(href)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        try:
            title = a_elem.text.strip()
            if not title or len(title) < 5 or "blog.naver.com" in title:
                title = ""
        except Exception:
            title = ""
        items.append({"title": title, "url": normalized, "description": ""})

    logger.debug("페이지 수집: %s start=%d → %d개", keyword, start, len(items))
    return items


def get_brand_rank(keyword: str, driver=None, brand: str = TARGET_BRAND, depth: int = SEARCH_DEPTH) -> dict:
    matched_ranks = []
    matched_title = ""
    matched_url = ""
    global_rank = 0
    page_start = 1
    seen_urls: set[str] = set()

    while global_rank < depth:
        items = _scrape_blog_page(driver, keyword, start=page_start)
        if not items:
            break
        new_items = [it for it in items if it["url"] not in seen_urls]
        if not new_items:
            break
        for item in new_items:
            if global_rank >= depth:
                break
            seen_urls.add(item["url"])
            global_rank += 1
            if _contains_brand(item) and not _is_excluded(item):
                if not matched_ranks:
                    matched_title = item["title"]
                    matched_url = item["url"]
                matched_ranks.append(global_rank)
        page_start += RESULTS_PER_PAGE
        if global_rank < depth and new_items:
            time.sleep(REQUEST_DELAY)

    return {
        "keyword": keyword,
        "brand": brand,
        "rank": matched_ranks[0] if matched_ranks else None,
        "ranks": matched_ranks,
        "popular_rank": None,
        "popular_ranks": [],
        "title": matched_title,
        "url": matched_url,
        "checked_count": global_rank,
    }


def run_all_keywords(keywords: list[str]) -> list[dict]:
    results = []
    with _browser() as driver:
        for i, keyword in enumerate(keywords):
            logger.info("[%d/%d] 키워드 조회 중: %s", i + 1, len(keywords), keyword)
            result = get_brand_rank(keyword, driver=driver)
            results.append(result)
            ranks = result.get("ranks", [])
            ranks_str = ", ".join(f"{r}위" for r in ranks) if ranks else "미노출"
            logger.info("  -> 블로그: %s", ranks_str)
            if i < len(keywords) - 1:
                time.sleep(REQUEST_DELAY)
    return results
```

---

### `database.py`

```python
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
    with _conn() as con:
        con.execute(CREATE_TABLE_SQL)
        con.execute(CREATE_INDEX_SQL)
        cols = [r[1] for r in con.execute("PRAGMA table_info(rankings)").fetchall()]
        for col in ["ranks_all", "popular_rank", "popular_ranks_all"]:
            if col not in cols:
                typ = "INTEGER" if col == "popular_rank" else "TEXT DEFAULT ''"
                con.execute(f"ALTER TABLE rankings ADD COLUMN {col} {typ}")
    logger.info("DB 초기화 완료: %s", DB_PATH)

def save_results(results: list[dict], check_date: date | None = None) -> None:
    if check_date is None:
        check_date = date.today()
    sql = """
        INSERT INTO rankings
            (date, keyword, brand, rank, ranks_all, popular_rank, popular_ranks_all,
             title, url, checked_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, keyword, brand) DO UPDATE SET
            rank=excluded.rank, ranks_all=excluded.ranks_all,
            popular_rank=excluded.popular_rank, popular_ranks_all=excluded.popular_ranks_all,
            title=excluded.title, url=excluded.url,
            checked_count=excluded.checked_count, created_at=excluded.created_at
    """
    with _conn() as con:
        for r in results:
            con.execute(sql, (
                check_date.isoformat(), r["keyword"], r["brand"],
                r.get("rank"), json.dumps(r.get("ranks", []), ensure_ascii=False),
                r.get("popular_rank"), json.dumps(r.get("popular_ranks", []), ensure_ascii=False),
                r.get("title", ""), r.get("url", ""), r.get("checked_count", 0),
                datetime.now().isoformat(timespec="seconds"),
            ))
    logger.info("%d건 저장 완료 (날짜: %s)", len(results), check_date)
```

---

### `notifier.py`

```python
import os
import logging
from datetime import date
import requests

logger = logging.getLogger(__name__)

def _get_webhook_url() -> str:
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        raise EnvironmentError("SLACK_WEBHOOK_URL 환경변수가 설정되지 않았습니다.")
    return url

def _rank_emoji(rank) -> str:
    if rank is None: return "⬜"
    if rank == 1:    return "🥇"
    if rank == 2:    return "🥈"
    if rank == 3:    return "🥉"
    if rank <= 5:    return "🟢"
    if rank <= 10:   return "🟡"
    return "🔴"

def _build_message(results: list[dict], check_date: date) -> dict:
    lines = []
    for r in results:
        kw = r["keyword"]
        blog_ranks = r.get("ranks") or ([r["rank"]] if r.get("rank") else [])
        if blog_ranks:
            emoji = _rank_emoji(blog_ranks[0])
            rank_str = ", ".join(f"{rk}위" for rk in blog_ranks)
        else:
            emoji = "⬜"
            rank_str = "미노출"
        lines.append(f"{emoji}  `{kw}`  →  *{rank_str}*")

    date_str = check_date.strftime("%Y년 %m월 %d일")
    return {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text",
                "text": f"📊 네이버 블로그 순위 ({date_str})", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
            {"type": "divider"},
            {"type": "context", "elements": [
                {"type": "mrkdwn", "text": "네이버 블로그 탭 기준 상위 20위"}
            ]},
        ]
    }

def send_slack(results: list[dict], check_date: date | None = None) -> bool:
    if check_date is None:
        check_date = date.today()
    try:
        webhook_url = _get_webhook_url()
    except EnvironmentError as e:
        logger.warning("슬랙 전송 건너뜀: %s", e)
        return False
    payload = _build_message(results, check_date)
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("슬랙 전송 완료")
            return True
        logger.warning("슬랙 전송 실패: %s %s", resp.status_code, resp.text)
        return False
    except requests.RequestException as e:
        logger.warning("슬랙 전송 오류: %s", e)
        return False
```

---

### `scheduler.py`

```python
import logging
import schedule
import time
from datetime import date
from config import KEYWORDS, SCHEDULE_TIME
from scraper import run_all_keywords
from database import init_db, save_results
from notifier import send_slack

logger = logging.getLogger(__name__)

def collect_once() -> None:
    today = date.today()
    logger.info("===== 순위 수집 시작 (%s) =====", today)
    try:
        results = run_all_keywords(KEYWORDS)
        save_results(results)
        send_slack(results, check_date=today)
        logger.info("===== 순위 수집 완료 =====")
    except Exception as e:
        logger.exception("순위 수집 중 오류: %s", e)

def run_scheduler() -> None:
    init_db()
    collect_once()
    for day in [schedule.every().monday, schedule.every().tuesday,
                schedule.every().wednesday, schedule.every().thursday,
                schedule.every().friday]:
        day.at(SCHEDULE_TIME).do(collect_once)
    logger.info("스케줄러 등록: 평일(월~금) %s 자동 수집", SCHEDULE_TIME)
    while True:
        schedule.run_pending()
        time.sleep(60)
```

---

### `main.py`

```python
"""
사용법:
  python main.py collect      # 즉시 1회 수집 + 슬랙 전송
  python main.py scheduler    # 매일 자동 수집 (백그라운드)
  python main.py dashboard    # 웹 대시보드 (http://localhost:5000)
"""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/collect.log", encoding="utf-8"),
    ],
)

def cmd_collect():
    from database import init_db, save_results
    from scraper import run_all_keywords
    from notifier import send_slack
    from config import KEYWORDS
    from datetime import date

    init_db()
    results = run_all_keywords(KEYWORDS)
    save_results(results)
    send_slack(results, check_date=date.today())

    print("\n===== 수집 결과 =====")
    for r in results:
        ranks = r.get("ranks", [])
        rank_str = ", ".join(f"{rk}위" for rk in ranks) if ranks else "미노출"
        print(f"  {r['keyword']:<20} → {rank_str}")
        if r.get("url"):
            print(f"    URL: {r['url']}")
    print("====================\n")

def cmd_scheduler():
    from scheduler import run_scheduler
    run_scheduler()

COMMANDS = {"collect": cmd_collect, "scheduler": cmd_scheduler}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
```

---

### `test_rank.py` (디버그용)

```python
"""
키워드별 순위 디버그 출력 (슬랙 전송 없음)
사용법: python test_rank.py 송도내성발톱 20
"""
import sys
import time
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scraper import _scrape_blog_page, _browser, _TARGET_URLS_NORMALIZED, RESULTS_PER_PAGE
from config import EXCLUDE_KEYWORDS, REQUEST_DELAY

def test_keyword(keyword: str, depth: int = 20):
    print(f"\n{'='*70}")
    print(f"  키워드: [{keyword}]  상위 {depth}위")
    print(f"{'='*70}")
    print(f"{'순위':>4}  {'구분':^6}  {'제목':<35}  URL")
    print(f"{'-'*110}")

    with _browser() as driver:
        global_rank = 0
        page_start = 1
        seen_urls: set = set()

        while global_rank < depth:
            items = _scrape_blog_page(driver, keyword, start=page_start)
            if not items:
                print("  (결과 없음)")
                break
            new_items = [it for it in items if it["url"] not in seen_urls]
            if not new_items:
                print(f"  (더 이상 새 결과 없음, 총 {global_rank}개)")
                break
            for item in new_items:
                if global_rank >= depth:
                    break
                seen_urls.add(item["url"])
                global_rank += 1
                is_match = item["url"] in _TARGET_URLS_NORMALIZED
                excluded = any(kw in item["title"] for kw in EXCLUDE_KEYWORDS)
                tag = ("제외" if excluded else "★우리") if is_match else ""
                title = item["title"][:33] if item["title"] else "(제목없음)"
                print(f"{global_rank:>4}  {tag:^6}  {title:<35}  {item['url']}")
            page_start += RESULTS_PER_PAGE
            if global_rank < depth and new_items:
                time.sleep(REQUEST_DELAY)
    print(f"{'='*70}\n")

if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "키워드입력"
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    test_keyword(keyword, depth)
```

---

## STEP 5. Windows 자동화 (Task Scheduler)

**관리자 PowerShell**에서 실행:

```powershell
# Python 경로 확인
where python

# 작업 등록
Unregister-ScheduledTask -TaskName "NaverBlogRankCollect" -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "여기에_python_전체경로" `
    -Argument "main.py collect" `
    -WorkingDirectory "C:\Users\사용자명\marketing"

$trigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "08:20AM"

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "NaverBlogRankCollect" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force
```

### 즉시 테스트

```powershell
Start-ScheduledTask -TaskName "NaverBlogRankCollect"
# 잠시 후 슬랙 확인

# 결과 확인
Get-ScheduledTaskInfo -TaskName "NaverBlogRankCollect"
# LastTaskResult: 0 = 성공, 1 = 실패
```

---

## STEP 6. 수동 실행 및 디버그

```powershell
cd C:\Users\사용자명\marketing

# 즉시 수집 + 슬랙 전송
python main.py collect

# 특정 키워드만 순위 확인 (슬랙 전송 없음)
python test_rank.py 송도내성발톱 20
```

---

## 슬랙 알림 형식

```
📊 네이버 블로그 순위 (2026년 04월 21일)

🥇  `송도내성발톱`  →  *1위*
🟢  `인천내성발톱`  →  *4위, 7위*
⬜  `인천발톱무좀`  →  *미노출*

네이버 블로그 탭 기준 상위 20위
```

| 이모지 | 순위 |
|--------|------|
| 🥇🥈🥉 | 1·2·3위 |
| 🟢 | 4~5위 |
| 🟡 | 6~10위 |
| 🔴 | 11위 이상 |
| ⬜ | 미노출 |

---

## 자주 수정하는 항목 (config.py)

| 항목 | 설명 |
|------|------|
| `KEYWORDS` | 모니터링할 검색 키워드 추가/삭제 |
| `TARGET_URLS` | 우리 브랜드 블로그 포스트 URL 추가/삭제 |
| `EXCLUDE_KEYWORDS` | 경쟁사 이름 추가/삭제 |
| `SEARCH_DEPTH` | 몇 위까지 확인할지 (기본 20) |
| `SCHEDULE_TIME` | 자동 실행 시각 (기본 `"08:20"`) |
| `TARGET_BRAND` | 슬랙에 표시될 브랜드명 |
