"""
오블리브 문제성발톱클리닉 - 의료법 준수 SEO/AEO/GEO 콘텐츠 자동 생성 모듈

구성
  clinic.py       병원 프로필(NAP·장비·진료범위) 단일 진실 공급원
  taxonomy.py     카테고리 / 키워드 세트 / 해시태그 풀
  slug.py         포스트 URL 슬러그 생성
  medical_law.py  의료법 제56조 의료광고 금지사항 검사기
  seo.py          SEO / AEO / GEO 점수 산출 및 검증
  schema.py       JSON-LD 구조화 데이터(MedicalWebPage·FAQPage 등)
  prompts.py      생성 프롬프트 + 출력 스키마
  generator.py    Claude API 호출
  renderer.py     생성 결과 → 발행용 HTML 본문
  store.py        생성 이력 SQLite 저장
"""

__all__ = [
    "clinic",
    "taxonomy",
    "slug",
    "medical_law",
    "seo",
    "schema",
    "prompts",
    "generator",
    "renderer",
    "store",
]
