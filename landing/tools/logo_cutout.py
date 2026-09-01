#!/usr/bin/env python3
"""
Obliv Clinic 로고 누끼 스크립트.

흰색(밝은) 배경을 알파로 빼고, 여백을 잘라내고,
헤더용(검정) / 다크배경용(흰색) 두 벌을 만들어 landing/assets 에 저장합니다.

사용:
    pip install pillow
    python landing/tools/logo_cutout.py <원본로고파일>

결과:
    landing/assets/logo.png        투명 배경 (검정 워드마크)
    landing/assets/logo-white.png  투명 배경 (흰색 워드마크, 어두운 배경용)
    landing/assets/favicon.png     512px 정사각 파비콘
"""
import sys
from pathlib import Path

from PIL import Image

# 이 값보다 밝은 픽셀은 배경으로 간주. 로고 가장자리가 지저분하면 240~250 사이로 조정.
WHITE_CUTOFF = 246
# 이 값보다 어두운 픽셀은 완전 불투명 유지.
INK_CUTOFF = 90


def cutout(src: Path, out_dir: Path) -> None:
    img = Image.open(src).convert("RGBA")
    px = img.load()
    w, h = img.size

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            if lum >= WHITE_CUTOFF:
                alpha = 0
            elif lum <= INK_CUTOFF:
                alpha = 255
            else:
                # 안티에일리어싱 구간은 밝기에 비례해 부드럽게 처리
                alpha = int(255 * (WHITE_CUTOFF - lum) / (WHITE_CUTOFF - INK_CUTOFF))
            px[x, y] = (0, 0, 0, min(alpha, a))

    img = img.crop(img.getbbox())  # 여백 트림
    out_dir.mkdir(parents=True, exist_ok=True)

    img.save(out_dir / "logo.png")
    print(f"  ✓ logo.png        {img.size[0]}×{img.size[1]}")

    white = img.copy()
    wp = white.load()
    for y in range(white.size[1]):
        for x in range(white.size[0]):
            wp[x, y] = (255, 255, 255, wp[x, y][3])
    white.save(out_dir / "logo-white.png")
    print("  ✓ logo-white.png")

    side = max(img.size)
    fav = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    fav.paste(img, ((side - img.size[0]) // 2, (side - img.size[1]) // 2))
    fav.resize((512, 512), Image.LANCZOS).save(out_dir / "favicon.png")
    print("  ✓ favicon.png     512×512")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python landing/tools/logo_cutout.py <원본로고파일>")
    source = Path(sys.argv[1])
    if not source.exists():
        sys.exit(f"파일을 찾을 수 없습니다: {source}")
    target = Path(__file__).resolve().parent.parent / "assets"
    print(f"누끼 처리: {source}")
    cutout(source, target)
    print(f"완료 → {target}")
