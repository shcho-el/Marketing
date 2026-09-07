# -*- coding: utf-8 -*-
"""
목(mock) CMS - 자동 업로드를 안전하게 연습하기 위한 가짜 관리자 페이지.

운영 CMS(blog.obliv.kr)에 붙이기 전에 여기서 먼저 돌려 보세요.
로그인 → 폼 분석 → 업로드 전 과정이 실제와 같은 순서로 동작하는지 확인할 수 있습니다.

  python tools/mock_cms.py                       # http://localhost:5002

  # 다른 터미널에서
  CMS_WRITE_URL=http://localhost:5002/write \
  CMS_LOGIN_URL=http://localhost:5002/login \
  CMS_USERNAME=test CMS_PASSWORD=test \
  CMS_MAPPING_PATH=mock_mapping.json \
  python main.py inspect-cms

폼 구조와 라벨은 실제 관리자 화면을 그대로 옮겼습니다.
"""

import json
import os

from flask import Flask, redirect, request, session, url_for

app = Flask(__name__)
app.secret_key = "mock-cms-only-for-local-testing"

USERNAME = os.getenv("MOCK_CMS_USER", "test")
PASSWORD = os.getenv("MOCK_CMS_PASS", "test")
SUBMISSIONS = "mock_cms_submissions.json"

CATEGORIES = ["발톱무좀치료", "내성발톱치료", "문제성발톱", "발톱관리"]


LOGIN_HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>관리자 로그인</title></head><body style="font-family:sans-serif;padding:60px">
<h2>블로그 관리자</h2>
{msg}
<form method="post">
  <p><input type="text" name="mb_id" placeholder="아이디"></p>
  <p><input type="password" name="mb_password" placeholder="비밀번호"></p>
  <p><button type="submit">로그인</button></p>
</form></body></html>"""


WRITE_HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>블로그 글쓰기</title></head>
<body style="font-family:sans-serif;padding:30px;max-width:1100px">
<h2>기본 정보</h2>
<form method="post" enctype="multipart/form-data" action="/write">
<table border="1" cellpadding="10" style="border-collapse:collapse;width:100%">
  <tr>
    <th align="left" width="180">노출 여부</th>
    <td>
      <label><input type="radio" name="wr_show" value="1"> 노출</label>
      <label><input type="radio" name="wr_show" value="0" checked> 미노출</label>
      <p style="color:#c00;font-size:12px">
        *모든 글 작성이 완료된 이후에 최종완료 사항으로 노출을 선택해주세요.</p>
    </td>
  </tr>
  <tr>
    <th align="left">카테고리</th>
    <td><select name="ca_name" id="ca_name">{options}</select></td>
  </tr>
  <tr>
    <th align="left">제목( H1 )</th>
    <td><input type="text" name="wr_subject" id="wr_subject" style="width:100%"></td>
  </tr>
  <tr>
    <th align="left">포스트URL</th>
    <td><input type="text" name="wr_link1" id="wr_link1" style="width:100%">
      <p style="color:#00c;font-size:12px">
        *포스트 URL은 키워드 위주로 작성해 주시고 한번 작성한 포스트 URL은
        수정하지 말아주세요. | 키워드 단어 단위로 '-'로 연결</p></td>
  </tr>
  <tr>
    <th align="left">MetaTitle</th>
    <td><input type="text" name="wr_meta_title" id="wr_meta_title" style="width:100%">
      <p style="font-size:12px">(0 / 최대 40자)</p></td>
  </tr>
  <tr>
    <th align="left">MetaDescription</th>
    <td><input type="text" name="wr_meta_desc" id="wr_meta_desc" style="width:100%">
      <p style="font-size:12px">(0 / 최대 80자)</p></td>
  </tr>
  <tr>
    <th align="left">해시태그</th>
    <td><textarea name="wr_tag" id="wr_tag" rows="6" style="width:100%"></textarea>
      <p style="color:#c00;font-size:12px">
        *해시태그 하나를 작성하고 엔터를 쳐서 줄바꾸기를 해주세요.</p></td>
  </tr>
  <tr>
    <th align="left">썸네일 등록</th>
    <td><input type="file" name="bf_file" id="bf_file">
      <p style="color:#c00;font-size:12px">
        *썸네일 이미지 규격 사이즈 = 880(가로) x 580(세로)<br>
        *썸네일 이미지 첨부용량 제한은 300kb입니다.<br>
        *썸네일 이미지를 등록하셔야 글이 저장됩니다.</p></td>
  </tr>
</table>

<h2>본문</h2>
<textarea name="wr_content" id="wr_content" rows="18" style="width:100%"></textarea>

<p style="margin-top:20px">
  <button type="submit" id="btn_submit">저장</button>
  <button type="button">취소</button>
</p>
</form>
</body></html>"""


