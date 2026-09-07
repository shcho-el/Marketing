# -*- coding: utf-8 -*-
"""
CMS 자동 업로드 점검 (브라우저 없이 실행).

  python test_publish.py

검증 대상
  1. 썸네일 규격 (880x580, 300KB 이하, 한글 렌더링)
  2. 셀렉터 자동 매핑 - 실제 관리자 화면과 같은 구조의 폼에서 필드를 올바로 찾는지
  3. 업로드 절차 - 안전장치(의료법 차단·미노출 기본값·연습 실행)와 입력 순서

브라우저 상호작용 자체는 여기서 검증할 수 없습니다.
그 부분은 tools/mock_cms.py를 띄우고 실제로 돌려서 확인하세요 (CONTENT.md 참고).
"""

import os
import sys
import tempfile

from publisher import config as cms_config
from publisher import inspector, thumbnail
from publisher import publish as cms


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'✅' if ok else '❌'} {name}{(' — ' + detail) if detail else ''}")
    return ok


# ── 목 CMS의 HTML을 _COLLECT_JS와 같은 형태로 수집 ─────────────────────
def collect_from_html(html: str) -> tuple:
    """브라우저 없이 폼 요소를 수집한다.

    실제로는 페이지 안에서 _COLLECT_JS가 하는 일을, 표 레이아웃 기준으로
    BeautifulSoup으로 똑같이 재현합니다. 라벨은 같은 행의 첫 칸에서 가져옵니다.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    def label_for(el):
        texts = []
        if el.get("id"):
            lab = soup.find("label", attrs={"for": el["id"]})
            if lab:
                texts.append(lab.get_text(" ", strip=True))
        wrap = el.find_parent("label")
        if wrap:
            texts.append(wrap.get_text(" ", strip=True))
        row = el.find_parent("tr")
        if row:
            cells = row.find_all(["th", "td"])
            if cells:
                texts.append(cells[0].get_text(" ", strip=True))
        return " | ".join(texts)[:160]

    def selector_for(el):
        if el.get("id"):
            return f"#{el['id']}"
        if el.get("name"):
            same = soup.find_all(el.name, attrs={"name": el["name"]})
            if len(same) == 1:
                return f'{el.name}[name="{el["name"]}"]'
        # 브라우저의 cssPath와 동일하게, 같은 태그가 여럿이면 nth-of-type 경로를 만든다.
        path, node = [], el
        while node is not None and node.name and node.name != "[document]":
            siblings = [c for c in node.parent.find_all(node.name, recursive=False)] \
                if node.parent else []
            step = node.name
            if len(siblings) > 1:
                step += f":nth-of-type({siblings.index(node) + 1})"
            path.insert(0, step)
            node = node.parent
            if node is not None and node.name == "body":
                break
        return " > ".join(path)

    elements = []
    for el in soup.find_all(["input", "select", "textarea", "iframe"]):
        elements.append(
            {
                "tag": el.name,
                "type": (el.get("type") or "").lower(),
                "name": el.get("name", ""),
                "id": el.get("id", ""),
                "cls": " ".join(el.get("class", [])),
                "placeholder": el.get("placeholder", ""),
                "value": "",
                "options": [o.get_text(strip=True) for o in el.find_all("option")]
                if el.name == "select"
                else [],
                "selector": selector_for(el),
                "label": label_for(el),
                "visible": True,
            }
        )

    buttons = []
    for el in soup.find_all(["button", "input"]):
        if el.name == "input" and el.get("type") not in ("submit", "button"):
            continue
        text = el.get_text(" ", strip=True) or el.get("value", "")
        if not text:
            continue
        buttons.append(
            {
                "tag": el.name,
                "text": text[:40],
                "id": el.get("id", ""),
                "cls": " ".join(el.get("class", [])),
                "selector": f"#{el['id']}" if el.get("id") else "",
            }
        )
    return elements, buttons


# ── 가짜 드라이버 ────────────────────────────────────────────────────
class FakeOption:
    def __init__(self, text):
        self.text = text
        self.clicked = False

    def click(self):
        self.clicked = True

    def is_selected(self):
        return self.clicked

    def get_attribute(self, name):
        return self.text if name == "value" else None

    def value_of_css_property(self, name):
        # Select()가 옵션의 표시 여부를 확인할 때 쓴다.
        return {"display": "block", "visibility": "visible"}.get(name, "")

    def is_enabled(self):
        return True

    def is_displayed(self):
        return True


class FakeElement:
    def __init__(self, selector, tag="input", type_="text", options=None):
        self.selector = selector
        self.tag_name = tag
        self._type = type_
        self.value = ""
        self.keys_sent = []
        self.options = [FakeOption(o) for o in (options or [])]
        self.clicked = False

    def clear(self):
        self.value = ""

    def send_keys(self, v):
        self.keys_sent.append(v)
        self.value += str(v)

    def click(self):
        self.clicked = True

    def is_displayed(self):
        return True

    def get_attribute(self, name):
        if name == "value":
            return self.value
        return None

    def get_dom_attribute(self, name):
        # Select()가 multiple 여부를 이 메서드로 확인한다.
        return None

    def find_elements(self, by, value):
        if self.tag_name != "select":
            return []
        if "option" in str(value).lower():
            # select_by_visible_text의 xpath는 따옴표로 감싼 텍스트를 담고 있다.
            for quote in ('"', "'"):
                if quote in str(value):
                    wanted = str(value).split(quote)[1]
                    return [o for o in self.options if o.text == wanted]
            return self.options
        return []


class FakeAlert:
    text = ""

    def accept(self):
        pass


class FakeSwitchTo:
    def __init__(self, drv):
        self.drv = drv

    def frame(self, el):
        self.drv.actions.append(("switch_frame", getattr(el, "selector", "")))

    def default_content(self):
        self.drv.actions.append(("switch_default", ""))

    @property
    def alert(self):
        raise Exception("no alert")


class FakeDriver:
    """publish()가 브라우저에 시키는 일을 그대로 기록하는 대역."""

    def __init__(self, mapping, body_tag="textarea"):
        self.actions = []
        self.scripts = []
        self.current_url = cms_config.WRITE_URL
        self.title = "글쓰기"
        self.switch_to = FakeSwitchTo(self)
        self.elements = {}

        fields = mapping["fields"]
        self.elements[fields["category"]] = FakeElement(
            fields["category"], "select", "",
            ["발톱무좀치료", "내성발톱치료", "문제성발톱", "발톱관리"],
        )
        for key in ("title", "post_url", "meta_title", "meta_description"):
            self.elements[fields[key]] = FakeElement(fields[key], "input", "text")
        self.elements[fields["hashtags"]] = FakeElement(
            fields["hashtags"], "textarea", ""
        )
        self.elements[fields["thumbnail"]] = FakeElement(
            fields["thumbnail"], "input", "file"
        )
        self.elements[fields["body"]] = FakeElement(fields["body"], body_tag, "")
        for sel in (mapping.get("expose") or {}).values():
            self.elements[sel] = FakeElement(sel, "input", "radio")
        if mapping.get("submit"):
            self.elements[mapping["submit"]] = FakeElement(
                mapping["submit"], "button", "submit"
            )

    def find_elements(self, by, selector):
        el = self.elements.get(selector)
        return [el] if el else []

    def execute_script(self, script, *args):
        self.scripts.append((script[:40], args))
        if "setter.call" in script and len(args) >= 2:
            args[0].value = args[1]
            self.actions.append(("set_value", args[0].selector, str(args[1])))
        elif "innerHTML" in script and len(args) >= 2:
            args[0].value = args[1]
            self.actions.append(("set_html", args[0].selector, str(args[1])))
        elif "document.body.innerHTML" in script and args:
            self.actions.append(("set_iframe_html", "", str(args[0])))
        elif ".click()" in script and args:
            args[0].clicked = True
            self.actions.append(("click", args[0].selector, ""))
        return None

    def get(self, url):
        self.current_url = url
        self.actions.append(("get", url, ""))

    def save_screenshot(self, path):
        with open(path, "wb") as fp:
            fp.write(b"\x89PNG\r\n\x1a\n")
        self.actions.append(("screenshot", path, ""))
        return True

    def set_page_load_timeout(self, n):
        pass

    def quit(self):
        pass


def main() -> int:
    failures = 0
    from content import renderer
    from test_content import FIXTURE
    from content import generator

    doc = generator._normalize(dict(FIXTURE), FIXTURE["category"], FIXTURE["primary_keyword"])

    # ── 1. 썸네일 ──────────────────────────────────────────────────
    print("\n[1] 썸네일 생성")
    with tempfile.TemporaryDirectory() as tmp:
        path = thumbnail.generate_for(doc, out_dir=tmp)
        from PIL import Image

        img = Image.open(path)
        size_kb = os.path.getsize(path) / 1024
        failures += not check("규격 880x580", img.size == (880, 580), f"{img.size}")
        failures += not check("용량 300KB 이하", size_kb <= 300, f"{size_kb:.0f}KB")
        failures += not check("JPEG 형식", img.format == "JPEG", img.format)

    # ── 2. 셀렉터 자동 매핑 ────────────────────────────────────────
    print("\n[2] 셀렉터 자동 매핑 (실제 관리자 화면과 같은 구조)")
    sys.path.insert(0, "tools")
    from mock_cms import CATEGORIES, WRITE_HTML

    html = WRITE_HTML.format(
        options="".join(f'<option value="{c}">{c}</option>' for c in CATEGORIES)
    )
    elements, buttons = collect_from_html(html)
    mapping = inspector.build_mapping(elements, buttons)

    expected = {
        "category": "#ca_name",
        "title": "#wr_subject",
        "post_url": "#wr_link1",
        "meta_title": "#wr_meta_title",
        "meta_description": "#wr_meta_desc",
        "hashtags": "#wr_tag",
        "thumbnail": "#bf_file",
        "body": "#wr_content",
    }
    for field, want in expected.items():
        got = mapping["fields"].get(field)
        failures += not check(f"{field} 매핑", got == want, f"{got} (기대 {want})")

    failures += not check(
        "노출/미노출 라디오 구분",
        bool(mapping["expose"].get("show")) and bool(mapping["expose"].get("hide")),
        str(mapping["expose"]),
    )
    failures += not check("저장 버튼 탐지", mapping["submit"] == "#btn_submit", mapping["submit"])
    failures += not check(
        "카테고리 목록 수집",
        mapping["_notes"]["category"].get("options") == CATEGORIES,
    )
    failures += not check(
        "해시태그를 본문으로 오인하지 않음",
        mapping["fields"]["body"] != mapping["fields"]["hashtags"],
    )

    # ── 3. 업로드 절차 ─────────────────────────────────────────────
    print("\n[3] 업로드 절차와 안전장치")
    body_html = renderer.render_body(doc, include_schema=True)

    clean = {"law": {"passed": True, "block_count": 0, "warn_count": 0,
                     "findings": [], "missing_required": []}}
    dirty = {"law": {"passed": False, "block_count": 1, "warn_count": 0,
                     "findings": [{"severity": "block", "matched": "완치 보장"}],
                     "missing_required": []}}
    incomplete = {"law": {"passed": False, "block_count": 0, "warn_count": 0,
                          "findings": [],
                          "missing_required": [{"label": "부작용 안내"}]}}

    # 3-1. 의료법 위반이면 업로드 차단
    for label, rep in (("위반 표현", dirty), ("필수 기재 누락", incomplete)):
        try:
            cms.check_publishable(rep)
            failures += not check(f"{label} 시 차단", False, "차단되지 않음")
        except cms.ComplianceBlocked as exc:
            failures += not check(f"{label} 시 차단", True, str(exc).split("\n")[0][:48])

    try:
        cms.check_publishable(clean)
        failures += not check("정상 원고는 통과", True)
    except cms.ComplianceBlocked:
        failures += not check("정상 원고는 통과", False)

    # 3-2. 실제 업로드 흐름 (가짜 드라이버)
    with tempfile.TemporaryDirectory() as tmp:
        thumb = thumbnail.generate_for(doc, out_dir=tmp)
        cms_config.MAPPING_PATH = os.path.join(tmp, "m.json")
        cms_config.save_mapping(mapping)
        cms.SHOT_DIR = os.path.join(tmp, "shots")

        import contextlib

        from publisher import browser as pb

        def run(dry_run, expose, body_tag="textarea"):
            drv = FakeDriver(mapping, body_tag=body_tag)

            @contextlib.contextmanager
            def fake_driver(headless=None):
                yield drv

            orig_driver, orig_login = pb.driver, pb.login
            cms.browser.driver = fake_driver
            cms.browser.login = lambda d: None
            try:
                result = cms.publish(
                    doc=doc, body_html=body_html, reports=clean,
                    expose=expose, dry_run=dry_run, thumbnail_path=thumb,
                )
            finally:
                cms.browser.driver, cms.browser.login = orig_driver, orig_login
            return drv, result

        drv, result = run(dry_run=True, expose=False)
        failures += not check("연습 실행은 저장하지 않음", result["saved"] is False)
        failures += not check(
            "연습 실행에서도 저장 버튼 미클릭",
            not drv.elements[mapping["submit"]].clicked,
        )
        failures += not check("저장 전 화면 캡처", len(result["shots"]) >= 1)

        drv, result = run(dry_run=False, expose=False)
        failures += not check("실제 저장 시 버튼 클릭", drv.elements[mapping["submit"]].clicked)
        failures += not check("미노출 라디오 선택", drv.elements[mapping["expose"]["hide"]].clicked)
        failures += not check(
            "노출 라디오는 건드리지 않음",
            not drv.elements[mapping["expose"]["show"]].clicked,
        )

        cat_el = drv.elements[mapping["fields"]["category"]]
        failures += not check(
            "카테고리 선택",
            any(o.clicked and o.text == doc["category"] for o in cat_el.options),
            doc["category"],
        )
        failures += not check(
            "제목 입력",
            drv.elements[mapping["fields"]["title"]].value == doc["h1"],
        )
        failures += not check(
            "포스트URL 입력",
            drv.elements[mapping["fields"]["post_url"]].value == doc["post_url"],
        )
        failures += not check(
            "MetaTitle 입력",
            drv.elements[mapping["fields"]["meta_title"]].value == doc["meta_title"],
        )
        failures += not check(
            "해시태그 줄바꿈 구분",
            drv.elements[mapping["fields"]["hashtags"]].value
            == "\n".join(doc["hashtags"]),
        )
        failures += not check(
            "썸네일 파일 경로 전달",
            os.path.abspath(thumb)
            in drv.elements[mapping["fields"]["thumbnail"]].keys_sent,
        )
        body_el = drv.elements[mapping["fields"]["body"]]
        failures += not check(
            "본문 HTML 주입",
            body_el.value == body_html,
            f"{len(body_el.value)}자",
        )
        failures += not check("저장 후 화면 캡처", len(result["shots"]) >= 2)
        failures += not check("미노출 안내 메시지", "미노출" in result["message"])

        # 노출 선택 시에는 노출 라디오를 누른다
        drv, result = run(dry_run=False, expose=True)
        failures += not check("노출 선택 시 노출 라디오", drv.elements[mapping["expose"]["show"]].clicked)

        # iframe 에디터 CMS 대응
        iframe_mapping = dict(mapping)
        iframe_mapping["body_is_iframe"] = True
        cms_config.save_mapping(iframe_mapping)
        drv = FakeDriver(iframe_mapping, body_tag="iframe")

        @contextlib.contextmanager
        def fake_driver(headless=None):
            yield drv

        orig_driver, orig_login = pb.driver, pb.login
        cms.browser.driver = fake_driver
        cms.browser.login = lambda d: None
        try:
            cms.publish(doc=doc, body_html=body_html, reports=clean,
                        expose=False, dry_run=True, thumbnail_path=thumb)
        finally:
            cms.browser.driver, cms.browser.login = orig_driver, orig_login

        kinds = [a[0] for a in drv.actions]
        failures += not check(
            "iframe 에디터 전환/복귀",
            "switch_frame" in kinds and "switch_default" in kinds,
        )

    print(f"\n{'=' * 46}")
    print(f"실패 {failures}건" if failures else "전체 통과")
    print("=" * 46)
    if not failures:
        print("\n브라우저 상호작용은 여기서 검증되지 않습니다.")
        print("tools/mock_cms.py를 띄우고 실제로 한 번 돌려 보세요 (CONTENT.md 참고).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
