# -*- coding: utf-8 -*-
"""
환경 점검 — 무엇이 준비됐고 무엇이 빠졌는지 한 번에 보여 준다.

  python main.py doctor

"왜 안 되지"를 매번 추적하는 대신, 실행 전에 여기서 확인합니다.
"""

import importlib
import os
import platform
import sys

OK, WARN, BAD = "ok", "warn", "bad"
MARK = {OK: "✅", WARN: "⚠️ ", BAD: "❌"}


def _row(state, label, detail="", fix=""):
    return {"state": state, "label": label, "detail": detail, "fix": fix}


def check_python():
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if v < (3, 9):
        return _row(BAD, "파이썬 버전", ver, "3.9 이상이 필요합니다.")
    return _row(OK, "파이썬 버전", f"{ver} ({platform.system()})")


def check_packages():
    rows = []
    required = [
        ("flask", "웹 화면"),
        ("anthropic", "원고 생성"),
        ("PIL", "썸네일"),
        ("selenium", "CMS 업로드"),
        ("dotenv", ".env 읽기"),
    ]
    optional = [("webdriver_manager", "크롬 드라이버 자동 설치"),
                ("bs4", "테스트"), ("schedule", "순위 수집 스케줄러")]

    for mod, why in required:
        try:
            importlib.import_module(mod)
            rows.append(_row(OK, f"{mod}", why))
        except ImportError:
            rows.append(_row(BAD, f"{mod} 없음", why,
                             "pip install -r requirements.txt"))
    for mod, why in optional:
        try:
            importlib.import_module(mod)
            rows.append(_row(OK, f"{mod}", why))
        except ImportError:
            rows.append(_row(WARN, f"{mod} 없음", why + " (선택)",
                             "pip install -r requirements.txt"))
    return rows


def check_env_file():
    if os.path.exists(".env"):
        return _row(OK, ".env 파일", os.path.abspath(".env"))
    return _row(BAD, ".env 파일 없음", "",
                "copy .env.example .env  (맥/리눅스: cp .env.example .env)")


def check_api_key():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return _row(WARN, "ANTHROPIC_API_KEY 없음", "원고 생성 불가 (검사·미리보기는 동작)",
                    ".env에 키를 넣으세요. https://console.anthropic.com")
    if not key.startswith("sk-ant-"):
        return _row(WARN, "ANTHROPIC_API_KEY 형식 확인", f"{key[:10]}…",
                    "보통 sk-ant- 로 시작합니다.")
    return _row(OK, "ANTHROPIC_API_KEY", f"{key[:12]}…")


def check_webapp():
    rows = []
    if os.getenv("APP_PASSWORD"):
        rows.append(_row(OK, "웹앱 비밀번호", "설정됨"))
    else:
        rows.append(_row(WARN, "웹앱 비밀번호 없음", "같은 네트워크면 누구나 접속",
                         ".env에 APP_PASSWORD를 넣으세요."))
    if os.getenv("APP_SECRET"):
        rows.append(_row(OK, "세션 키", "설정됨"))
    else:
        rows.append(_row(WARN, "세션 키 없음", "재시작하면 로그인이 풀립니다",
                         ".env에 APP_SECRET을 아무 긴 문자열로 넣으세요."))
    return rows


def check_clinic():
    try:
        from content import clinic
    except Exception as exc:
        return [_row(BAD, "병원 프로필 로드 실패", str(exc)[:60])]
    nap = clinic.nap_completeness()
    if nap["complete"]:
        return [_row(OK, "병원 기본정보(NAP)", "완비")]
    return [_row(WARN, "병원 기본정보 누락", ", ".join(nap["missing"]),
                 ".env에 채우면 JSON-LD와 지역 검색에 반영되고 GEO 점수가 오릅니다.")]


def check_service():
    try:
        from content import services

        svc = services.current()
        return _row(OK, "진료 분야", f"{services.ACTIVE} — {svc['label']}")
    except Exception as exc:
        return _row(BAD, "진료 분야 설정", str(exc).splitlines()[0][:70],
                    "content/services.py를 확인하세요.")


