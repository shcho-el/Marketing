# -*- coding: utf-8 -*-
"""
CMS 업로드 전 과정 점검 — 실제 브라우저로 목 CMS에 올려 본다.

  python test_cms_e2e.py

운영 CMS를 건드리지 않고 다음을 한 번에 확인합니다.
  1. 크롬 드라이버가 뜨는지
  2. 로그인이 되는지
  3. 폼 구조를 읽어 셀렉터를 잡는지 (inspect-cms)
  4. 연습 실행이 저장을 누르지 않는지
  5. 실제 저장 시 각 칸에 올바른 값이 들어가는지
  6. 썸네일이 규격대로 업로드되는지

여기까지 통과하면 남은 변수는 운영 CMS의 실제 셀렉터뿐이고,
그건 `python main.py inspect-cms`가 읽어 옵니다.
"""

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import closing

PORT = int(os.getenv("E2E_PORT", "5091"))
BASE = f"http://127.0.0.1:{PORT}"
WORK = os.path.abspath(os.getenv("E2E_DIR", ".e2e"))
SUBMISSIONS = "mock_cms_submissions.json"


def check(name, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {name}{(' — ' + detail) if detail else ''}")
    return 0 if ok else 1


def wait_port(port, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        with closing(socket.socket()) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


def env_for_run():
    env = dict(os.environ)
    env.update({
        "CMS_WRITE_URL": f"{BASE}/write",
        "CMS_LOGIN_URL": f"{BASE}/login",
        "CMS_USERNAME": "test",
        "CMS_PASSWORD": "test",
        "CMS_MAPPING_PATH": os.path.join(WORK, "mapping.json"),
        "CMS_DUMP_PATH": os.path.join(WORK, "dump.json"),
        "CMS_SHOT_DIR": os.path.join(WORK, "shots"),
        "CONTENT_DB_PATH": os.path.join(WORK, "content.db"),
        "THUMB_DIR": os.path.join(WORK, "thumbs"),
        "PYTHONIOENCODING": "utf-8",
    })
    return env


def run(args, env, timeout=240):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        env=env, capture_output=True, text=True, timeout=timeout,
    )


def seed_post(env):
    """검사를 통과한 원고 하나를 DB에 넣는다(생성 API 호출 없이)."""
    code = (
        "import sys; sys.path.insert(0,'.')\n"
        "from content import store, generator, medical_law, positioning, seo\n"
        "from test_content import FIXTURE\n"
        "doc = generator._normalize(dict(FIXTURE), FIXTURE['category'], FIXTURE['primary_keyword'])\n"
        "t = generator._full_text(doc)\n"
        "r = {'law': medical_law.review(t), 'positioning': positioning.review(t),\n"
        "     'seo': seo.audit(doc, doc['primary_keyword'])}\n"
        "assert r['law']['passed'] and r['positioning']['passed'], '픽스처가 검사를 통과하지 못함'\n"
        "print(store.save(doc, r, 'e2e'))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], env=env,
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr[-800:])
    return int(out.stdout.strip().splitlines()[-1])


def main():
    fails = 0
    os.makedirs(WORK, exist_ok=True)
    for f in (SUBMISSIONS, os.path.join(WORK, "content.db")):
        if os.path.exists(f):
            os.remove(f)

    env = env_for_run()
    mock_env = dict(env)
    mock_env["MOCK_CMS_PORT"] = str(PORT)

    print("\n[0] 목 CMS 기동")
    mock = subprocess.Popen(
        [sys.executable, "tools/mock_cms.py"], env=mock_env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_port(PORT):
            print("  ❌ 목 CMS가 뜨지 않았습니다.")
            return 1
        print(f"  ✅ {BASE}")

        print("\n[1] 폼 구조 분석 (실제 브라우저 로그인 포함)")
        r = run(["inspect-cms"], env)
        if r.returncode != 0:
            print("  ❌ inspect-cms 실패")
            print("     " + (r.stderr or r.stdout).strip().splitlines()[-1][:200])
            print("\n  크롬/드라이버 문제라면 .env에 경로를 지정하세요:")
            print("     CHROMEDRIVER_PATH=...   CHROME_BINARY=...")
            return 1
        mapping = json.load(open(env["CMS_MAPPING_PATH"], encoding="utf-8"))
        for field in ("category", "title", "post_url", "meta_title",
                      "meta_description", "hashtags", "thumbnail", "body"):
            fails += check(f"{field} 셀렉터", bool(mapping["fields"].get(field)),
                           mapping["fields"].get(field, ""))
        fails += check("노출/미노출 구분", len(mapping.get("expose", {})) == 2)
        fails += check("저장 버튼", bool(mapping.get("submit")), mapping.get("submit", ""))

        post_id = seed_post(env)

        print("\n[2] 연습 실행 — 저장하지 않아야 한다")
        r = run(["publish", str(post_id)], env)
        fails += check("정상 종료", r.returncode == 0)
        fails += check("저장되지 않음", not os.path.exists(SUBMISSIONS))
        fails += check("저장 전 캡처 생성",
                       any(f.endswith("before-save.png") for f in os.listdir(env["CMS_SHOT_DIR"])))

        print("\n[3] 실제 저장 (미노출)")
        r = run(["publish", str(post_id), "--save"], env)
        fails += check("정상 종료", r.returncode == 0)
        if not os.path.exists(SUBMISSIONS):
            print("  ❌ CMS가 아무것도 저장하지 않았습니다.")
            print("     " + (r.stdout or "").strip()[-400:])
            return 1

        rows = json.load(open(SUBMISSIONS, encoding="utf-8"))
        got = rows[-1]

        code = (
            "import sys,json; sys.path.insert(0,'.')\n"
            "from content import store, renderer\n"
            f"rec = store.get({post_id})\n"
            "print(json.dumps({'doc': rec['doc'],\n"
            "  'body': renderer.render_body(rec['doc'], include_schema=True)}, ensure_ascii=False))\n"
        )
        out = subprocess.run([sys.executable, "-c", code], env=env,
                             capture_output=True, text=True)
        want = json.loads(out.stdout.strip().splitlines()[-1])
        doc, body = want["doc"], want["body"]

        # 브라우저는 textarea 제출 시 줄바꿈을 CRLF로 정규화한다(HTML 표준).
        # 내용 비교에서는 이를 되돌린다.
        nl = lambda s: str(s).replace("\r\n", "\n")

        print("\n[4] CMS가 받은 값 대조")
        fails += check("노출여부 = 미노출", got["노출여부"] == "미노출", got["노출여부"])
        fails += check("카테고리", got["카테고리"] == doc["category"], got["카테고리"])
        fails += check("제목(H1)", got["제목"] == doc["h1"])
        fails += check("포스트URL", got["포스트URL"] == doc["post_url"])
        fails += check("MetaTitle", got["MetaTitle"] == doc["meta_title"],
                       f'{len(got["MetaTitle"])}자')
        fails += check("MetaDescription", got["MetaDescription"] == doc["meta_description"],
                       f'{len(got["MetaDescription"])}자')
        fails += check("해시태그 (줄바꿈 구분)",
                       nl(got["해시태그"]) == "\n".join(doc["hashtags"]),
                       f'{len(nl(got["해시태그"]).splitlines())}개')
        fails += check("본문 길이", got["본문길이"] == len(body) + body.count("\n"),
                       f'{got["본문길이"]}자 (CRLF 보정 포함)')
        fails += check("썸네일 업로드", got["썸네일"]["bytes"] > 10_000,
                       f'{got["썸네일"]["bytes"] // 1024}KB')
        fails += check("썸네일 300KB 이하", got["썸네일"]["bytes"] <= 300 * 1024)
        fails += check("저장 후 캡처 생성",
                       any(f.endswith("after-save.png") for f in os.listdir(env["CMS_SHOT_DIR"])))
        fails += check("한 번만 저장됨", len(rows) == 1, f"{len(rows)}건")

    finally:
        mock.terminate()
        try:
            mock.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mock.kill()

    print("\n" + "=" * 46)
    if fails:
        print(f"실패 {fails}건")
    else:
        print("전체 통과 — 업로드 경로가 실제 브라우저에서 동작합니다.")
        print("남은 변수는 운영 CMS의 실제 셀렉터뿐입니다.")
        print("  python main.py inspect-cms   # 운영 CMS 설정으로 실행")
    print("=" * 46)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
