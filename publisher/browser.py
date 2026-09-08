# -*- coding: utf-8 -*-
"""
Selenium 드라이버 생성과 CMS 로그인.

레거시 PHP 관리자 페이지는 세션 쿠키·CSRF 토큰·파일 업로드가 얽혀 있어
requests로 재현하기보다 실제 브라우저를 띄우는 쪽이 안정적입니다.
기존 scraper.py와 같은 드라이버 설정 방식을 씁니다.
"""

import logging
import time
from contextlib import contextmanager

from publisher import config

logger = logging.getLogger(__name__)


class BrowserError(RuntimeError):
    pass


class LoginError(RuntimeError):
    pass


@contextmanager
def driver(headless: bool = None):
    """Chrome 드라이버를 만들고 사용 후 종료한다."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    headless = config.HEADLESS if headless is None else headless

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--lang=ko-KR")
    options.add_argument("--window-size=1440,1000")

    # 브라우저 실행 파일을 직접 지정해야 하는 환경이 있다.
    # (크로미움을 별도 경로에 두었거나, 여러 버전이 깔려 있는 경우)
    if config.CHROME_BINARY:
        options.binary_location = config.CHROME_BINARY

    drv = None
    try:
        from selenium.webdriver.chrome.service import Service

        # 1) 드라이버 경로를 직접 지정한 경우가 가장 확실하다.
        if config.CHROMEDRIVER_PATH:
            drv = webdriver.Chrome(
                service=Service(config.CHROMEDRIVER_PATH), options=options
            )
        else:
            # 2) webdriver-manager가 브라우저 버전에 맞는 드라이버를 받아 온다.
            try:
                from webdriver_manager.chrome import ChromeDriverManager

                drv = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()), options=options
                )
            except Exception as exc:
                logger.debug("webdriver-manager 실패, 기본 경로로 재시도: %s", exc)
                # 3) 마지막으로 Selenium이 알아서 찾게 둔다.
                drv = webdriver.Chrome(options=options)

        drv.set_page_load_timeout(config.TIMEOUT + 20)
    except Exception as exc:
        # 여기까지가 '드라이버 시작'이다. 그 뒤에 난 오류를 이 문구로 덮으면
        # 엉뚱한 곳을 뒤지게 된다.
        if drv:
            drv.quit()
        raise BrowserError(
            f"크롬 드라이버를 시작하지 못했습니다: {exc}\n\n"
            "다음을 확인하세요.\n"
            "  1. 크롬(또는 엣지)이 설치되어 있는지\n"
            "  2. 크롬 버전과 드라이버 버전이 맞는지 "
            "(chrome://version 에서 확인)\n"
            "  3. 자동 설치가 막힌 환경이면 .env에 경로를 직접 지정\n"
            "       CHROMEDRIVER_PATH=드라이버 실행파일 경로\n"
            "       CHROME_BINARY=크롬 실행파일 경로\n"
            "     드라이버는 pip install chromedriver-py 로도 받을 수 있습니다."
        ) from exc

    try:
        yield drv
    finally:
        drv.quit()


def _find_login_form(drv):
    """현재 페이지에서 아이디/비밀번호 입력칸을 찾는다."""
    from selenium.webdriver.common.by import By

    pw_fields = drv.find_elements(By.CSS_SELECTOR, "input[type='password']")
    if not pw_fields:
        return None, None, None

    pw = pw_fields[0]

    # 비밀번호 칸과 같은 form 안에서 앞쪽 text 입력칸을 아이디로 본다.
    try:
        form = pw.find_element(By.XPATH, "./ancestor::form[1]")
        scope = form
    except Exception:
        scope = drv

    candidates = scope.find_elements(
        By.CSS_SELECTOR, "input[type='text'], input[type='email'], input:not([type])"
    )
    user = candidates[0] if candidates else None

    submit = None
    for sel in (
        "button[type='submit']",
        "input[type='submit']",
        "input[type='image']",
        "button",
    ):
        hits = scope.find_elements(By.CSS_SELECTOR, sel)
        if hits:
            submit = hits[0]
            break

    return user, pw, submit


def is_logged_in(drv) -> bool:
    """로그인 상태인지 판단한다 - 비밀번호 입력칸이 없으면 통과로 본다."""
    from selenium.webdriver.common.by import By

    return not drv.find_elements(By.CSS_SELECTOR, "input[type='password']")


def login(drv) -> None:
    """CMS에 로그인한다. 이미 로그인 상태면 아무 것도 하지 않는다."""
    username, password = config.credentials()

    start_url = config.LOGIN_URL or config.WRITE_URL
    logger.info("CMS 접속: %s", start_url)
    drv.get(start_url)
    time.sleep(config.STEP_DELAY)

    if is_logged_in(drv):
        logger.info("이미 로그인된 상태입니다.")
        return

    user_el, pw_el, submit_el = _find_login_form(drv)
    if not pw_el:
        raise LoginError(
            f"로그인 폼을 찾지 못했습니다. 현재 URL: {drv.current_url}\n"
            "CMS_LOGIN_URL을 .env에 직접 지정해 보세요."
        )
    if not user_el:
        raise LoginError("아이디 입력칸을 찾지 못했습니다.")

    user_el.clear()
    user_el.send_keys(username)
    pw_el.clear()
    pw_el.send_keys(password)

    if submit_el:
        submit_el.click()
    else:
        from selenium.webdriver.common.keys import Keys

        pw_el.send_keys(Keys.ENTER)

    time.sleep(config.STEP_DELAY * 3)

    # 로그인 후 글쓰기 페이지로 이동해 최종 확인
    if drv.current_url.rstrip("/") != config.WRITE_URL.rstrip("/"):
        drv.get(config.WRITE_URL)
        time.sleep(config.STEP_DELAY * 2)

    if not is_logged_in(drv):
        raise LoginError(
            "로그인에 실패했습니다. CMS_USERNAME / CMS_PASSWORD를 확인하세요. "
            f"(현재 URL: {drv.current_url})"
        )
    logger.info("로그인 성공")
