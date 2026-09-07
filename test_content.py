# -*- coding: utf-8 -*-
"""
콘텐츠 생성 파이프라인 점검 (API 호출 없음).

  python test_content.py

실제 발행된 글을 출력 스키마로 옮긴 픽스처로
의료법 검사 · SEO/AEO/GEO 채점 · 렌더링 · JSON-LD · 웹 라우트를 확인합니다.
"""

import json
import os
import sys

from content import generator, medical_law, renderer, schema, seo, slug, store


# 실제 발행 글("두꺼워진 발톱, 겉에만 '약' 바르는 건…")을 스키마 형태로 옮긴 것
FIXTURE = {
    "category": "발톱무좀치료",
    "primary_keyword": "발톱무좀",
    "h1": "두꺼워진 발톱, 겉에만 약을 발라도 낫지 않는 이유_송도발톱무좀",
    "meta_title": "두꺼워진 발톱 무좀, 약이 안 듣는 이유",
    "meta_description": "약을 발라도 발톱 무좀이 그대로인 이유와 송도 오블리브의원의 치료 과정을 정리했습니다.",
    "thumbnail_copy": "약이 안 듣는 이유",
    "hashtags": [
        "#송도발톱무좀", "#인천발톱무좀", "#연수구발톱무좀", "#송도동무좀치료",
        "#인천논현동발톱무좀", "#배곧발톱무좀", "#두꺼워진발톱", "#조갑진균증",
        "#발톱무좀레이저", "#문제성발톱",
    ],
    "answer_capsule": (
        "발톱무좀에 약을 발라도 낫지 않는 가장 큰 이유는 두꺼워진 발톱이 물리적 장벽이 되어 "
        "약물이 병변까지 닿지 못하기 때문입니다. 두꺼워진 층을 먼저 정리해 약물과 레이저가 "
        "지나갈 통로를 확보하는 과정이 필요합니다."
    ),
    "intro": (
        "인천 송도에서 문제성 발톱을 중점 진료하는 오블리브 송도 호라이즌의원 문제성발톱클리닉입니다. "
        "많은 분들이 약국에서 구한 외용액만으로 발톱 무좀을 해결하려 하시지만, "
        "정성껏 발라도 발톱이 여전히 두껍고 노랗다면 그것은 정성의 문제가 아니라 구조의 문제입니다."
    ),
    "sections": [
        {
            "h2": "왜 바르는 약만으로는 부족한가요?",
            "answer": (
                "발톱이 두꺼워지면 약물이 발톱 아래 병변까지 도달하기 어렵기 때문입니다. "
                "발톱은 단단한 케라틴 층으로 이루어져 있어, 무좀균이 침투하면 방어 기전으로 "
                "더 두껍고 딱딱해집니다."
            ),
            "blocks": [
                {
                    "type": "list",
                    "text": "",
                    "items": [
                        "무좀균은 발톱 표면이 아니라 발톱 밑바닥(조상)과 뿌리 쪽에 자리 잡습니다.",
                        "두꺼워진 케라틴 층은 외용제의 유효 성분이 지나가기 어려운 장벽이 됩니다.",
                        "표면에만 도포하면 균 서식지에 약이 닿지 않아 상태가 유지될 수 있습니다.",
                    ],
                    "headers": [], "rows": [],
                },
            ],
        },
        {
            "h2": "치료는 어떤 순서로 진행되나요?",
            "answer": (
                "오블리브의원은 진단 후 두꺼워진 발톱을 먼저 정리하고, 그 통로로 레이저와 약물을 "
                "적용하는 순서로 진행합니다. 진행 단계에 따라 조합을 달리합니다."
            ),
            "blocks": [
                {
                    "type": "steps",
                    "text": "",
                    "items": [
                        "정밀 진단으로 무좀 외 원인과 감별합니다.",
                        "프리컨디셔닝으로 두꺼워진 발톱 층을 정리합니다.",
                        "비가열성 또는 가열성 레이저로 심부에 에너지를 전달합니다.",
                        "상태에 따라 국소 도포제·경구 항진균제를 병행합니다.",
                        "새 발톱이 자라는 경과를 주기적으로 재평가합니다.",
                    ],
                    "headers": [], "rows": [],
                },
            ],
        },
        {
            "h2": "발톱 변색은 모두 무좀인가요?",
            "answer": (
                "아닙니다. 발톱 변색과 두꺼워짐은 무좀 외에도 여러 원인으로 나타나므로 "
                "감별 진단이 먼저입니다. 원인이 다르면 치료 방향도 달라집니다."
            ),
            "blocks": [
                {
                    "type": "table",
                    "text": "",
                    "items": [],
                    "headers": ["감별 대상", "특징"],
                    "rows": [
                        ["조갑하 혈종", "외상 후 발생하며 자라면서 위치가 이동합니다."],
                        ["조갑 건선", "다른 부위 피부 병변이 동반되는 경우가 있습니다."],
                        ["외상성 변형", "반복적인 압박이나 충격 이력이 확인됩니다."],
                    ],
                },
                {
                    "type": "callout",
                    "text": "자가 판단으로 발톱을 깎아내거나 뽑으면 2차 감염 위험이 있어 권장되지 않습니다.",
                    "items": [], "headers": [], "rows": [],
                },
            ],
        },
        {
            "h2": "치료 기간은 얼마나 걸리나요?",
            "answer": (
                "새 발톱이 끝까지 자라 나오는 시간이 필요해 수개월 이상의 경과 관찰이 권장됩니다. "
                "발톱 성장 속도와 감염 범위에 따라 개인차가 있습니다."
            ),
            "blocks": [
                {
                    "type": "paragraph",
                    "text": (
                        "질병관리청 국가건강정보포털에서도 조갑진균증은 손발톱이 새로 자라는 기간을 "
                        "고려해 장기적으로 관리하는 질환으로 안내하고 있습니다. 치료 중단 여부는 "
                        "의료진 진료를 통해 판단하는 것이 안전합니다."
                    ),
                    "items": [], "headers": [], "rows": [],
                },
            ],
        },
    ],
    "key_takeaways": [
        "발톱무좀은 발톱 밑바닥과 뿌리 쪽에 균이 서식하는 진균 감염 질환입니다.",
        "두꺼워진 발톱은 외용제의 침투를 막는 물리적 장벽으로 작용합니다.",
        "오블리브의원은 프리컨디셔닝으로 통로를 확보한 뒤 레이저와 약물을 적용합니다.",
        "발톱 변색은 조갑하 혈종이나 건선일 수 있어 감별 진단이 먼저 필요합니다.",
        "치료 기간은 새 발톱이 자라는 속도에 따라 수개월 이상 걸리며 개인차가 있습니다.",
    ],
    "faq": [
        {
            "q": "발톱무좀 레이저 치료는 아픈가요?",
            "a": "비가열성 레이저는 온열감 정도로 느껴지는 경우가 많습니다. 다만 통증 민감도에는 "
                 "개인차가 있으므로 진료 시 상태를 확인한 뒤 방식을 정합니다.",
        },
        {
            "q": "먹는 무좀약을 먹을 수 없는데 방법이 있나요?",
            "a": "간 기능 이상이나 다약제 복용으로 경구 항진균제가 어려운 경우 국소 치료와 레이저를 "
                 "고려할 수 있습니다. 복용 가능 여부는 의료진 진료로 판단합니다.",
        },
        {
            "q": "치료 후 재감염을 막으려면 어떻게 하나요?",
            "a": "발을 건조하게 유지하고 신발과 양말을 소독하거나 교체하는 것이 권장됩니다. "
                 "가족 간 슬리퍼·발톱깎이 공유도 피하는 것이 좋습니다.",
        },
        {
            "q": "당뇨가 있는데 발톱무좀을 두어도 되나요?",
            "a": "당뇨병이나 말초혈관질환이 있으면 작은 상처도 합병증으로 이어질 수 있어 조기 진료가 "
                 "권장됩니다. 자가 처치보다 의료진 확인이 안전합니다.",
        },
    ],
    "closing": (
        "발톱 상태는 사람마다 달라 같은 방법이 모두에게 맞지는 않습니다. "
        "현재 상태가 어떤 단계인지 확인하는 것이 치료의 첫걸음입니다."
    ),
    "internal_link_suggestions": [
        {"anchor_text": "내성발톱 치료 과정", "target_topic": "내성발톱 교정 방법"},
        {"anchor_text": "발톱무좀 재발 방지 생활 관리", "target_topic": "재감염 예방"},
    ],
    "citations": [
        {
            "org": "질병관리청 국가건강정보포털",
            "title": "조갑진균증(손발톱무좀)",
            "url": "https://health.kdca.go.kr",
        },
    ],
}


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'✅' if ok else '❌'} {name}{(' — ' + detail) if detail else ''}")
    return ok


