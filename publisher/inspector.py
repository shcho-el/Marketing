# -*- coding: utf-8 -*-
"""
CMS 글쓰기 폼 구조 분석기.

실제 페이지를 열어 모든 입력 요소와 그 라벨을 훑고,
관리자 화면 라벨('제목( H1 )', 'MetaTitle', '썸네일 등록' …)로 필드를 매칭해
셀렉터 매핑 파일을 만듭니다.

이렇게 하는 이유: 남의 CMS 필드명을 추측해서 코드에 박아 두면
화면이 조금만 바뀌어도 엉뚱한 칸에 값이 들어갑니다.
실물을 보고 매핑을 만들고, 확신이 없는 항목은 사람이 채우도록 남깁니다.
"""

import json
import logging
import os
import time
from urllib.parse import urljoin

from publisher import browser, config

logger = logging.getLogger(__name__)


# 각 요소의 CSS 셀렉터와 주변 라벨 텍스트를 브라우저 안에서 수집한다.
_COLLECT_JS = r"""
function cssPath(el) {
  if (el.id) return '#' + CSS.escape(el.id);
  if (el.name) {
    var byName = document.querySelectorAll(
      el.tagName.toLowerCase() + '[name="' + el.name + '"]');
    if (byName.length === 1) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
  }
  var path = [], node = el;
  while (node && node.nodeType === 1 && node !== document.body) {
    var sel = node.tagName.toLowerCase();
    var parent = node.parentNode;
    if (parent) {
      var sameTag = Array.prototype.filter.call(
        parent.children, function (c) { return c.tagName === node.tagName; });
      if (sameTag.length > 1) {
        sel += ':nth-of-type(' + (sameTag.indexOf(node) + 1) + ')';
      }
    }
    path.unshift(sel);
    node = parent;
  }
  return path.join(' > ');
}

function labelText(el) {
  var texts = [];
  // 1) <label for="id">
  if (el.id) {
    var lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
    if (lab) texts.push(lab.innerText);
  }
  // 2) 감싸고 있는 <label>
  var wrap = el.closest('label');
  if (wrap) texts.push(wrap.innerText);
  // 3) 표 레이아웃: 같은 행의 첫 칸
  var row = el.closest('tr');
  if (row && row.cells && row.cells.length) texts.push(row.cells[0].innerText);
  // 4) div 레이아웃: 조상들의 앞선 형제
  var node = el, hops = 0;
  while (node && hops < 4) {
    var prev = node.previousElementSibling;
    if (prev && prev.innerText) { texts.push(prev.innerText); break; }
    node = node.parentElement; hops++;
  }
  return texts.join(' | ').replace(/\s+/g, ' ').trim().slice(0, 160);
}

var out = [];
document.querySelectorAll('input, select, textarea, iframe, [contenteditable="true"]')
  .forEach(function (el) {
    var rect = el.getBoundingClientRect();
    out.push({
      tag: el.tagName.toLowerCase(),
      type: (el.getAttribute('type') || '').toLowerCase(),
      name: el.getAttribute('name') || '',
      id: el.id || '',
      cls: el.getAttribute('class') || '',
      placeholder: el.getAttribute('placeholder') || '',
      value: (el.tagName.toLowerCase() === 'select' || el.type === 'file')
             ? '' : String(el.value || '').slice(0, 40),
      options: el.tagName.toLowerCase() === 'select'
        ? Array.prototype.map.call(el.options, function (o) { return o.text.trim(); })
        : [],
      selector: cssPath(el),
      label: labelText(el),
      visible: rect.width > 0 && rect.height > 0,
    });
  });
return out;
"""

