"""src/Index.src.html → Index.html 생성.

구글 HtmlService가 화면을 만들 때 <script> 안의 일부 글자를 바꿔 문법 오류가 나는 문제가 있어,
앱 스크립트를 base64로 감싸 넣습니다 (영문·숫자만 남으므로 변형될 여지가 없음).
수정은 src/Index.src.html 에서 하고, `python3 build.py` 로 Index.html 을 다시 만드세요.
"""
import base64, pathlib, re

root = pathlib.Path(__file__).parent
src = (root / 'src' / 'Index.src.html').read_text(encoding='utf-8')

scripts = list(re.finditer(r'<script>\n(.*?)</script>', src, re.S))
main = next(m for m in scripts if 'const BOOT = window.BOOT' in m.group(1))
app_b64 = base64.b64encode(main.group(1).encode('utf-8')).decode('ascii')

loader = """<script>
(function () {
  function dec(b) {
    var bin = atob(b), u = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(u);
  }
  try {
    var boot = '__BOOT_B64__';
    window.BOOT = /^[A-Za-z0-9+\\/=]+$/.test(boot) && boot.length > 20 ? JSON.parse(dec(boot)) : null;
    var s = document.createElement('script');
    s.text = dec('""" + app_b64 + """');
    document.body.appendChild(s);
  } catch (e) {
    var el = document.getElementById('loading');
    if (el) el.textContent = '화면 오류: ' + (e && e.message || e);
  }
})();
</script>"""

out = src[:main.start()] + loader + src[main.end():]
(root / 'Index.html').write_text(out, encoding='utf-8')
print('Index.html', len(out), 'bytes')
