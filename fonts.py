# -*- coding: utf-8 -*-
"""
프리텐다드 폰트 내려받기.

  python main.py fonts

브라우저는 CDN에서 폰트를 받지만, 썸네일은 서버가 직접 그리므로
폰트 파일이 로컬에 있어야 합니다. assets/fonts/ 에 받아 둡니다.
"""

import os
import sys
import urllib.request

BASE = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/public/static"
WEIGHTS = ["Regular", "Medium", "SemiBold", "Bold"]
DEST = os.path.join("assets", "fonts")


def run() -> int:
    os.makedirs(DEST, exist_ok=True)
    print(f"\n프리텐다드를 {os.path.abspath(DEST)} 에 내려받습니다.\n")

    ok = 0
    for w in WEIGHTS:
        name = f"Pretendard-{w}.otf"
        path = os.path.join(DEST, name)
        if os.path.exists(path) and os.path.getsize(path) > 100_000:
            print(f"  · {name} — 이미 있음")
            ok += 1
            continue
        try:
            urllib.request.urlretrieve(f"{BASE}/{name}", path)
            print(f"  ✅ {name} ({os.path.getsize(path) // 1024}KB)")
            ok += 1
        except Exception as exc:
            print(f"  ❌ {name} — {exc}")

    if not ok:
        print(
            "\n내려받지 못했습니다. 인터넷 연결을 확인하거나,\n"
            "https://github.com/orioncactus/pretendard 에서 직접 받아\n"
            f"{os.path.abspath(DEST)} 에 넣으세요.\n"
            "설치 없이도 동작합니다(다른 한글 폰트로 대체)."
        )
        return 1

    try:
        from publisher import thumbnail

        print(f"\n썸네일 폰트: {thumbnail._find_font(True)}")
    except Exception:
        pass
    print("\n완료했습니다.\n")
    return 0


if __name__ == "__main__":
    sys.exit(run())