_BUTTONS_JS = r"""
var out = [];
document.querySelectorAll(
  "button, input[type='submit'], input[type='button'], a.btn, .btn").forEach(function (el) {
  var t = (el.innerText || el.value || '').replace(/\s+/g, ' ').trim();
  if (!t) return;
  out.push({
    tag: el.tagName.toLowerCase(),
    text: t.slice(0, 40),
    id: el.id || '',
    cls: el.getAttribute('class') || '',
    selector: el.id ? '#' + CSS.escape(el.id) : '',
  });
});
return out;
"""


def _matches(label: str, aliases: list) -> bool:
    flat = (label or "").replace(" ", "")
    return any(a.replace(" ", "") in flat for a in aliases)


def _pick(elements: list, field: str, aliases: list):
    """라벨과 요소 종류를 함께 보고 가장 그럴듯한 요소를 고른다."""
    labeled = [e for e in elements if _matches(e["label"], aliases)]

    def prefer(cands, predicate):
        hits = [c for c in cands if predicate(c)]
        return hits or cands

    if field == "thumbnail":
        pool = prefer(labeled or elements, lambda e: e["type"] == "file")
        return pool[0] if pool and pool[0]["type"] == "file" else None

    if field == "category":
        pool = prefer(labeled or elements, lambda e: e["tag"] == "select")
        return pool[0] if pool and pool[0]["tag"] == "select" else None

    if field == "expose":
        # 라디오 그룹 - name이 같은 라디오 두 개
        radios = [e for e in (labeled or elements) if e["type"] == "radio"]
        return radios[0] if radios else None

    if field == "hashtags":
        pool = prefer(labeled, lambda e: e["tag"] == "textarea")
        return pool[0] if pool else None

    if field == "body":
        # 본문은 라벨이 없는 경우가 많다. textarea / iframe / contenteditable 중
        # 가장 큰 것을 고른다.
        cands = [
            e
            for e in elements
            if e["tag"] in ("textarea", "iframe")
            or "contenteditable" in (e["cls"] or "")
        ]
        cands = [e for e in cands if e["visible"]] or cands
        # 해시태그 textarea를 본문으로 잘못 잡지 않도록 제외
        cands = [
            e for e in cands if not _matches(e["label"], config.FIELD_LABELS["hashtags"])
        ]
        return cands[-1] if cands else None

    pool = prefer(labeled, lambda e: e["tag"] in ("input", "textarea"))
    return pool[0] if pool else None


def build_mapping(elements: list, buttons: list) -> dict:
    """수집한 요소로 셀렉터 매핑을 조립한다."""
    fields, notes = {}, {}

    for field, aliases in config.FIELD_LABELS.items():
        picked = _pick(elements, field, aliases)
        if picked:
            fields[field] = picked["selector"]
            notes[field] = {
                "tag": picked["tag"],
                "type": picked["type"],
                "name": picked["name"],
                "label": picked["label"],
                "confident": _matches(picked["label"], aliases),
            }
            if field == "category" and picked["options"]:
                notes[field]["options"] = picked["options"]
        else:
            fields[field] = ""
            notes[field] = {"confident": False, "label": ""}

    # 노출/미노출 라디오는 두 개를 각각 잡아 둔다.
    expose_radios = [e for e in elements if e["type"] == "radio"]
    expose_map = {}
    for e in expose_radios:
        text = (e["label"] or "").replace(" ", "")
        if "미노출" in text:
            expose_map["hide"] = e["selector"]
        elif "노출" in text:
            expose_map.setdefault("show", e["selector"])
    # 라벨로 못 가르면 value로 시도
    if len(expose_map) < 2 and len(expose_radios) >= 2:
        expose_map.setdefault("show", expose_radios[0]["selector"])
        expose_map.setdefault("hide", expose_radios[1]["selector"])

    # 본문이 iframe이면 별도 표시 - 값 입력 방식이 달라진다.
    body_note = notes.get("body", {})
    body_is_iframe = body_note.get("tag") == "iframe"

    # 저장 버튼 후보
    save_words = ("저장", "등록", "작성완료", "확인", "완료")
    save_btn = ""
    for b in buttons:
        if any(w in b["text"] for w in save_words):
            save_btn = b["selector"] or ""
            if save_btn:
                break

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "write_url": config.WRITE_URL,
        "fields": fields,
        "expose": expose_map,
        "body_is_iframe": body_is_iframe,
        "submit": save_btn,
        "submit_text_candidates": [
            b["text"] for b in buttons if any(w in b["text"] for w in save_words)
        ],
        "_notes": notes,
        "_hint": (
            "confident=false 인 항목은 자동 매칭에 확신이 없다는 뜻입니다. "
            f"{config.DUMP_PATH}에서 올바른 셀렉터를 찾아 fields에 직접 넣으세요."
        ),
    }


