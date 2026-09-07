# -*- coding: utf-8 -*-
"""
바로가기 아이콘(.ico) 만들기.

  python tools/make_icon.py

assets/logo.png(누끼 딴 로고)가 있으면 그걸로 만들고,
없으면 브랜드 색으로 간단한 마크를 그립니다.
"""

import os
import sys

OUT = os.path.join("assets", "obliv.ico")
SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

BG = "#241F19"        # 짙은 중성 배경 - 콘솔 화면과 같은 계열
FG = "#F5EBDC"        # 크림


def _rounded(size: int, radius_ratio: float = 0.22):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(size * radius_ratio)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)
    return img, d


def from_logo(path: str, size: int = 256):
    """누끼 로고를 크림색으로 칠해 배경 위에 얹는다."""
    from PIL import Image

    logo = Image.open(path).convert("RGBA")
    if logo.getchannel("A").getextrema() == (255, 255):
        return None  # 투명 배경이 아니면 아이콘으로 쓰기 어렵다

    img, _ = _rounded(size)
    box = int(size * 0.72)
    w = box
    h = max(1, round(logo.height * w / logo.width))
    if h > box:
        h = box
        w = max(1, round(logo.width * h / logo.height))
    logo = logo.resize((w, h), Image.LANCZOS)

    tinted = Image.new("RGBA", logo.size, FG)
    tinted.putalpha(logo.getchannel("A"))
    img.paste(tinted, ((size - w) // 2, (size - h) // 2), tinted)
    return img


def generated(size: int = 256):
    """로고가 없을 때 쓰는 마크 — 크림색 O와 밑줄."""
    from PIL import ImageFont

    img, d = _rounded(size)

    font_path = ""
    try:
        from publisher import thumbnail

        font_path = thumbnail._find_font(korean=False)
    except Exception:
        for c in (
            "/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            r"C:\Windows\Fonts\georgia.ttf",
        ):
            if os.path.exists(c):
                font_path = c
                break

    if font_path:
        font = ImageFont.truetype(font_path, int(size * 0.52))
        box = d.textbbox((0, 0), "O", font=font)
        d.text(
            ((size - (box[2] - box[0])) // 2 - box[0],
             int(size * 0.40) - (box[3] - box[1]) // 2 - box[1]),
            "O", font=font, fill=FG,
        )
    else:  # 폰트가 아예 없으면 도형으로
        pad = int(size * 0.28)
        d.ellipse([pad, pad, size - pad, int(size * 0.62)],
                  outline=FG, width=max(2, size // 22))

    # 콘솔의 세로 구분선을 눕힌 형태 — 브랜드 요소를 하나 이어 붙인다
    bar_w = int(size * 0.26)
    d.rectangle(
        [(size - bar_w) // 2, int(size * 0.72),
         (size + bar_w) // 2, int(size * 0.72) + max(2, size // 40)],
        fill=FG,
    )
    return img


def run() -> int:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Pillow가 필요합니다: pip install -r requirements.txt")
        return 1

    os.makedirs("assets", exist_ok=True)
    logo = os.path.join("assets", "logo.png")

    base = None
    if os.path.exists(logo):
        base = from_logo(logo)
        if base is None:
            print(f"{logo} 에 투명 영역이 없어 기본 마크로 만듭니다.")
    if base is None:
        base = generated()

    base.save(OUT, format="ICO", sizes=SIZES)
    print(f"아이콘을 만들었습니다: {os.path.abspath(OUT)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    sys.exit(run())
