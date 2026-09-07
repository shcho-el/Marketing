# -*- coding: utf-8 -*-
"""
JSON-LD 구조화 데이터 생성.

구글은 이 데이터로 리치 결과(FAQ 아코디언·사이트링크)를 만들고,
생성형 검색은 여기서 '누가·어디서·무엇을' 말했는지를 확정합니다.
개체(Entity)를 명시적으로 선언해 두면 인용될 때 병원명이 함께 붙습니다.

@graph 하나에 다음을 묶어 발행합니다.
  MedicalClinic    - 병원 개체(NAP). 지역 검색과 인용 귀속의 기준.
  MedicalWebPage   - 이 글 자체. 작성자·감수자·최종수정일(E-E-A-T).
  FAQPage          - FAQ 리치 결과.
  BreadcrumbList   - 사이트 구조.
"""

import json
from datetime import date

from content import clinic, taxonomy


def _clinic_node() -> dict:
    node = {
        "@type": ["MedicalClinic", "MedicalBusiness"],
        "@id": f"{clinic.HOMEPAGE}#clinic",
        "name": clinic.FULL_NAME,
        "alternateName": [clinic.OFFICIAL_NAME, clinic.SHORT_NAME],
        "url": clinic.HOMEPAGE,
        "medicalSpecialty": "Dermatology",
        "availableService": [
            {"@type": "MedicalTherapy", "name": s}
            for s in clinic.SCOPE["primary"]
        ],
        "areaServed": [
            {"@type": "AdministrativeArea", "name": a} for a in clinic.SERVICE_AREAS
        ],
    }

    address = {"@type": "PostalAddress", "addressCountry": "KR"}
    if clinic.ADDRESS_REGION:
        address["addressRegion"] = clinic.ADDRESS_REGION
    if clinic.ADDRESS_LOCALITY:
        address["addressLocality"] = clinic.ADDRESS_LOCALITY
    if clinic.ADDRESS_STREET:
        address["streetAddress"] = clinic.ADDRESS_STREET
    if clinic.POSTAL_CODE:
        address["postalCode"] = clinic.POSTAL_CODE
    node["address"] = address

    if clinic.PHONE:
        node["telephone"] = clinic.PHONE
    if clinic.OPENING_HOURS:
        node["openingHours"] = clinic.OPENING_HOURS

    same_as = [u for u in (clinic.NAVER_PLACE_URL, clinic.GOOGLE_PROFILE_URL) if u]
    if same_as:
        node["sameAs"] = same_as

    return node


def _person_node(person: dict, suffix: str) -> dict:
    return {
        "@type": "Person",
        "@id": f"{clinic.HOMEPAGE}#{suffix}",
        "name": person["name"],
        "jobTitle": person.get("job_title", ""),
        "honorificSuffix": person.get("credential", ""),
        "worksFor": {"@id": f"{clinic.HOMEPAGE}#clinic"},
    }


def _webpage_node(doc: dict, url: str, published: str, modified: str) -> dict:
    node = {
        "@type": ["MedicalWebPage", "Article"],
        "@id": f"{url}#webpage",
        "url": url,
        "name": doc.get("h1", ""),
        "headline": doc.get("h1", ""),
        "description": doc.get("meta_description", ""),
        "inLanguage": "ko-KR",
        "datePublished": published,
        "dateModified": modified,
        "publisher": {"@id": f"{clinic.HOMEPAGE}#clinic"},
        "isPartOf": {"@id": f"{clinic.BLOG_BASE}#blog"},
        # 의학 정보 페이지임을 명시 - 구글 건강 콘텐츠 분류에 사용
        "medicalAudience": {"@type": "MedicalAudience", "audienceType": "Patient"},
        "about": [
            {
                "@type": "MedicalCondition",
                "name": name,
                "alternateName": alt,
            }
            for name, alt in (
                ("발톱무좀", "조갑진균증(Onychomycosis)"),
                ("내성발톱", "함입조갑(Ingrown toenail)"),
            )
        ],
        "lastReviewed": modified,
        "reviewedBy": {"@id": f"{clinic.HOMEPAGE}#reviewer"}
        if clinic.REVIEWER["name"]
        else None,
    }

    if clinic.AUTHOR["name"]:
        node["author"] = {"@id": f"{clinic.HOMEPAGE}#author"}
    else:
        node["author"] = {"@id": f"{clinic.HOMEPAGE}#clinic"}

    if not clinic.REVIEWER["name"]:
        node.pop("reviewedBy")

    # 인용 근거로 제시한 외부 출처
    citations = doc.get("citations") or []
    cite_nodes = [
        {
            "@type": "CreativeWork",
            "name": c.get("title") or c.get("org", ""),
            "publisher": c.get("org", ""),
            "url": c.get("url", ""),
        }
        for c in citations
        if c.get("org") or c.get("title")
    ]
    if cite_nodes:
        node["citation"] = cite_nodes

    # 핵심 요약 - 발췌 후보 텍스트를 명시적으로 노출
    takeaways = doc.get("key_takeaways") or []
    if takeaways:
        node["abstract"] = " ".join(takeaways)

    return {k: v for k, v in node.items() if v not in (None, "", [], {})}


def _faq_node(doc: dict, url: str) -> dict:
    faq = doc.get("faq") or []
    return {
        "@type": "FAQPage",
        "@id": f"{url}#faq",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f.get("q", ""),
                "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")},
            }
            for f in faq
            if f.get("q") and f.get("a")
        ],
    }


def _breadcrumb_node(doc: dict, url: str) -> dict:
    category = doc.get("category", "")
    items = [
        {"name": "홈", "item": clinic.HOMEPAGE},
        {"name": "블로그", "item": clinic.BLOG_BASE},
    ]
    if category:
        items.append(
            {"name": category, "item": f"{clinic.BLOG_BASE}/{category}"}
        )
    items.append({"name": doc.get("h1", ""), "item": url})

    return {
        "@type": "BreadcrumbList",
        "@id": f"{url}#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": it["name"],
                "item": it["item"],
            }
            for i, it in enumerate(items)
        ],
    }


def build(doc: dict, published: str = "", modified: str = "") -> dict:
    """발행용 JSON-LD @graph를 만든다."""
    today = date.today().isoformat()
    published = published or today
    modified = modified or today

    url = taxonomy.post_url(doc.get("category", ""), doc.get("post_url", ""))

    graph = [_clinic_node()]
    if clinic.AUTHOR["name"]:
        graph.append(_person_node(clinic.AUTHOR, "author"))
    if clinic.REVIEWER["name"]:
        graph.append(_person_node(clinic.REVIEWER, "reviewer"))
    graph.append(_webpage_node(doc, url, published, modified))

    faq = _faq_node(doc, url)
    if faq["mainEntity"]:
        graph.append(faq)

    graph.append(_breadcrumb_node(doc, url))

    return {"@context": "https://schema.org", "@graph": graph}


def to_script_tag(doc: dict, published: str = "", modified: str = "") -> str:
    """<head> 또는 본문 하단에 붙일 <script> 태그 문자열."""
    data = build(doc, published, modified)
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{body}\n</script>'
