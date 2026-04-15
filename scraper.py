"""
Selenium으로 네이버 블로그 탭을 실제 브라우저와 동일하게 렌더링하여
키워드 순위를 추출하는 스크레이퍼
"""

import re
import time
import logging
from contextlib import contextmanager

from bs4 import BeautifulSoup

from config import TARGET_BRAND, TARGET_URLS, SEARCH_DEPTH, REQUEST_DELAY, EXCLUDE_KEYWORDS

logger = logging.getLogger(__name__)

NAVER_BLOG_SEARCH_URL = "https://search.naver.com/search.naver"
RESULTS_PER_PAGE = 10

_POSTVIEW_RE = re.compile(r"blogId=([^&]+)&logNo=(\d+)", re.IGNORECASE)


def _normalize_url(url: str) -> str:
    if "PostView.naver" in url or "PostView.nhn" in url:
        m = _POSTVIEW_RE.search(url)
        if m:
            return f"https://blog.naver.com/{m.group(1)}/{m.group(2)}"
    return (
        url.replace("https://m.blog.naver.com/", "https://blog.naver.com/")
           .replace("http://m.blog.naver.com/", "https://blog.naver.com/")
           .split("?")[0]
           .rstrip("/")
    )


_TARGET_URLS_NORMALIZED = {_normalize_url(u) for u in TARGET_URLS}


def _is_post_url(url: str) -> bool:
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
    """네이버 블로그 탭 한 페이지를 Selenium으로 렌더링 후 결과 반환.
    결과 카드(li) 단위로 카운트하여 실제 브라우저 순위와 일치시킴."""
    url = (
        f"{NAVER_BLOG_SEARCH_URL}"
        f"?where=blog&query={keyword}"
        f"&sm=tab_jum&nso=so:r,p:all,a:all&start={start}"
    )
    driver.get(url)
    time.sleep(1.5)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    container = (
        soup.find(id="main_pack")
        or soup.find(id="ct")
        or soup
    )

    items = []
    seen_urls: set[str] = set()

    # 결과 카드(li) 단위로 파싱 — 각 카드에서 대표 포스트 링크 1개만 추출
    result_cards = container.find_all("li", class_=lambda c: c and "bx" in c.split())

    if result_cards:
        for card in result_cards:
            found = False
            for a in card.find_all("a", href=True):
                href = a["href"]
                if "blog.naver.com" not in href:
                    continue
                if not _is_post_url(href):
                    continue
                normalized = _normalize_url(href)
                if normalized in seen_urls:
                    continue
                seen_urls.add(normalized)

                raw_title = a.get_text(" ", strip=True)
                if "blog.naver.com" in raw_title or len(raw_title) < 5:
                    title = ""
                    for tag in card.find_all(["strong", "em", "span", "h2", "h3"]):
                        text = tag.get_text(" ", strip=True)
                        if text and "blog.naver.com" not in text and len(text) > 5:
                            title = text
                            break
                else:
                    title = raw_title

                description = ""
                dsc = card.find(
                    class_=lambda c: c and any(x in c for x in ("dsc", "desc", "text", "summary"))
                )
                if dsc:
                    description = dsc.get_text(" ", strip=True)

                items.append({"title": title, "url": normalized, "description": description})
                found = True
                break  # 카드당 대표 링크 1개만

            if not found:
                # 포스트 링크 없는 카드도 순위 슬롯으로 카운트 (자리 유지)
                items.append({"title": "", "url": "", "description": ""})
    else:
        # 폴백: li.bx 없을 경우 기존 방식
        for a in container.find_all("a", href=True):
            href = a["href"]
            if "blog.naver.com" not in href or not _is_post_url(href):
                continue
            normalized = _normalize_url(href)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            raw_title = a.get_text(" ", strip=True)
            title = "" if "blog.naver.com" in raw_title or len(raw_title) < 5 else raw_title
            items.append({"title": title, "url": normalized, "description": ""})

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
