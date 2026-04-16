"""
디버그 스크립트 - 네이버 블로그 검색 HTML 저장 및 선택자 검사

사용법:
  python debug_scraper.py 송도내성발톱
"""
import sys
import time
from pathlib import Path
from bs4 import BeautifulSoup
from scraper import _browser, NAVER_BLOG_SEARCH_URL, _normalize_url, _is_post_url


def dump_debug(keyword: str):
    url = (
        f"{NAVER_BLOG_SEARCH_URL}"
        f"?where=blog&query={keyword}"
        f"&sm=tab_jum&nso=so:r,p:all,a:all&start=1"
    )
    print(f"URL: {url}")
    print("브라우저 시작 중...")

    with _browser() as driver:
        driver.get(url)

        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#main_pack li, #ct li, body")
                )
            )
        except Exception:
            pass
        time.sleep(3)

        html = driver.page_source
        safe_kw = keyword.replace(" ", "_")
        out_path = Path(f"debug_{safe_kw}.html")
        out_path.write_text(html, encoding="utf-8")
        print(f"\nHTML 저장: {out_path.absolute()} ({len(html):,} bytes)")

        soup = BeautifulSoup(html, "html.parser")

        print("\n=== 선택자 검사 ===")
        main_pack = soup.find(id="main_pack")
        ct = soup.find(id="ct")
        print(f"#main_pack: {'있음' if main_pack else '없음'}")
        print(f"#ct: {'있음' if ct else '없음'}")

        container = main_pack or ct or soup

        li_bx = container.find_all("li", class_=lambda c: c and "bx" in c.split())
        print(f"li.bx: {len(li_bx)}개")

        lst = container.find("ul", class_=lambda c: c and "lst_total" in (c or "").split())
        print(f"ul.lst_total: {'있음' if lst else '없음'}", end="")
        if lst:
            li_in_lst = lst.find_all("li", recursive=False)
            print(f" → li 개수: {len(li_in_lst)}")
        else:
            print()

        total_wrap = container.find_all("div", class_=lambda c: c and "total_wrap" in (c or ""))
        print(f".total_wrap: {len(total_wrap)}개")

        api_bx = container.find_all(
            ["li", "div"], class_=lambda c: c and "api_subject_bx" in (c or "")
        )
        print(f".api_subject_bx: {len(api_bx)}개")

        # li.bx 카드 내부 링크 분석
        print(f"\n=== li.bx 카드 내부 a 태그 분석 ===")
        for i, card in enumerate(li_bx):
            print(f"\n--- card {i+1} ---")
            for a in card.find_all("a"):
                href = a.get("href", "(없음)")
                onclick = a.get("onclick", "")
                data_url = a.get("data-url", "")
                text = a.get_text(" ", strip=True)[:40]
                print(f"  href={href[:100]}  text={text}")
                if onclick:
                    print(f"     onclick={onclick[:120]}")
                if data_url:
                    print(f"     data-url={data_url[:120]}")

        # data 속성에서 blog.naver.com 또는 logNo 검색
        print(f"\n=== 모든 요소 data-* 속성 중 blog/logNo 포함 ===")
        found_data = 0
        for elem in soup.find_all(True):
            for attr, val in elem.attrs.items():
                if not isinstance(val, str):
                    continue
                if ("blog.naver.com" in val or "logNo" in val) and attr != "href":
                    print(f"  <{elem.name}> {attr}={val[:120]}")
                    found_data += 1
        if not found_data:
            print("  (없음)")

        # Selenium DOM에서 직접 a 태그 href 확인
        print(f"\n=== Selenium DOM: blog.naver.com 포함 링크 ===")
        from selenium.webdriver.common.by import By
        all_anchors = driver.find_elements(By.TAG_NAME, "a")
        sel_found = 0
        for a in all_anchors:
            try:
                href = a.get_attribute("href") or ""
                data_url = a.get_attribute("data-url") or ""
                if "blog.naver.com" in href or "blog.naver.com" in data_url:
                    print(f"  href={href[:100]}")
                    if data_url:
                        print(f"     data-url={data_url[:100]}")
                    sel_found += 1
            except Exception:
                pass
        if not sel_found:
            print("  (없음)")

        print(f"\n=== 페이지 제목 ===")
        title_tag = soup.find("title")
        print(f"  {title_tag.get_text() if title_tag else '(없음)'}")


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "송도내성발톱"
    dump_debug(keyword)
