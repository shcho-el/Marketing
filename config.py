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
    # ── 발톱 콘텐츠 ──────────────────────────────────────────
    "https://blog.naver.com/rosee_log/224223118377",
    "https://blog.naver.com/dltkdgo1029/224236941854",
    "https://blog.naver.com/y0000uj/224237174148",
    "https://blog.naver.com/castqueen/224039798863",
    "https://blog.naver.com/yunicong/224042302646",
    "https://blog.naver.com/deadcity/224036950448",
    "https://blog.naver.com/delphine0327/224037321732",
    "https://blog.naver.com/gittygittygitty/224030288053",
    "https://blog.naver.com/23people2000/224026052346",
    "https://blog.naver.com/dmssdlrhdwns/224022417329",
    "https://blog.naver.com/allaboutcanada/224042138524",
    "https://blog.naver.com/hilty74/224099437038",
    "https://blog.naver.com/banggeul07/224099267173",
    "https://blog.naver.com/89_mazy/224118856285",
    "https://blog.naver.com/cjswo4354/224115439062",
    "https://blog.naver.com/alsrud7667/224097058770",
    "https://blog.naver.com/ans141205/224125629211",
    "https://blog.naver.com/alsyffl2/224135025837",
    "https://blog.naver.com/hana5cjstk/224159520834",
    "https://blog.naver.com/l_n_y/224230390901",
    "https://blog.naver.com/lllillillioo/224230515556",
    "https://blog.naver.com/chai_beauty/224231665056",
    "https://blog.naver.com/allaboutcanada/224237092430",
    "https://blog.naver.com/castqueen/224236895517",
    "https://blog.naver.com/l971031/223851099595",
    "https://blog.naver.com/five911/223873193461",
    "https://blog.naver.com/apeach0124/223895680642",
    "https://blog.naver.com/jihye8611/223958602714",
    "https://blog.naver.com/dmswls3330/223991071478",
    "https://blog.naver.com/asegh9502/223984076057",
    "https://blog.naver.com/chan7ky/224002487329",
    "https://blog.naver.com/bless_mycat/224011202479",
    "https://blog.naver.com/ranybom1/224025996257",
    "https://blog.naver.com/banbanmoo_cos/223881681149",
    "https://blog.naver.com/s_e_y_0615/223900720159",
    "https://blog.naver.com/eun_da_/223889690076",
    "https://blog.naver.com/yhikim/223910024648",
    "https://blog.naver.com/bayern01/223906710915",
    "https://blog.naver.com/bpony1020/223912048205",
    "https://blog.naver.com/piacame/223901908177",
    "https://blog.naver.com/jingols/223912135277",
    "https://blog.naver.com/sosoheyo012/223925509936",
    "https://blog.naver.com/nizooo/223941539273",
    "https://blog.naver.com/mrkvnykov20/223941875602",
    "https://blog.naver.com/dadalda/223949568788",
    "https://blog.naver.com/swimand/223960919595",
    "https://blog.naver.com/allaboutcanada/223932969077",
    "https://blog.naver.com/ahnbyul/224017607605",
    "https://blog.naver.com/wldjskd/224036663964",
    "https://blog.naver.com/somerz94/224062024102",
    "https://blog.naver.com/ekfrnsdl1026/224067030956",
    "https://blog.naver.com/js_817/224164624022",
    "https://blog.naver.com/o3o4260/224131488018",
    "https://blog.naver.com/five911/224163758009",
    "https://blog.naver.com/apeach0124/224182712683",
    "https://blog.naver.com/dmswls3330/224198309025",
    "https://blog.naver.com/asegh9502/224188502607",
    "https://blog.naver.com/bpony1020/224214794949",
    "https://blog.naver.com/parkkwanseo1004/224026697168",
    "https://blog.naver.com/marketerbisu/224046555204",
    "https://blog.naver.com/scblove18/224046539578",
    "https://blog.naver.com/tj26840/224057393228",
    "https://blog.naver.com/uqrkyaxeqpurg/224063346316",
    "https://blog.naver.com/lamimi__/224094450678",
    "https://blog.naver.com/jooa9796/224106978016",
    "https://blog.naver.com/hongchicboy/224070699315",
    "https://blog.naver.com/sgsg0510/224079626888",
    "https://blog.naver.com/hrsd1020/224118354224",
    "https://blog.naver.com/vkfdnjf03/224134925724",
    "https://blog.naver.com/kimanam1/224155665586",
    "https://blog.naver.com/codkfhdns/224232499423",
]

# 포스트 제목/내용에 이 단어가 포함되면 경쟁사 콘텐츠로 간주하여 제외
EXCLUDE_KEYWORDS = [
    "오벨리뷰티",
    "레푸스",
    "메디푸스",
    "포디랩",
    "피오레네일",
    "에이풋케어",
    "아인병원",
    "청라사랑내과",
    "어바웃뷰티",
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
