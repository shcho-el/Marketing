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

TARGET_BRAND = "오블리브"  # 슬랙/DB 표시용

# 오블리브 콘텐츠로 확정된 블로그 포스트 URL 목록
# (m.blog.naver.com / blog.naver.com 자동 통합)
TARGET_URLS = [
    "https://blog.naver.com/rosee_log/224223118377",
    "https://blog.naver.com/dltkdgo1029/224236941854",
    "https://blog.naver.com/y0000uj/224237174148",
    "https://blog.naver.com/l_n_y/224230390901",
    "https://blog.naver.com/lllillillioo/224230515556",
    "https://blog.naver.com/chai_beauty/224231665056",
    "https://blog.naver.com/allaboutcanada/224237092430",
    "https://blog.naver.com/castqueen/224236895517",
    "https://blog.naver.com/five911/224163758009",
    "https://blog.naver.com/apeach0124/224182712683",
    "https://blog.naver.com/dmswls3330/224198309025",
    "https://blog.naver.com/asegh9502/224188502607",
    "https://blog.naver.com/bpony1020/224214794949",
    "https://blog.naver.com/codkfhdns/224232499423",
    "https://blog.naver.com/vkfdnjf03/224134925724",
    "https://blog.naver.com/kimanam1/224155665586",
]

# URL 매칭 실패 시 폴백용 브랜드명 (보조 수단)
BRAND_ALIASES = [
    "오블리브",
    "오블리브의원",
]

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
