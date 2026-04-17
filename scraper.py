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
    # PostView 형식: PostView.naver?blogId=xxx&logNo=yyy
    if "PostView.naver" in url or "PostView.nhn" in url:
        m = _POSTVIEW_RE.search(url)
        if m:
            return f"https://blog.naver.com/{m.group(1)}/{m.group(2)}"

    # 리다이렉트 형식: blog.naver.com/username?Redirect=Log&logNo=yyy
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
    # logNo= 파라미터 포함 리다이렉트 URL도 포스트로 인정
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
    """헤드리스 Chrome 드라이버를 생성하고 사용 후 종료."""
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
    """네이버 블로그 탭 한 페이지를 Selenium 라이브 DOM으로 파싱.
    page_source 스냅샷은 JS 렌더링 결과를 누락하므로 find_elements를 사용."""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By

    url = (
        f"{NAVER_BLOG_SEARCH_URL}"
        f"?where=blog&query={keyword}"
        f"&sm=tab_jum&nso=so:r,p:all,a:all&start={start}"
    )
    driver.get(url)

    # 실제 블로그 포스트 링크가 DOM에 나타날 때까지 대기
    # (내비게이션의 blog.naver.com 링크와 구별: 포스트 URL에만 숫자 logNo 포함)
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
    """모든 키워드에 대해 블로그 순위를 조회하고 결과 리스트를 반환."""
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
