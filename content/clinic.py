"""
병원 프로필 - 모든 생성 콘텐츠가 참조하는 단일 진실 공급원(Single Source of Truth).

여기 적힌 사실만 본문에 등장할 수 있습니다. 생성기는 이 파일에 없는
장비명·수치·실적을 지어내지 못하도록 프롬프트에서 강하게 제약합니다.

NAP(Name·Address·Phone) 일관성은 로컬 SEO와 GEO(생성형 검색 인용)의 핵심입니다.
아래 값이 홈페이지·네이버플레이스·구글 비즈니스 프로필과 글자 단위로 같아야 합니다.
확인되지 않은 항목은 빈 문자열로 두면 SEO 검사에서 경고로 표시됩니다.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ── 기관 식별 정보 (NAP) ──────────────────────────────────────────────
# 정식 명칭. 본문 첫 등장 시 반드시 이 표기를 사용합니다.
OFFICIAL_NAME = os.getenv("CLINIC_OFFICIAL_NAME", "오블리브 송도 호라이즌의원")
# 클리닉(진료 브랜드) 명칭
CLINIC_NAME = os.getenv("CLINIC_UNIT_NAME", "문제성발톱클리닉")
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
# 본원이 실제로 진료하는 범위. 이 밖의 질환은 본문에서 다루지 않습니다.
SCOPE = {
    "primary": ["발톱무좀(조갑진균증)", "내성발톱(함입조갑)"],
    "umbrella": "문제성발톱",
    "related": ["두꺼워진 발톱(조갑비후)", "발톱 변색", "발톱 변형"],
}

# 감별이 필요한 질환 - "무좀이 아닐 수도 있다"는 근거 있는 서술에 사용
DIFFERENTIAL_DX = [
    "조갑하 혈종",
    "조갑 건선",
    "단순 외상성 발톱 변형",
    "편평태선",
]


# ── 치료 프로세스 및 장비 ─────────────────────────────────────────────
# 실제 보유·시행 항목만 기재. 생성기는 이 목록 밖의 장비를 언급할 수 없습니다.
TREATMENT_STEPS = [
    {
        "name": "정밀 진단",
        "detail": "발톱 두께·변색 범위·변형 정도와 기저질환을 확인해 무좀 외 원인"
                  "(조갑하 혈종·건선 등)과 감별합니다.",
    },
    {
        "name": "프리컨디셔닝",
        "detail": "발톱 치료사가 두꺼워진 발톱 층을 정리해 레이저 에너지와 국소 도포제가"
                  "발톱 아래 병변까지 도달할 통로를 확보하는 과정입니다.",
    },
    {
        "name": "레이저 치료",
        "detail": "단단한 발톱 조직을 투과해 진균이 서식하는 심부에 에너지를 전달합니다.",
    },
    {
        "name": "복합 치료 플랜",
        "detail": "진행 단계(1기~5기)와 기저질환에 따라 국소 도포제·경구 항진균제·레이저를"
                  "조합한 개인별 계획을 세웁니다.",
    },
    {
        "name": "경과 추적",
        "detail": "새 발톱이 자라 나오는 속도에 맞춰 주기적으로 상태를 재평가합니다.",
    },
]

# 보유 장비 - 명칭을 임의로 바꾸거나 추가하지 않습니다.
DEVICES = [
    {"name": "오니코", "type": "비가열성"},
    {"name": "AF", "type": "비가열성"},
    {"name": "아톰", "type": "비가열성"},
    {"name": "클라레 다이오드", "type": "가열성"},
]

# 본원이 내세울 수 있는 차별점. 최상급 표현 없이 사실 서술만 남깁니다.
DIFFERENTIATORS = [
    "발톱 두께와 진행 단계를 확인한 뒤 진행하는 1:1 맞춤 치료 계획",
    "비가열성·가열성 레이저를 상태에 따라 선택 적용",
    "프리컨디셔닝으로 약물·레이저의 침투 경로를 먼저 확보",
    "교차 감염을 고려한 기구 소독·멸균 절차",
    "독립된 문제성발톱 전용 진료 공간",
]


# ── 의료법 필수 고지 ──────────────────────────────────────────────────
# 의료법 제56조 제2항 및 의료광고 심의 기준상 치료 관련 콘텐츠에는
# 부작용 등 중요정보를 반드시 함께 기재해야 합니다. 모든 글 하단에 삽입됩니다.
MANDATORY_NOTICE = {
    "heading": "시술 전 반드시 확인해 주세요",
    "items": [
        "가열성 레이저 시술 시 개인의 민감도에 따라 일시적인 열감, 화끈거림, "
        "홍반 등이 나타날 수 있습니다.",
        "진균 감염 정도와 발톱 성장 속도에 따라 치료 기간과 경과에는 개인차가 있습니다.",
        "경구 항진균제는 간 기능 이상, 위장 장애, 약물 상호작용 등이 보고되어 있어 "
        "복용 전 의료진 상담과 필요 시 혈액검사가 권장됩니다.",
        "시술 후에는 발을 건조하게 유지하고, 재감염 방지를 위해 신발·양말을 "
        "소독하거나 교체하는 것이 권장됩니다.",
        "본 내용은 의학 정보 제공을 목적으로 하며 특정 치료 효과를 보장하지 않습니다. "
        "정확한 진단과 치료 방법은 의료진 진료를 통해 결정됩니다.",
    ],
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

[인용 가능한 근거 기관]
{sources}
"""
