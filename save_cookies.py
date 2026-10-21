"""
네이버 로그인 쿠키 저장 스크립트

사용법:
  python save_cookies.py

브라우저가 열리면 네이버에 로그인하세요.
로그인 완료 후 Enter를 누르면 쿠키가 저장됩니다.
"""
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

COOKIE_FILE = Path("naver_cookies.json")


def save_naver_cookies():
    options = Options()
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

        driver.get("https://naver.com")
        print("\n브라우저가 열렸습니다.")
        print("네이버에 로그인하세요.")
        print("\n로그인 완료 후 여기서 Enter를 누르세요...", end="", flush=True)
        input()

        cookies = driver.get_cookies()
        COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n쿠키 저장 완료: {COOKIE_FILE.absolute()} ({len(cookies)}개)")

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    save_naver_cookies()