LOG_DIR = "logs"


def _keep_evidence(drv, why: str) -> list:
    """실패한 순간의 화면을 남긴다.

    "안 되던데"만으로는 로그인에서 막힌 건지, 글쓰기 화면까지 갔는데 칸을
    못 읽은 건지 알 수 없습니다. 그림 한 장과 주소 한 줄이면 바로 갈립니다.
    """
    saved = []
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        return saved

    shot = os.path.join(LOG_DIR, "cms-실패화면.png")
    page = os.path.join(LOG_DIR, "cms-실패화면.html")
    try:
        drv.save_screenshot(shot)
        saved.append(shot)
    except Exception:  # 드라이버가 이미 죽었을 수도 있다
        pass
    try:
        with open(page, "w", encoding="utf-8") as fp:
            fp.write(drv.page_source)
        saved.append(page)
    except Exception:
        pass
    try:
        logger.error("%s — 그때 열려 있던 주소: %s", why, drv.current_url)
    except Exception:
        pass
    return saved


# 목록 화면에는 입력칸이 거의 없다. 글쓰기 폼으로 넘어가는 링크를 찾아 따라간다.
_FIND_WRITE_LINK_JS = r"""
var words = ['포스팅등록','글쓰기','새글','등록하기','글등록','작성하기'];
var best = null;
document.querySelectorAll("a, button, input[type='button'], input[type='submit']")
  .forEach(function (el) {
    var t = (el.innerText || el.value || '').replace(/\s+/g, ' ').trim();
    if (!t) return;
    var flat = t.replace(/\s/g, '');
    for (var i = 0; i < words.length; i++) {
      if (flat.indexOf(words[i]) !== -1) {
        if (!best || i < best.rank) {
          best = { rank: i, text: t, href: el.getAttribute('href') || '', id: el.id || '' };
        }
        break;
      }
    }
  });
return best;
"""


def _field_count(elements: list) -> int:
    """폼이라 할 만한 입력칸이 몇 개인지 센다."""
    return sum(
        1 for e in elements
        if e.get("tag") in ("input", "select", "textarea")
        and e.get("type") not in ("hidden",)
    )


def _goto_write_form(drv):
    """목록 화면에 있으면 글쓰기 폼으로 이동한다. 이동했으면 그 주소를 돌려준다."""
    link = drv.execute_script(_FIND_WRITE_LINK_JS)
    if not link:
        return ""

    logger.info("글쓰기 링크를 찾았습니다: %s", link.get("text"))
    href = (link.get("href") or "").strip()
    before = drv.current_url

    if href and not href.startswith("#") and not href.lower().startswith("javascript"):
        drv.get(urljoin(before, href))
    else:
        # href 가 없으면 눌러 본다
        from selenium.webdriver.common.by import By

        try:
            if link.get("id"):
                drv.find_element(By.ID, link["id"]).click()
            else:
                drv.find_element(
                    By.XPATH, f"//*[normalize-space(text())={_xpath_literal(link['text'])}]"
                ).click()
        except Exception as exc:
            logger.warning("글쓰기 링크를 누르지 못했습니다: %s", exc)
            return ""

    time.sleep(config.STEP_DELAY * 4)
    return drv.current_url if drv.current_url != before else ""


