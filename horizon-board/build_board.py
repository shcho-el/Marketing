"""Build Board.html for the Apps Script status board from the Claude dashboard page.

The dashboard page (index.html) is copied as-is — same markup, styles and drawing
code — and wrapped with:
  * fixed design tokens that stand in for the dashboard host's theme tokens,
  * a small `dash` / `claude` shim that feeds the same drawings from getRaw()
    and saves through saveStatus(),
  * viewer/editor wording.

Usage: python3 build_board.py <dashboard index.html> <output Board.html>
"""
import re
import sys

src, out = sys.argv[1], sys.argv[2]
h = open(src, encoding='utf-8').read()

def rep(old, new, count=1):
    global h
    assert h.count(old) == count, (old[:80], h.count(old))
    h = h.replace(old, new)

# --- strip host-only bits
rep('<meta name="dash-one-writer">\n', '')
h = re.sub(r'@font-face \{ font-family: "HZ Pretendard";[^\n]*\n', '', h)
rep('--hz-font: "HZ Pretendard", var(--font-anthropic-sans),', '--hz-font: "Pretendard", "Pretendard Variable",')

# --- wording that only fits the Claude dashboard
rep('편집 권한이 있는 사람만 저장할 수 있고, 저장한 내용은 이 대시보드를 여는 모든 사람에게 보여요.',
    '편집 링크로 연 사람만 저장할 수 있고, 저장한 내용은 이 현황판을 여는 모든 사람에게 보여요.')
rep('저장하지 못했어요. 이 대시보드의 편집 권한이 있어야 저장할 수 있어요.',
    '저장하지 못했어요. 편집 링크로 열어야 저장할 수 있어요.')
rep('지원자 목록 시트를 읽을 수 있는 사람에게만 보여요. 행을 누르면 입력칸에 불러와요.',
    '<span class="hz-viewer-only">상태·촬영일은 편집 링크에서 바꿀 수 있어요.</span><span class="hz-edit-only">행을 누르면 입력칸에 불러와요.</span>')
rep('이름을 누르면 아래 입력칸에 불러와요.', '<span class="hz-edit-only">이름을 누르면 아래 입력칸에 불러와요.</span>')
rep('<p class="hz-note">카드를 누르면 아래 입력칸에 불러와요.</p>',
    '<p class="hz-note"><span class="hz-edit-only">카드를 누르면 아래 입력칸에 불러와요.</span><span class="hz-viewer-only">단계별로 지원자를 모아 보여줘요.</span></p>')
rep('<section class="hz-sec" id="edit">', '<section class="hz-sec hz-edit-only" id="edit">')
rep('<p class="hz-alert" id="reqwarn" hidden>',
    '<p class="hz-alert" id="loaderr" hidden>데이터를 불러오지 못했어요. 잠시 후 새로고침해 주세요.</p>\n  <p class="hz-alert" id="reqwarn" hidden>')
# everything reloads together here, every 5 minutes
rep('  const REFRESH_MIN = 30;', '  const REFRESH_MIN = 5;')

style_end = h.index('</style>')
styles, body = h[:style_end + len('</style>')], h[style_end + len('</style>'):]
first_script = body.index('<script>')
markup, scripts = body[:first_script], body[first_script:]

head = '''<!DOCTYPE html>
<html lang="ko">
<head>
<base target="_blank">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<script>
/* The two d3 helpers the dashboard drawings use (group, format) — no external library needed */
window.d3 = window.d3 || {
  group: (arr, f) => { const m = new Map(); (arr || []).forEach((x) => { const k = f(x); if (!m.has(k)) m.set(k, []); m.get(k).push(x); }); return m; },
  format: () => (n) => Number(n).toLocaleString('en-US'),
};
</script>
<style>
/* Tokens that the Claude dashboard host normally provides */
:root {
  --color-bg: #ffffff; --color-fg: #2b2724; --color-fg-muted: #6b625c; --color-panel: #ffffff;
  --color-border-line: #e3ddd8; --color-ok: #3f8a5f; --color-warn: #c98a1e; --color-bad: #b83a55;
  --cds-gap-xs: 4px; --cds-gap-sm: 8px; --cds-gap-md: 12px; --cds-gap-lg: 16px; --cds-gap-xl: 24px;
  --cds-pad-xs: 4px; --cds-pad-sm: 8px; --cds-pad-md: 12px; --cds-pad-lg: 16px; --cds-pad-xl: 24px;
  --cds-radius: 10px; --cds-font-size-caption: 12.5px; --cds-font-size-body: 15px;
  --cds-font-size-heading: 18px; --cds-font-size-title: 28px; --cds-font-weight-medium: 600;
  --font-anthropic-sans: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
  color-scheme: light;
}
html, body { margin: 0; background: #f4f2f0; color: var(--color-fg); font-family: var(--font-anthropic-sans); font-size: 15px; }
.hz-page { max-width: 1240px; margin: 0 auto; padding-block: 20px 48px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.dash-select { appearance: none; -webkit-appearance: none; font: inherit; font-size: var(--cds-font-size-body); color: var(--color-fg); background-color: var(--color-bg); border: 1px solid #d8d1cb; border-radius: var(--cds-radius); padding: 7px 30px 7px 9px; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%236b625c'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 10px center; }
[hidden] { display: none !important; }
body:not(.can-edit) .hz-edit-only { display: none !important; }
body.can-edit .hz-viewer-only { display: none !important; }
</style>
'''