def main() -> int:
    failures = 0
    doc = json.loads(json.dumps(FIXTURE))  # 깊은 복사

    print("\n[1] 정규화 (슬러그·해시태그·표 정합성)")
    doc = generator._normalize(doc, doc["category"], doc["primary_keyword"])
    failures += not check("슬러그 유효", slug.is_valid(doc["post_url"]), doc["post_url"])
    failures += not check(
        "MetaTitle 40자 이내",
        doc["meta_title_overflow"] == 0,
        f"{len(doc['meta_title'])}자",
    )
    failures += not check(
        "MetaDescription 80자 이내",
        doc["meta_desc_overflow"] == 0,
        f"{len(doc['meta_description'])}자",
    )
    failures += not check("발행 URL 조립", doc["published_url"].startswith("http"), doc["published_url"])

    print("\n[2] 의료법 검사")
    law = medical_law.review(generator._full_text(doc))
    failures += not check("금지 표현 없음", law["block_count"] == 0, law["summary"])
    failures += not check("필수 기재 완비", not law["missing_required"])
    for f in law["findings"]:
        print(f"      [{f['severity']}] \"{f['matched']}\" — {f['reason']}")

    print("\n[2-1] 포지셔닝 검사")
    from content import positioning

    pos = positioning.review(generator._full_text(doc))
    failures += not check("미시행 시술 언급 없음", pos["passed"], pos["summary"])
    for f in pos["findings"]:
        print(f"      [{f['severity']}] \"{f['matched']}\" — {f['reason']}")

    # 문맥 판별 - 본원이 안 한다고 쓴 문장은 잡히면 안 된다
    failures += not check(
        "'뽑지 않고 교정' 문맥 통과",
        positioning.review("본원은 발톱을 뽑지 않고 교정합니다.")["passed"],
    )
    failures += not check(
        "'외과 진료 필요' 안내 통과",
        positioning.review("절개가 필요한 경우 외과 진료가 필요할 수 있습니다.")["passed"],
    )
    failures += not check(
        "본원이 절개한다고 쓰면 차단",
        not positioning.review("본원에서 내성발톱 절개를 시행합니다.")["passed"],
    )

    print("\n[3] SEO / AEO / GEO 채점")
    audit = seo.audit(doc, doc["primary_keyword"])
    s = audit["scores"]
    print(f"      SEO {s['seo']} · AEO {s['aeo']} · GEO {s['geo']} → 종합 {s['total']} ({audit['grade']})")
    failures += not check("SEO 75점 이상", s["seo"] >= 75)
    failures += not check("AEO 75점 이상", s["aeo"] >= 75)
    for c in audit["top_fixes"]:
        print(f"      ⚠ {c['label']}: {c['detail']}")

    print("\n[4] 렌더링")
    html = renderer.render_body(doc, include_schema=False)
    text = renderer.render_plaintext(doc)
    failures += not check("HTML 생성", len(html) > 1000, f"{len(html)}자")
    failures += not check("소제목 id 유지", 'id="s1"' in html)
    failures += not check("표 렌더링", "<table>" in html)
    failures += not check("의료법 고지 자동 삽입", "medical-notice" in html)
    failures += not check("평문 생성", len(text) > 800, f"{len(text)}자")

    print("\n[5] JSON-LD")
    graph = schema.build(doc)
    types = [n["@type"] for n in graph["@graph"]]
    failures += not check("MedicalClinic 노드", any("MedicalClinic" in str(t) for t in types))
    failures += not check("MedicalWebPage 노드", any("MedicalWebPage" in str(t) for t in types))
    failures += not check("FAQPage 노드", "FAQPage" in types)
    failures += not check("BreadcrumbList 노드", "BreadcrumbList" in types)
    failures += not check(
        "JSON 직렬화 가능",
        bool(json.dumps(graph, ensure_ascii=False)),
    )

    print("\n[6] 웹 라우트")
    import content_app

    content_app.app.config["TESTING"] = True
    content_app.PASSWORD = ""          # 인증은 아래에서 따로 확인한다
    client = content_app.app.test_client()

    post_id = store.save(doc, {"law": law, "positioning": pos, "seo": audit}, "테스트 주제")
    for path, label in [
        ("/", "콘솔 화면"),
        ("/api/posts", "API 목록"),
        (f"/api/post/{post_id}", "API 상세"),
        (f"/post/{post_id}/thumbnail.jpg", "썸네일"),
        ("/api/preview-title?title=송도 발톱무좀 병원", "제목 해석"),
    ]:
        r = client.get(path)
        failures += not check(f"GET {path.split('?')[0]} ({label})",
                              r.status_code == 200, f"HTTP {r.status_code}")

    # 화면이 필요한 값을 모두 담아 내려주는지
    vm = client.get(f"/api/post/{post_id}").get_json()
    for key in ("doc", "reports", "cms_fields", "body_html", "plaintext",
                "jsonld", "logo", "cms"):
        failures += not check(f"뷰 모델 '{key}'", key in vm)
    # 변수 이름은 안내 문구에 나올 수 있다. 실제 '값'이 새는지를 본다.
    from publisher import config as _cms

    sentinel_key, sentinel_pw = "sk-ant-SENTINEL-KEY", "SENTINEL-PASSWORD"
    saved = (os.environ.get("ANTHROPIC_API_KEY"), _cms.PASSWORD, _cms.USERNAME)
    os.environ["ANTHROPIC_API_KEY"] = sentinel_key
    _cms.PASSWORD, _cms.USERNAME = sentinel_pw, "sentinel-user"
    try:
        leaked = client.get(f"/api/post/{post_id}").get_data(as_text=True)
        page = client.get("/").get_data(as_text=True)
        failures += not check(
            "API 응답에 비밀정보 없음",
            sentinel_key not in leaked and sentinel_pw not in leaked,
        )
        failures += not check(
            "화면 HTML에 비밀정보 없음",
            sentinel_key not in page and sentinel_pw not in page,
        )
    finally:
        if saved[0] is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = saved[0]
        _cms.PASSWORD, _cms.USERNAME = saved[1], saved[2]

    r = client.post("/api/lint",
                    json={"text": "최고의 완치 보장 전문병원, 내성발톱 절개도 합니다"})
    body = r.get_json()
    failures += not check(
        "POST /api/lint 의료법 탐지",
        r.status_code == 200 and body["law"]["block_count"] >= 3,
        body["law"]["summary"],
    )
    failures += not check(
        "POST /api/lint 포지셔닝 탐지",
        body["positioning"]["block_count"] >= 1,
        body["positioning"]["summary"],
    )

    # 비밀번호를 걸면 막히는지
    content_app.PASSWORD = "secret"
    guarded = content_app.app.test_client()
    failures += not check("비로그인 화면 차단", guarded.get("/").status_code == 302)
    failures += not check("비로그인 API 차단", guarded.get("/api/posts").status_code == 401)
    failures += not check(
        "틀린 비밀번호 거부",
        guarded.post("/login", data={"password": "nope"}).status_code == 401,
    )
    ok = guarded.post("/login", data={"password": "secret"})
    failures += not check("맞는 비밀번호 통과", ok.status_code == 302)
    failures += not check("로그인 후 API 접근", guarded.get("/api/posts").status_code == 200)
    content_app.PASSWORD = ""

    store.delete(post_id)

    print(f"\n{'=' * 46}")
    if failures:
        print(f"실패 {failures}건")
    else:
        print("전체 통과")
    print("=" * 46)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
