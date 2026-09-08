# -*- coding: utf-8 -*-
"""
CMS 접속 정보와 셀렉터 매핑.

셀렉터를 코드에 하드코딩하지 않습니다.
`python main.py inspect-cms`가 실제 폼을 훑어 만든 매핑 파일을 읽습니다.
CMS 화면이 바뀌면 inspector만 다시 돌리면 됩니다.

로그인 정보는 반드시 .env에 두고 저장소에 커밋하지 마십시오.
"""

import json
import logging
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ── 접속 정보 ────────────────────────────────────────────────────────
WRITE_URL = os.getenv("CMS_WRITE_URL", "https://blog.obliv.kr/blogmanage/nxt-blog.php")
LOGIN_URL = os.getenv("CMS_LOGIN_URL", "")  # 비우면 WRITE_URL 접속 후 리다이렉트를 따라감
USERNAME = os.getenv("CMS_USERNAME", "")
PASSWORD = os.getenv("CMS_PASSWORD", "")

# 매핑 파일 경로
MAPPING_PATH = os.getenv("CMS_MAPPING_PATH", "cms_mapping.json")
DUMP_PATH = os.getenv("CMS_DUMP_PATH", "cms_form_dump.json")

# 드라이버·브라우저 실행 파일 경로.
# 자동 탐지가 실패하는 환경(사내망, 오프라인, 버전 불일치)에서 직접 지정합니다.
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "")
CHROME_BINARY = os.getenv("CHROME_BINARY", "")

# 브라우저 동작
HEADLESS = os.getenv("CMS_HEADLESS", "1") not in ("0", "false", "False")
TIMEOUT = int(os.getenv("CMS_TIMEOUT", "25"))
# 사람이 눈으로 확인하며 진행할 때 각 단계 사이 지연(초)
STEP_DELAY = float(os.getenv("CMS_STEP_DELAY", "0.4"))


# ── 폼 필드 정의 ─────────────────────────────────────────────────────
# 관리자 화면의 라벨 텍스트. inspector가 이 라벨로 필드를 찾아 매핑합니다.
# 화면 문구가 바뀌면 여기 별칭을 추가하세요.
FIELD_LABELS = {
    "expose": ["노출 여부", "노출여부"],
    "category": ["카테고리"],
    "title": ["제목( H1 )", "제목(H1)", "제목"],
    "post_url": ["포스트URL", "포스트 URL"],
    "meta_title": ["MetaTitle", "메타타이틀"],
    "meta_description": ["MetaDescription", "메타디스크립션"],
    "hashtags": ["해시태그"],
    "thumbnail": ["썸네일 등록", "썸네일"],
    "body": ["본문", "내용", "에디터"],
}

# 업로드에 반드시 필요한 필드. 하나라도 매핑이 없으면 발행을 막습니다.
REQUIRED_FIELDS = [
    "category",
    "title",
    "post_url",
    "meta_title",
    "meta_description",
    "hashtags",
    "thumbnail",
    "body",
]


class ConfigError(RuntimeError):
    pass


def credentials() -> tuple:
    """로그인 정보를 돌려준다. 없으면 명확히 알린다."""
    if not USERNAME or not PASSWORD:
        raise ConfigError(
            "CMS 로그인 정보가 없습니다. .env에 CMS_USERNAME / CMS_PASSWORD를 넣으세요.\n"
            "(로그인 정보는 절대 코드나 저장소에 커밋하지 마십시오.)"
        )
    return USERNAME, PASSWORD


def load_mapping() -> dict:
    """셀렉터 매핑을 읽는다."""
    if not os.path.exists(MAPPING_PATH):
        raise ConfigError(
            f"셀렉터 매핑 파일이 없습니다: {MAPPING_PATH}\n"
            "먼저 `python main.py inspect-cms`를 실행해 폼 구조를 읽어오세요."
        )
    with open(MAPPING_PATH, encoding="utf-8") as fp:
        mapping = json.load(fp)

    missing = [
        f for f in REQUIRED_FIELDS if not (mapping.get("fields", {}) or {}).get(f)
    ]
    if missing:
        raise ConfigError(
            f"매핑에서 다음 필드를 찾지 못했습니다: {', '.join(missing)}\n"
            f"{DUMP_PATH}를 열어 해당 필드의 셀렉터를 확인한 뒤 "
            f"{MAPPING_PATH}의 fields에 직접 채워 넣으세요."
        )
    return mapping


def save_mapping(mapping: dict) -> str:
    with open(MAPPING_PATH, "w", encoding="utf-8") as fp:
        json.dump(mapping, fp, ensure_ascii=False, indent=2)
    logger.info("셀렉터 매핑 저장: %s", MAPPING_PATH)
    return MAPPING_PATH


def has_mapping() -> bool:
    return os.path.exists(MAPPING_PATH)


def status() -> dict:
    """웹 화면에 표시할 설정 점검 결과."""
    problems = []
    if not USERNAME or not PASSWORD:
        problems.append("CMS_USERNAME / CMS_PASSWORD 미설정")
    if not has_mapping():
        problems.append(f"셀렉터 매핑 없음 ({MAPPING_PATH}) — inspect-cms 실행 필요")
    return {
        "ready": not problems,
        "problems": problems,
        "write_url": WRITE_URL,
        "mapping_path": MAPPING_PATH,
    }


# ── 로그인 정보 입력 ─────────────────────────────────────────────────
ENV_PATH = os.getenv("ENV_PATH", ".env")


def _write_env(key: str, value: str, path: str = ENV_PATH) -> None:
    """.env의 한 줄만 바꾸거나 없으면 덧붙인다. 나머지 줄은 그대로 둔다."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fp:
            lines = fp.read().splitlines()

    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[i] = prefix + value
            break
    else:
        lines.append(prefix + value)

    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")


def ensure_credentials() -> bool:
    """CMS 로그인 정보가 없으면 이 자리에서 묻고 .env에 넣는다.

    비밀번호를 채팅이나 메모에 적어 옮기지 않아도 되게 하려는 것입니다.
    입력값은 화면에 표시되지 않고, 저장소에 올라가지 않는 .env에만 적힙니다.
    """
    global USERNAME, PASSWORD

    if USERNAME and PASSWORD:
        return True

    import getpass

    print()
    print("  CMS 로그인 정보가 아직 없습니다.")
    print(f"  아래에 입력하면 {ENV_PATH} 에만 저장됩니다. (git에 올라가지 않습니다)")
    print("  건너뛰려면 그냥 Enter를 누르세요.")
    print()

    try:
        user = input("  아이디> ").strip()
        if not user:
            print("  건너뛰었습니다.")
            return False
        pw = getpass.getpass("  비밀번호> (입력해도 화면에 보이지 않습니다) ")
    except (EOFError, KeyboardInterrupt):
        print("\n  취소했습니다.")
        return False

    if not pw:
        print("  비밀번호가 비어 있어 저장하지 않았습니다.")
        return False

    _write_env("CMS_USERNAME", user)
    _write_env("CMS_PASSWORD", pw)
    os.environ["CMS_USERNAME"] = user
    os.environ["CMS_PASSWORD"] = pw
    USERNAME, PASSWORD = user, pw
    print(f"  {ENV_PATH} 에 저장했습니다.")
    return True