shim = '''
<script>
/* Feeds the dashboard's own drawings from the Apps Script server (getRaw) and saves through saveStatus. */
const BOOT = <?!= JSON.stringify(boot) ?>;
if (BOOT.canEdit) document.body.classList.add('can-edit');
window.dash = (() => {
  const src = {}, calcs = [], calcVal = {}, draws = [], onDatas = [];
  let status = 'loading';
  const value = (id) => (id in calcVal ? calcVal[id] : (src[id] || []));
  function compute() {
    calcs.forEach((c) => { try { calcVal[c.id] = c.fn(...c.inputs.map(value)); } catch (e) { console.error(c.id, e); calcVal[c.id] = []; } });
  }
  function runDraw(d) {
    document.querySelectorAll('[data-draw="' + d.name + '"]').forEach((el) => {
      if (el.closest('[hidden]')) return;
      try {
        if (typeof d.spec === 'function') d.spec(el);
        else { if (!el.__hzMade) el.__hzMade = d.spec.mount ? d.spec.mount(el) : {}; d.spec.update && d.spec.update(el, el.__hzMade); }
      } catch (e) { console.error(d.name, e); }
    });
  }
  function render() { onDatas.forEach((f) => { try { f(); } catch (e) { console.error(e); } }); draws.forEach(runDraw); }
  let timer = null;
  return {
    colors: ['#a8523b'],
    loader() {},
    calc(id, spec) { calcs.push({id, inputs: spec.inputs || [], fn: spec.fn}); },
    data(id) {
      const has = (id in src) || calcs.some((c) => c.id === id);
      return {status: has ? status : 'missing', data: status === 'ok' ? value(id) : [], truncated: false, refreshing: false, columns: []};
    },
    draw(name, spec) { if (spec === undefined) { draws.filter((d) => d.name === name).forEach(runDraw); return; } draws.push({name, spec}); },
    onData(fn) { onDatas.push(fn); },
    params() { return {}; }, setParams() {}, resetParams() {}, setLink() {},
    refresh() { clearTimeout(timer); timer = setTimeout(load, 300); },
    _set(raw) {
      ['mails', 'applicants', 'requests', 'schedule'].forEach((k) => { src[k] = raw[k] || []; });
      status = 'ok';
      document.querySelectorAll('#loaderr').forEach((p) => { p.hidden = !(raw.errors && raw.errors.length); });
      if (raw.errors && raw.errors.length) console.warn(raw.errors);
      compute(); render();
    },
    _fail(e) { console.error(e); document.querySelectorAll('#loaderr').forEach((p) => { p.hidden = false; }); if (status === 'loading') { status = 'error'; render(); } },
    _render: render,
  };
})();
function load() {
  google.script.run.withSuccessHandler((raw) => dash._set(raw)).withFailureHandler((e) => dash._fail(e)).getRaw(BOOT.key);
}
window.claude = {
  use: async (name) => {
    if (name !== 'db') throw new Error('unsupported');
    return {
      doc: (path) => ({
        set: (obj) => new Promise((resolve, reject) => {
          const id = String(path).split('/').pop();
          const r = ((window.HZ && window.HZ.rows()) || []).find((x) => x.key === id);
          google.script.run
            .withSuccessHandler(() => { resolve(); dash.refresh(); })
            .withFailureHandler(reject)
            .saveStatus(BOOT.key, id, Object.assign({name: r ? r['이름'] : ''}, obj));
        }),
      }),
    };
  },
};
</script>
'''

boot = '''
<script>
  dash._render();
  load();
</script>
'''

page = head + styles.replace('<style>', '<style>', 1) + '\n</head>\n<body>\n<div class="hz-page">' + markup + '</div>\n' + shim + scripts + boot + '</body>\n</html>\n'
open(out, 'w', encoding='utf-8').write(page)
print('wrote', out, len(page))
