"""Build apps-script/Index.html from the artifact page (../index.html).

The artifact version saves votes through claude.ai; this public version saves
them to a Google Sheet through Code.gs, so anyone with the link can vote.
Run: python3 apps-script/build.py
"""
import base64
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
s = (ROOT / "index.html").read_text()


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (old[:60], n)
    s = s.replace(old, new)


# Fonts: Pretendard from jsDelivr instead of bundled files
s, n = re.subn(r'@font-face \{ font-family: "Pretendard";[^\n]*\n', "", s)
assert n == 3, n

# Images: inline as data URIs (Apps Script serves a single HTML file)
# each image is embedded once (160px WebP) and assigned to its <img> tags by script
from io import BytesIO
from PIL import Image
imgs = {}
for name in ["chicken", "galbi", "sashimi", "beer"]:
    im = Image.open(ROOT / "img" / f"{name}.png").convert("RGBA")
    im.thumbnail((160, 160), Image.LANCZOS)
    buf = BytesIO(); im.save(buf, "WEBP", quality=82, method=6)
    imgs[name] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    s = s.replace(f'src="img/{name}.png"', f'data-img="{name}"')
assert 'src="img/' not in s
img_js = ("const IMGS = " + json.dumps(imgs) + ";\n"
          "document.querySelectorAll(\"[data-img]\").forEach(i => { i.src = IMGS[i.dataset.img]; });\n")

# Name field (identifies a voter without a login)
rep('''  <section class="q" id="q1"''', '''  <section class="q" id="who" style="--c:var(--ink)">
    <div class="q-head">
      <span class="tag">이름 <em class="req">필수</em></span>
      <label for="name"><h2>누구신가요?</h2></label>
      <p>같은 이름으로 다시 제출하면 기존 투표가 수정됩니다.</p>
    </div>
    <input id="name" type="text" maxlength="20" autocomplete="name" placeholder="예: 홍길동">
  </section>

  <section class="q" id="q1"''')
rep('</style>', '''#name { width: 100%; font: inherit; font-size: 16px; color: var(--ink); background: var(--surface); border: 1.5px solid var(--line); border-radius: 10px; padding: 12px 14px; }
#name:focus-visible { outline: 3px solid color-mix(in srgb, var(--ink) 25%, transparent); outline-offset: 2px; }
.q.missing #name { border-color: var(--ember); }
.chip { width: 26px; height: 26px; border-radius: 50%; display: inline-grid; place-items: center; font-size: 11.5px; font-weight: 700; color: #fff; border: 2px solid var(--surface); }
.faces .chip { width: 22px; height: 22px; font-size: 10px; margin-left: -6px; }
.faces .chip:first-child { margin-left: 0; }
.note .chip { flex: none; }
</style>''')

# --- script changes ---
rep('const state = { draft: { q1: null, q2: null }, votes: new Map(), uid: null, db: null, user: null, canWrite: true, loadedMine: false, saving: false };',
    'const state = { draft: { q1: null, q2: null }, votes: new Map(), online: false, canWrite: true, saving: false, prefilledFor: null };\n'
    'const myName = () => $("name").value.trim().slice(0, 20);\n'
    'const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };')
rep('function mineSaved() { return state.uid ? state.votes.get(state.uid) : null; }',
    'function mineSaved() { const n = myName(); return n ? state.votes.get(n) : null; }')
rep('''  QS.forEach(q => $(q).classList.toggle("missing", !state.draft[q] && state.canWrite && !isClosed()));''',
    '''  QS.forEach(q => $(q).classList.toggle("missing", !state.draft[q] && state.canWrite && !isClosed()));
  $("who").classList.toggle("missing", !myName() && !isClosed());''')
rep('''  if (!state.db) { btn.disabled = true; st.textContent = "투표는 claude.ai에서 열었을 때 저장됩니다."; return; }
  if (!state.canWrite) { btn.disabled = true; st.textContent = "보기 전용 권한이라 투표할 수 없어요. 결과만 볼 수 있습니다."; return; }''',
    '''  if (!state.online) { btn.disabled = true; st.textContent = "투표 현황을 불러오는 중…"; return; }''')
rep('''  btn.disabled = !ready || !draftDiffers();
  if (!ready)''', '''  btn.disabled = !ready || !myName() || !draftDiffers();
  if (!myName()) st.textContent = "필수: 이름을 입력해야 제출할 수 있어요.";
  else if (!ready)''')