def _xpath_literal(text: str) -> str:
    """따옴표가 섞인 문자열을 XPath 리터럴로 만든다."""
    if "'" not in text:
        return f"'{text}'"
    if '"' not in text:
        return f'"{text}"'
    parts = text.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"


def inspect(headless: bool = None, save: bool = True) -> dict:
    """CMS에 로그인해 글쓰기 폼을 분석하고 매핑을 만든다."""
    with browser.driver(headless=headless) as drv:
        try:
            browser.login(drv)

            if drv.current_url.rstrip("/") != config.WRITE_URL.rstrip("/"):
                drv.get(config.WRITE_URL)
                time.sleep(config.STEP_DELAY * 2)

            elements = drv.execute_script(_COLLECT_JS)

            # 여기가 목록 화면이면 입력칸이 거의 없다. 글쓰기 폼으로 한 번 더 간다.
            found_url = ""
            if _field_count(elements) < 5:
                logger.info("입력칸이 %d개뿐입니다. 글쓰기 폼을 찾습니다.", _field_count(elements))
                found_url = _goto_write_form(drv)
                if found_url:
                    logger.info("글쓰기 폼으로 이동했습니다: %s", found_url)
                    elements = drv.execute_script(_COLLECT_JS)

            buttons = drv.execute_script(_BUTTONS_JS)
            page_title = drv.title
            html_len = len(drv.page_source)
        except Exception as exc:
            files = _keep_evidence(drv, str(exc))
            exc.evidence = files  # 위쪽에서 사람에게 보여 준다
            raise

    logger.info("입력 요소 %d개, 버튼 %d개 수집", len(elements), len(buttons))

    dump = {
        "page_title": page_title,
        "url": found_url or config.WRITE_URL,
        "write_url_found": found_url,
        "html_length": html_len,
        "elements": elements,
        "buttons": buttons,
    }
    if save:
        with open(config.DUMP_PATH, "w", encoding="utf-8") as fp:
            json.dump(dump, fp, ensure_ascii=False, indent=2)
        logger.info("폼 덤프 저장: %s", config.DUMP_PATH)

    mapping = build_mapping(elements, buttons)
    if save:
        config.save_mapping(mapping)
    return {"mapping": mapping, "dump": dump, "write_url": found_url}


def report(mapping: dict) -> str:
    """사람이 읽을 매핑 요약."""
    lines = ["", "=" * 60, "CMS 폼 매핑 결과", "=" * 60]
    for field, selector in mapping["fields"].items():
        note = mapping["_notes"].get(field, {})
        if not selector:
            mark, extra = "❌", "찾지 못함 — 직접 입력 필요"
        elif note.get("confident"):
            mark, extra = "✅", f"{note.get('tag', '')}[{note.get('type', '')}]"
        else:
            mark, extra = "⚠️ ", f"{note.get('tag', '')} — 라벨 불일치, 확인 권장"
        lines.append(f"  {mark} {field:<18} {selector or '-':<40} {extra}")

    lines.append("")
    lines.append(f"  노출/미노출 라디오: {mapping.get('expose') or '찾지 못함'}")
    lines.append(f"  본문 iframe 여부  : {mapping.get('body_is_iframe')}")
    lines.append(f"  저장 버튼         : {mapping.get('submit') or '텍스트로 탐색'}")
    if mapping.get("submit_text_candidates"):
        lines.append(f"  저장 버튼 후보    : {mapping['submit_text_candidates']}")
    if mapping["_notes"].get("category", {}).get("options"):
        lines.append(f"  카테고리 목록     : {mapping['_notes']['category']['options']}")
    lines.append("")
    lines.append(f"  매핑 파일: {config.MAPPING_PATH}")
    lines.append(f"  전체 덤프: {config.DUMP_PATH}")
    lines.append("=" * 60)
    return "\n".join(lines)
