"""
병원 프로필 - 모든 생성 콘텐츠가 참조하는 단일 진실 공급원(Single Source of Truth).

여기 적힌 사실만 본문에 등장할 수 있습니다. 생성기는 이 파일에 없는
장비명·수치·실적을 지어내지 못하도록 프롬프트에서 강하게 제약합니다.

NAP(Name·Address·Phone) 일관성은 로컬 SEO와 GEO(생성형 검색 인용)의 핵심입니다.
아래 값이 홈페이지·네이버플레이스·구글 비즈니스 프로필과 글자 단위로 같아야 합니다.
확인되지 않은 항목은 빈 문자열로 두면 SEO 검사에서 경고로 표시됩니다.
"""

import os

from content import services

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ── 기관 식별 정보 (NAP) ──────────────────────────────────────────────
# 정식 명칭. 본문 첫 등장 시 반드시 이 표기를 사용합니다.
OFFICIAL_NAME = os.getenv("CLINIC_OFFICIAL_NAME", "오블리브 송도 호라이즌의원")
# 클리닉(진료 브랜드) 명칭
CLINIC_NAME = os.getenv("CLINIC_UNIT_NAME", "") or services.current()["label"]
# 본문에서 반복 사용할 짧은 호칭
SHORT_NAME = os.getenv("CLINIC_SHORT_NAME", "오블리브의원")
# 개체(Entity) 일관성을 위해 AI 검색이 학습할 정식 결합 표기
FULL_NAME = f"{OFFICIAL_NAME} {CLINIC_NAME}"

# 주소·전화·영업시간은 반드시 실제 값으로 채워주세요.
# 빈 값이면 JSON-LD에서 해당 필드가 생략되고 SEO 검사에서 경고가 뜹니다.
ADDRESS_REGION = os.getenv("CLINIC_REGION", "인천광역시")
ADDRESS_LOCALITY = os.getenv("CLINIC_LOCALITY", "연수구")
ADDRESS_STREET = os.getenv("CLINIC_STREET", "")  # 예: "송도과학로 16번길 13-4, 3층"
POSTAL_CODE = os.getenv("CLINIC_POSTAL_CODE", "")
PHONE = os.getenv("CLINIC_PHONE", "")  # 예: "032-000-0000"
OPENING_HOURS = os.getenv("CLINIC_HOURS", "")  # 예: "Mo-Fr 10:00-19:00, Sa 10:00-14:00"

HOMEPAGE = os.getenv("CLINIC_HOMEPAGE", "https://obliv.kr")
BLOG_BASE = os.getenv("CLINIC_BLOG_BASE", "https://blog.obliv.kr/blog")
NAVER_PLACE_URL = os.getenv("CLINIC_NAVER_PLACE", "")
GOOGLE_PROFILE_URL = os.getenv("CLINIC_GOOGLE_PROFILE", "")

# 지역 SEO용 세부 상권 (본문·해시태그에서 활용)
SERVICE_AREAS = [
    "인천 송도",
    "연수구",
    "송도동",
    "인천 논현동",
    "인천 청라",
    "인천 구월동",
    "부평",
]


# ── 진료 범위 ────────────────────────────────────────────────────────
# 진료 분야 카탈로그(content/services.py)에서 가져온다.
# 새 분야를 추가하거나 진료 범위가 바뀌면 그 파일만 고치면 된다.
_SVC = services.current()

SCOPE = _SVC["scope"]
DIFFERENTIAL_DX = _SVC["differential"]

# 본원에서 시행하지 않는 시술. 광고에 쓰면 허위광고가 된다.
NOT_PERFORMED = _SVC["not_performed"]
# 쓰지 않을 표현과 대체어 (치료 의원이지 관리숍이 아니다)
AVOID_TERMS = _SVC["avoid_terms"]


# ── 치료 프로세스 및 장비 ─────────────────────────────────────────────
# 실제 보유·시행 항목만. 생성기는 이 목록 밖의 장비를 언급할 수 없다.
TREATMENT_STEPS = _SVC["steps"]
DEVICES = _SVC["devices"]
DIFFERENTIATORS = _SVC["strengths"]


# ── 의료법 필수 고지 ──────────────────────────────────────────────────
# 의료법 제56조 제2항 및 의료광고 심의 기준상 치료 관련 콘텐츠에는
# 부작용 등 중요정보를 반드시 함께 기재해야 합니다. 모든 글 하단에 삽입됩니다.
MANDATORY_NOTICE = {
    "heading": "시술 전 반드시 확인해 주세요",
    "items": _SVC["notice"],
}