rep('async function renderResults() {', 'function renderResults() {')
rep('''  const ids = votes.map(([u]) => u);
  const profiles = state.user && ids.length ? await state.user.profiles(ids) : {};
  const face = uid => { const p = profiles[uid]; const img = el("img"); img.alt = (p && p.name) || "참여자"; img.title = img.alt; if (p) img.src = p.avatarUrl; return img; };''',
    '''  const ids = votes.map(([u]) => u);
  const face = name => { const c = el("span", "chip", [...name][0] || "?"); c.title = name; c.style.background = hue(name); return c; };''')
rep('''el("div", "who", (profiles[u] && profiles[u].name) || "참여자")''', 'el("div", "who", u)')

# Replace the claude.ai save/load code with Google Apps Script calls
head, sep, _ = s.partition('$("note").addEventListener("input", updateStatus);')
assert sep
s = head + img_js + r'''function hue(name) { let h = 0; for (const ch of name) h = (h * 31 + ch.codePointAt(0)) % 360; return `hsl(${h} 45% 45%)`; }

function setVotes(list) {
  state.votes = new Map(list.map(v => [v.name, v]));
  state.online = true;
  notice("");
  prefill();
  updateStatus();
  renderResults();
}

function prefill() {
  const n = myName(), mine = mineSaved();
  if (!mine || state.prefilledFor === n) return;
  state.prefilledFor = n;
  QS.forEach(q => { state.draft[q] = byId[mine[q]] ? mine[q] : null; });
  $("note").value = mine.note || "";
  updateSelection();
}

function load() {
  google.script.run
    .withSuccessHandler(setVotes)
    .withFailureHandler(() => { if (!state.online) notice("투표 현황을 불러오지 못했어요. 페이지를 새로 고쳐 주세요."); })
    .getVotes();
}

$("note").addEventListener("input", updateStatus);
$("name").value = store.get("dinner-vote-name") || "";
$("name").addEventListener("input", () => { state.prefilledFor = null; prefill(); updateStatus(); });
$("submit").addEventListener("click", () => {
  const name = myName();
  if (isClosed() || !name || !QS.every(q => state.draft[q])) return;
  state.saving = true; updateStatus();
  google.script.run
    .withSuccessHandler(list => {
      state.saving = false;
      store.set("dinner-vote-name", name);
      state.prefilledFor = name;
      setVotes(list);
      $("status").textContent = "투표가 저장됐어요. 감사합니다!";
    })
    .withFailureHandler(err => {
      state.saving = false; updateStatus();
      const m = String(err && err.message || "");
      $("status").textContent = m.includes("closed") ? "투표가 마감되어 저장하지 못했어요." : "저장하지 못했어요. 잠시 후 다시 눌러 주세요.";
    })
    .submitVote({ name, q1: state.draft.q1, q2: state.draft.q2, note: $("note").value.trim().slice(0, 300) });
});

function checkDeadline() {
  const d = $("deadline");
  if (isClosed()) { d.textContent = "투표 마감됨 · 10월 2일(금) 17:00"; d.classList.add("closed"); updateSelection(); updateStatus(); return; }
  const left = DEADLINE - Date.now();
  const h = Math.floor(left / 3600000), m = Math.floor(left % 3600000 / 60000);
  d.textContent = `10월 2일(금) 17:00 마감 · ${h ? h + "시간 " : ""}${m}분 남음`;
  setTimeout(checkDeadline, Math.min(left + 1000, 60000));
}

buildOptions();
checkDeadline();
updateSelection();
updateStatus();
renderResults();
load();
setInterval(load, 15000);
</script>
'''

title = re.search(r"<title>(.*?)</title>", s).group(1)
s = s.replace(f"<title>{title}</title>\n", "", 1)
s = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
     '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
     f'<title>{title}</title>\n<base target="_blank">\n'
     '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.min.css">\n'
     '<style>[hidden]{display:none!important} body{margin:0} img{max-width:100%}</style>\n'
     '</head>\n<body>\n' + s + '</body>\n</html>\n')

(HERE / "Index.html").write_text(s)
print("wrote", HERE / "Index.html", len(s) // 1024, "KB")