def check_thumbnail():
    rows = []
    try:
        from publisher import thumbnail
    except Exception as exc:
        return [_row(BAD, "썸네일 모듈", str(exc)[:60])]

    try:
        rows.append(_row(OK, "한글 폰트", os.path.basename(thumbnail._find_font(True))))
    except Exception as exc:
        rows.append(_row(BAD, "한글 폰트 없음", str(exc).splitlines()[0][:70],
                         ".env에 THUMB_FONT_KO=폰트파일경로"))

    logo = thumbnail.logo_status()
    rows.append(_row(OK if logo["ok"] else WARN, "썸네일 로고",
                     logo["message"].splitlines()[0][:80]))

    photos = thumbnail.list_photos()
    if photos:
        rows.append(_row(OK, "배경 사진", f"{len(photos)}장 ({thumbnail.PHOTO_DIR})"))
    else:
        rows.append(_row(WARN, "배경 사진 없음", thumbnail.PHOTO_DIR,
                         "사진을 넣지 않으면 단색 배경으로 만들어집니다."))
    return rows


def check_cms():
    rows = []
    try:
        from publisher import config as cms
    except Exception as exc:
        return [_row(BAD, "CMS 설정 로드 실패", str(exc)[:60])]

    if cms.USERNAME and cms.PASSWORD:
        rows.append(_row(OK, "CMS 로그인 정보", cms.USERNAME))
    else:
        rows.append(_row(WARN, "CMS 로그인 정보 없음", "자동 업로드 불가",
                         ".env에 CMS_USERNAME / CMS_PASSWORD"))

    if cms.has_mapping():
        try:
            mapping = cms.load_mapping()
            rows.append(_row(OK, "CMS 폼 매핑", f"{len(mapping['fields'])}개 필드"))
        except Exception as exc:
            rows.append(_row(WARN, "CMS 폼 매핑 불완전",
                             str(exc).splitlines()[0][:70],
                             "python main.py inspect-cms 를 다시 실행하세요."))
    else:
        rows.append(_row(WARN, "CMS 폼 매핑 없음", cms.MAPPING_PATH,
                         "python main.py inspect-cms"))
    return rows


def check_driver():
    """크롬 드라이버가 실제로 뜨는지 본다. CMS 업로드의 전제 조건."""
    try:
        from selenium import webdriver  # noqa: F401
    except ImportError:
        return _row(WARN, "크롬 드라이버", "selenium 미설치로 확인 생략")

    from publisher import config as cms

    if cms.CHROMEDRIVER_PATH:
        exists = os.path.exists(cms.CHROMEDRIVER_PATH)
        return _row(OK if exists else BAD, "크롬 드라이버 경로",
                    cms.CHROMEDRIVER_PATH,
                    "" if exists else "CHROMEDRIVER_PATH 경로에 파일이 없습니다.")
    return _row(WARN, "크롬 드라이버", "자동 탐지 사용",
                "업로드가 안 되면 python test_cms_e2e.py 로 확인하세요.")


def run() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    sections = [
        ("실행 환경", [check_python(), check_env_file(), check_api_key()] + check_webapp()),
        ("패키지", check_packages()),
        ("콘텐츠 설정", [check_service()] + check_clinic()),
        ("썸네일", check_thumbnail()),
        ("CMS 업로드", check_cms() + [check_driver()]),
    ]

    print("\n" + "=" * 60)
    print("  환경 점검")
    print("=" * 60)

    bad = warn = 0
    for title, rows in sections:
        print(f"\n[{title}]")
        for r in rows:
            bad += r["state"] == BAD
            warn += r["state"] == WARN
            line = f"  {MARK[r['state']]} {r['label']}"
            if r["detail"]:
                line += f" — {r['detail']}"
            print(line)
            if r["fix"] and r["state"] != OK:
                print(f"       → {r['fix']}")

    print("\n" + "=" * 60)
    if bad:
        print(f"  해결해야 할 문제 {bad}건" + (f", 확인 권장 {warn}건" if warn else ""))
        print("  위 → 표시된 방법대로 조치한 뒤 다시 실행하세요.")
    elif warn:
        print(f"  실행에는 지장 없습니다. 확인 권장 {warn}건")
        print("  원고 생성과 검사는 지금 바로 쓸 수 있습니다.")
    else:
        print("  모두 준비됐습니다.")
    print("=" * 60 + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(run())