RESULT_HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>저장 완료</title></head><body style="font-family:sans-serif;padding:40px">
<h2>저장되었습니다</h2>
<p>{summary}</p>
<pre style="background:#f4f4f4;padding:16px;white-space:pre-wrap">{dump}</pre>
<a href="/write">새 글 쓰기</a>
</body></html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form.get("mb_id") == USERNAME
            and request.form.get("mb_password") == PASSWORD
        ):
            session["ok"] = True
            return redirect(url_for("write"))
        return LOGIN_HTML.format(msg='<p style="color:red">로그인 실패</p>'), 401
    return LOGIN_HTML.format(msg="")


@app.route("/write", methods=["GET", "POST"])
def write():
    if not session.get("ok"):
        return redirect(url_for("login"))

    if request.method == "GET":
        options = "".join(f'<option value="{c}">{c}</option>' for c in CATEGORIES)
        return WRITE_HTML.format(options=options)

    # ── 저장 처리 ──
    thumb = request.files.get("bf_file")
    if not thumb or not thumb.filename:
        return "<script>alert('썸네일 이미지를 등록하셔야 글이 저장됩니다.');history.back();</script>"

    blob = thumb.read()
    record = {
        "노출여부": "노출" if request.form.get("wr_show") == "1" else "미노출",
        "카테고리": request.form.get("ca_name", ""),
        "제목": request.form.get("wr_subject", ""),
        "포스트URL": request.form.get("wr_link1", ""),
        "MetaTitle": request.form.get("wr_meta_title", ""),
        "MetaDescription": request.form.get("wr_meta_desc", ""),
        "해시태그": request.form.get("wr_tag", ""),
        "썸네일": {"filename": thumb.filename, "bytes": len(blob)},
        "본문길이": len(request.form.get("wr_content", "")),
        "본문앞부분": request.form.get("wr_content", "")[:200],
    }

    existing = []
    if os.path.exists(SUBMISSIONS):
        with open(SUBMISSIONS, encoding="utf-8") as fp:
            existing = json.load(fp)
    existing.append(record)
    with open(SUBMISSIONS, "w", encoding="utf-8") as fp:
        json.dump(existing, fp, ensure_ascii=False, indent=2)

    summary = (
        f"{record['노출여부']} · [{record['카테고리']}] {record['제목']} "
        f"· 썸네일 {record['썸네일']['bytes'] // 1024}KB "
        f"· 본문 {record['본문길이']}자"
    )
    return RESULT_HTML.format(
        summary=summary, dump=json.dumps(record, ensure_ascii=False, indent=2)
    )


@app.route("/")
def home():
    return redirect(url_for("write"))


if __name__ == "__main__":
    print(f"목 CMS 실행 - 아이디 {USERNAME} / 비밀번호 {PASSWORD}")
    print("  로그인: http://localhost:5002/login")
    print("  글쓰기: http://localhost:5002/write")
    print(f"  저장 결과는 {SUBMISSIONS}에 쌓입니다.")
    app.run(host="127.0.0.1", port=int(os.getenv("MOCK_CMS_PORT", "5002")), debug=False)
