# -*- coding: utf-8 -*-
"""
CMS 자동 업로드.

안전장치 (기본 동작)
  1. 의료법 검사에서 위반이 잡힌 글은 업로드하지 않습니다.
  2. 항상 '미노출'로 저장합니다. 노출 전환은 사람이 화면에서 확인하고 누릅니다.
  3. 저장 직전 화면을 캡처해 남깁니다. 무엇이 올라갔는지 나중에 확인할 수 있습니다.
  4. dry_run=True면 폼만 채우고 저장은 누르지 않습니다.

이 순서를 바꾸려면 인자를 명시적으로 넘겨야 합니다.
자동화가 병원 블로그에 잘못된 글을 노출시키는 사고가 가장 비쌉니다.
"""

import logging
import os
import time

from publisher import browser, config, thumbnail

logger = logging.getLogger(__name__)

SHOT_DIR = os.getenv("CMS_SHOT_DIR", "cms_shots")


class PublishError(RuntimeError):
    pass


class ComplianceBlocked(PublishError):
    """의료법 검사를 통과하지 못해 업로드를 막은 경우."""


# ── 값 입력 도우미 ───────────────────────────────────────────────────
_SET_VALUE_JS = """
var el = arguments[0], val = arguments[1];
var proto = el.tagName === 'TEXTAREA'
  ? window.HTMLTextAreaElement.prototype
  : window.HTMLInputElement.prototype;
var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
setter.call(el, val);
el.dispatchEvent(new Event('input',  {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
"""


def _find(drv, selector: str, what: str):
    from selenium.webdriver.common.by import By

    els = drv.find_elements(By.CSS_SELECTOR, selector)
    if not els:
        raise PublishError(
            f"{what} 요소를 찾지 못했습니다 (셀렉터: {selector}). "
            "CMS 화면이 바뀌었을 수 있습니다. `python main.py inspect-cms`를 다시 실행하세요."
        )
    return els[0]


def _fill_text(drv, selector: str, value: str, what: str) -> None:
    el = _find(drv, selector, what)
    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    try:
        el.clear()
    except Exception:
        pass
    # 긴 값은 send_keys가 느리므로 JS로 넣고 이벤트를 발생시킨다.
    if len(value) > 200:
        drv.execute_script(_SET_VALUE_JS, el, value)
    else:
        el.send_keys(value)
        if el.get_attribute("value") != value:  # 일부 스크립트 입력칸 대응
            drv.execute_script(_SET_VALUE_JS, el, value)
    time.sleep(config.STEP_DELAY)


def _select_category(drv, selector: str, category: str) -> None:
    from selenium.webdriver.support.ui import Select

    el = _find(drv, selector, "카테고리")
    sel = Select(el)
    available = [o.text.strip() for o in sel.options]
    for option in sel.options:
        if option.text.strip() == category:
            sel.select_by_visible_text(option.text)
            time.sleep(config.STEP_DELAY)
            return
    raise PublishError(
        f"카테고리 '{category}'가 CMS 목록에 없습니다. 선택 가능: {available}"
    )


def _set_body(drv, mapping: dict, html: str) -> None:
    """본문을 넣는다. iframe 에디터와 textarea를 모두 지원한다."""
    from selenium.webdriver.common.by import By

    selector = mapping["fields"]["body"]

    if mapping.get("body_is_iframe"):
        frame = _find(drv, selector, "본문 에디터(iframe)")
        drv.switch_to.frame(frame)
        try:
            drv.execute_script(
                "document.body.innerHTML = arguments[0];"
                "document.body.dispatchEvent(new Event('input', {bubbles:true}));",
                html,
            )
        finally:
            drv.switch_to.default_content()
        time.sleep(config.STEP_DELAY)
        return

    el = _find(drv, selector, "본문")
    tag = el.tag_name.lower()
    if tag == "textarea":
        drv.execute_script(_SET_VALUE_JS, el, html)
    else:  # contenteditable div 등
        drv.execute_script(
            "arguments[0].innerHTML = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
            el,
            html,
        )
    time.sleep(config.STEP_DELAY)


def _upload_thumbnail(drv, selector: str, path: str) -> None:
    el = _find(drv, selector, "썸네일 업로드")
    # 숨겨진 file input도 send_keys는 동작한다. 필요하면 보이게 만든다.
    drv.execute_script(
        "arguments[0].style.display='block';"
        "arguments[0].style.visibility='visible';"
        "arguments[0].style.height='auto';"
        "arguments[0].style.opacity=1;",
        el,
    )
    el.send_keys(os.path.abspath(path))
    time.sleep(config.STEP_DELAY * 2)


def _set_expose(drv, mapping: dict, expose: bool) -> None:
    key = "show" if expose else "hide"
    selector = (mapping.get("expose") or {}).get(key)
    if not selector:
        logger.warning("노출 여부 라디오 셀렉터가 없습니다. CMS 기본값을 그대로 둡니다.")
        return
    el = _find(drv, selector, f"노출여부({key})")
    drv.execute_script("arguments[0].click();", el)
    time.sleep(config.STEP_DELAY)


