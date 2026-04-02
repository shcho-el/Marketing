# ── 네이버 API 키 설정 ───────────────────────────────────────────────
# https://developers.naver.com 에서 앱 등록 후 발급
# 환경변수로 설정: export NAVER_CLIENT_ID=xxx  NAVER_CLIENT_SECRET=yyy
# 또는 .env 파일에 작성 (아래 참조)
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 미설치 시 환경변수 직접 설정 필요

KEYWORDS = [
    "송도내성발톱",
    "인천내성발톱",
    "인천문제성발톱",
    "송도문제성발톱",
    "인천내성발톱병원",
    "인천발톱무좀",
    "송도발톱무좀",
    "문제성발톱병원",
    "문제성발톱",
]

# "오블리브"로 검색 시 "오블리브의원"도 자동 포함 (부분 문자열 매칭)
TARGET_BRAND = "오블리브"

# 검색 결과 몇 위까지 확인할지 (블로그 기준)
SEARCH_DEPTH = 30

# 각 요청 간 딜레이 (초) - 네이버 차단 방지
REQUEST_DELAY = 2.0

# 데이터 저장 경로
DB_PATH = "rankings.db"

# 대시보드 서버 설정
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000

# 매일 실행 시각 (24시간 형식)
SCHEDULE_TIME = "09:00"
