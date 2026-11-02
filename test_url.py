"""
현재 코드가 어떤 URL로 이동하는지 확인하는 디버그 스크립트
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os

keyword = "인천내성발톱"

profile_dir = os.path.join(os.path.expanduser("~"), "naver_chrome_profile")
options = Options()
options.add_argument(f"--user-data-dir={profile_dir}")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--lang=ko-KR")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
except Exception:
    driver = webdriver.Chrome(options=options)

url = f"https://search.naver.com/search.naver?where=blog&query={keyword}&sm=tab_jum&nso=so:r,p:all,a:all&start=1"
print(f"\n이동할 URL: {url}")
driver.get(url)
time.sleep(3)

print(f"실제 이동된 URL: {driver.current_url}")
print(f"페이지 타이틀: {driver.title}")

# 블로그 결과 링크 확인
from selenium.webdriver.common.by import By
anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='blog.naver.com/']")
print(f"\nblog.naver.com 링크 수: {len(anchors)}")
for a in anchors[:5]:
    print(f"  {a.get_attribute('href')}")

input("\nEnter 누르면 종료...")
driver.quit()