def _click_submit(drv, mapping: dict) -> None:
    from selenium.webdriver.common.by import By

    selector = mapping.get("submit")
    if selector:
        el = _find(drv, selector, "저장 버튼")
        drv.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
        return

    # 셀렉터가 없으면 버튼 텍스트로 찾는다.
    for word in ("저장", "등록", "작성완료", "완료", "확인"):
        for el in drv.find_elements(By.CSS_SELECTOR, "button, input[type='submit'], a.btn"):
            text = (el.text or el.get_attribute("value") or "").strip()
            if word in text and el.is_displayed():
                drv.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                el.click()
                return
    raise PublishError(
        "저장 버튼을 찾지 못했습니다. cms_mapping.json의 submit에 셀렉터를 직접 넣으세요."
    )


def _screenshot(drv, tag: str) -> str:
    os.makedirs(SHOT_DIR, exist_ok=True)
    path = os.path.join(SHOT_DIR, f"{time.strftime('%Y%m%d-%H%M%S')}-{tag}.png")
    try:
        drv.save_screenshot(path)
        logger.info("화면 캡처: %s", path)
    except Exception as exc:
        logger.warning("캡처 실패: %s", exc)
        return ""
    return path


# ── 진입점 ───────────────────────────────────────────────────────────
def check_publishable(reports: dict, allow_violations: bool = False) -> None:
    """의료법 검사를 통과하지 못한 글의 업로드를 막는다."""
    if allow_violations:
        return
    law = reports.get("law", {})
    if law.get("block_count"):
        matched = ", ".join(
            f'"{f["matched"]}"' for f in law.get("findings", [])
            if f.get("severity") == "block"
        )
        raise ComplianceBlocked(
            f"의료법 위반 표현이 {law['block_count']}건 남아 있어 업로드를 중단했습니다: {matched}\n"
            "원고를 수정한 뒤 다시 시도하세요."
        )
    if law.get("missing_required"):
        labels = ", ".join(m["label"] for m in law["missing_required"])
        raise ComplianceBlocked(
            f"필수 기재 사항이 빠져 업로드를 중단했습니다: {labels}"
        )

    pos = reports.get("positioning", {})
    if pos.get("block_count"):
        matched = ", ".join(
            f'"{f["matched"]}"' for f in pos.get("findings", [])
            if f.get("severity") == "block"
        )
        raise ComplianceBlocked(
            f"본원에서 시행하지 않는 시술이 언급되어 업로드를 중단했습니다: {matched}\n"
            "허위광고에 해당할 수 있습니다. 원고를 수정한 뒤 다시 시도하세요."
        )


def publish(
    doc: dict,
    body_html: str,
    reports: dict = None,
    expose: bool = False,
    dry_run: bool = False,
    allow_violations: bool = False,
    thumbnail_path: str = "",
    headless: bool = None,
) -> dict:
    """생성된 글을 CMS에 업로드한다.

    expose=False (기본): 미노출로 저장. 사람이 확인하고 노출로 바꿉니다.
    dry_run=True       : 폼만 채우고 저장은 누르지 않습니다.
    """
    if reports:
        check_publishable(reports, allow_violations)

    mapping = config.load_mapping()
    fields = mapping["fields"]

    thumb = thumbnail_path or thumbnail.generate_for(doc)
    logger.info("썸네일 준비: %s (%.0fKB)", thumb, os.path.getsize(thumb) / 1024)

    result = {
        "dry_run": dry_run,
        "expose": expose,
        "thumbnail": thumb,
        "post_url": doc.get("post_url", ""),
        "shots": [],
    }

    with browser.driver(headless=headless) as drv:
        browser.login(drv)

        if drv.current_url.rstrip("/") != config.WRITE_URL.rstrip("/"):
            drv.get(config.WRITE_URL)
            time.sleep(config.STEP_DELAY * 2)

        _set_expose(drv, mapping, expose)
        _select_category(drv, fields["category"], doc.get("category", ""))
        _fill_text(drv, fields["title"], doc.get("h1", ""), "제목")
        _fill_text(drv, fields["post_url"], doc.get("post_url", ""), "포스트URL")
        _fill_text(drv, fields["meta_title"], doc.get("meta_title", ""), "MetaTitle")
        _fill_text(
            drv, fields["meta_description"], doc.get("meta_description", ""),
            "MetaDescription",
        )
        # 해시태그는 한 줄에 하나씩 (관리자 화면 안내 기준)
        _fill_text(
            drv, fields["hashtags"], "\n".join(doc.get("hashtags", []) or []), "해시태그"
        )
        _upload_thumbnail(drv, fields["thumbnail"], thumb)
        _set_body(drv, mapping, body_html)

        shot = _screenshot(drv, "before-save")
        if shot:
            result["shots"].append(shot)

        if dry_run:
            logger.info("dry_run: 저장 버튼을 누르지 않고 종료합니다.")
            result["saved"] = False
            result["message"] = (
                "폼을 채웠지만 저장하지 않았습니다(dry run). 캡처를 확인하세요."
            )
            return result

        _click_submit(drv, mapping)
        time.sleep(config.STEP_DELAY * 6)

        shot = _screenshot(drv, "after-save")
        if shot:
            result["shots"].append(shot)

        result["saved"] = True
        result["final_url"] = drv.current_url
        # 알림창이 떠 있으면 내용을 기록한다(저장 실패 사유가 여기 담기는 경우가 많다).
        try:
            alert = drv.switch_to.alert
            result["alert"] = alert.text
            alert.accept()
        except Exception:
            pass

        result["message"] = (
            "미노출 상태로 저장했습니다. CMS에서 내용을 확인한 뒤 노출로 바꾸세요."
            if not expose
            else "노출 상태로 저장했습니다."
        )

    return result