# 광고심의 관련 표기 (심의번호를 받은 경우 .env에 넣으면 하단에 자동 표기)
AD_REVIEW_NUMBER = os.getenv("CLINIC_AD_REVIEW_NO", "")


# ── E-E-A-T 신호 ─────────────────────────────────────────────────────
# 구글 YMYL(건강) 영역에서 필수. 작성자·감수자 정보를 명시합니다.
AUTHOR = {
    "name": os.getenv("CLINIC_AUTHOR_NAME", ""),        # 예: "홍길동"
    "job_title": os.getenv("CLINIC_AUTHOR_TITLE", "원장"),
    "credential": os.getenv("CLINIC_AUTHOR_CREDENTIAL", "의사"),
}
REVIEWER = {
    "name": os.getenv("CLINIC_REVIEWER_NAME", ""),
    "job_title": os.getenv("CLINIC_REVIEWER_TITLE", "원장"),
}


# ── 인용 가능한 공신력 있는 출처 ────────────────────────────────────────
# GEO(생성형 엔진 최적화)에서 AI가 인용할 근거를 제공합니다.
# 본문에 기관명을 언급하되, 없는 통계를 지어내지 않도록 사실만 나열합니다.
AUTHORITATIVE_SOURCES = [
    {
        "org": "질병관리청 국가건강정보포털",
        "topic": "조갑진균증(손발톱무좀) 일반 정보",
        "url": "https://health.kdca.go.kr",
    },
    {
        "org": "대한의학회 · 질병관리청",
        "topic": "손발톱 진균 감염 진단과 치료 원칙",
        "url": "https://www.kams.or.kr",
    },
    {
        "org": "식품의약품안전처",
        "topic": "경구 항진균제 안전성 정보 및 허가사항",
        "url": "https://nedrug.mfds.go.kr",
    },
]


def nap_completeness() -> dict:
    """NAP·E-E-A-T 필수 항목이 채워졌는지 점검한다."""
    missing = []
    if not ADDRESS_STREET:
        missing.append("주소(CLINIC_STREET)")
    if not PHONE:
        missing.append("대표번호(CLINIC_PHONE)")
    if not OPENING_HOURS:
        missing.append("진료시간(CLINIC_HOURS)")
    if not AUTHOR["name"]:
        missing.append("작성/감수 의료진명(CLINIC_AUTHOR_NAME)")
    if not NAVER_PLACE_URL:
        missing.append("네이버플레이스 URL(CLINIC_NAVER_PLACE)")
    return {"complete": not missing, "missing": missing}


def facts_block() -> str:
    """프롬프트에 주입할 '허용된 사실' 텍스트 블록."""
    devices = ", ".join(f"{d['name']}({d['type']})" for d in DEVICES)
    steps = "\n".join(f"  - {s['name']}: {s['detail']}" for s in TREATMENT_STEPS)
    diffs = "\n".join(f"  - {d}" for d in DIFFERENTIATORS)
    sources = "\n".join(
        f"  - {s['org']}: {s['topic']}" for s in AUTHORITATIVE_SOURCES
    )
    author = AUTHOR["name"] or "(미기재)"
    location = " ".join(
        p for p in (ADDRESS_REGION, ADDRESS_LOCALITY, ADDRESS_STREET) if p
    )
    not_performed = "\n".join(
        f"  - {', '.join(n['terms'])}: {n['reason']} → {n['instead']}"
        for n in NOT_PERFORMED
    )
    avoid = "\n".join(
        f"  - {', '.join(a['terms'])}: {a['reason']} → {a['instead']}"
        for a in AVOID_TERMS
    )
    return f"""[기관]
  정식명칭: {OFFICIAL_NAME}
  클리닉: {CLINIC_NAME}
  본문 호칭: {SHORT_NAME}
  소재지: {location}
  진료지역: {", ".join(SERVICE_AREAS)}
  작성/감수: {author} {AUTHOR['job_title']}

[진료 범위]
  주요: {", ".join(SCOPE["primary"])}
  포괄 명칭: {SCOPE["umbrella"]}
  감별 대상 질환: {", ".join(DIFFERENTIAL_DX)}

[보유 장비]
  {devices}

[치료 프로세스]
{steps}

[사실 기반 차별점]
{diffs}

[본원에서 시행하지 않는 시술 - 본원이 하는 것처럼 쓰면 허위광고]
{not_performed}

[쓰지 않을 표현]
{avoid}

[인용 가능한 근거 기관]
{sources}
"""
