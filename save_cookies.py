"""
네이버 로그인 쿠키 저장 스크립트

사용법:
  python save_cookies.py

브라우저가 열리면 네이버에 로그인하세요.
로그인 완료 후 Enter를 누르면 쿠키가 저장됩니다.
"""
import json
from pathlib import Path
import undetected_chromedriver as uc

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

COOKIE_FILE = Path("naver_cookies.json")


def save_naver_cookies():
    import os
    profile_dir = os.path.join(os.path.expanduser("~"), "naver_chrome_profile")

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--lang=ko-KR")

    driver = None
    try:
        driver = uc.Chrome(options=options, headless=False)

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
