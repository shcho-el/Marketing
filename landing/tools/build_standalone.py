#!/usr/bin/env python3
"""
index.html + assets 를 하나의 HTML 파일로 합칩니다.

이미지를 data URI 로 인라인하기 때문에 결과 파일 하나만 있으면
어디서든(메일 첨부, 로컬 더블클릭, 임시 공유) 그대로 열립니다.
운영 배포에는 원본 index.html + assets/ 구성을 쓰세요 — 캐싱이 훨씬 낫습니다.

사용:
    python landing/tools/build_standalone.py [출력파일]
기본 출력: landing/index.standalone.html
"""
import base64
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".svg": "image/svg+xml"}
# og:image 는 외부 스크래퍼가 읽어야 해서 인라인 대상에서 제외
SKIP = {"og.jpg"}
# 인라인할 때만 줄여서 넣을 파일 (탭 아이콘에 512px 원본은 과함)
SHRINK = {"favicon.png": 64}


def read_bytes(f: Path) -> bytes:
    px = SHRINK.get(f.name)
    if not px:
        return f.read_bytes()
    from PIL import Image
    im = Image.open(f).resize((px, px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def build(dst: Path) -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    inlined = []

    def repl(m):
        rel = m.group(1)
        name = Path(rel).name
        if name in SKIP:
            return m.group(0)
        f = ROOT / "assets" / name
        if not f.exists():
            print(f"  ! 없음: {rel}")
            return m.group(0)
        mime = MIME.get(f.suffix.lower())
        if not mime:
            return m.group(0)
        b64 = base64.b64encode(read_bytes(f)).decode()
        inlined.append((name, len(b64)))
        return f'"data:{mime};base64,{b64}"'

    html = re.sub(r'"(\./assets/[^"]+)"', repl, html)
    dst.write_text(html, encoding="utf-8")

    for name, size in inlined:
        print(f"  + {name:20} {size // 1024:>5} KB (base64)")
    print(f"\n완료 → {dst}  ({dst.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "index.standalone.html"
    build(out)
