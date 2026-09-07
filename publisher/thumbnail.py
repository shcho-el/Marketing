# -*- coding: utf-8 -*-
"""
썸네일 자동 생성.

CMS 요구사항 (관리자 화면 안내문):
  - 규격 880(가로) x 580(세로)
  - 용량 300KB 이하
  - 이미지 내 텍스트는 정중앙 배치
  - 썸네일을 등록해야 글이 저장됨 (필수)

따라서 자동 업로드에는 썸네일 생성이 반드시 포함되어야 합니다.
"""

import glob
import logging
import os
import platform
import textwrap

logger = logging.getLogger(__name__)

WIDTH = 880
HEIGHT = 580
MAX_BYTES = 300 * 1024

# 배경/글자 색 (원내 톤에 맞춰 .env로 바꿀 수 있음)
BG_COLOR = os.getenv("THUMB_BG", "#0f2540")
FG_COLOR = os.getenv("THUMB_FG", "#ffffff")
ACCENT_COLOR = os.getenv("THUMB_ACCENT", "#5b9bd5")

# 한글 폰트 탐색 우선순위. .env의 THUMB_FONT가 있으면 그것을 먼저 쓴다.
_FONT_CANDIDATES = {
    "Windows": [
        r"C:\Windows\Fonts\malgunbd.ttf",
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\NanumGothicBold.ttf",
        r"C:\Windows\Fonts\gulim.ttc",
    ],
    "Darwin": [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
    ],
    "Linux": [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/unifont/unifont.otf",
    ],
}


class ThumbnailError(RuntimeError):
    pass


def find_font() -> str:
    """한글이 그려지는 폰트 파일 경로를 찾는다."""
    override = os.getenv("THUMB_FONT", "")
    if override:
        if os.path.exists(override):
            return override
        raise ThumbnailError(f"THUMB_FONT 경로에 파일이 없습니다: {override}")

    for path in _FONT_CANDIDATES.get(platform.system(), []):
        if os.path.exists(path):
            return path

    # 마지막 수단: 시스템에서 CJK 폰트를 훑는다.
    for pattern in (
        "/usr/share/fonts/**/*NanumGothic*.ttf",
        "/usr/share/fonts/**/*NotoSansCJK*.*",
        "/usr/share/fonts/**/*.ttc",
    ):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return hits[0]

    raise ThumbnailError(
        "한글 폰트를 찾지 못했습니다. .env에 THUMB_FONT=<폰트파일 경로>를 지정하세요. "
        "(윈도우 예: C:\\Windows\\Fonts\\malgunbd.ttf)"
    )


def _fit_font(ImageFont, font_path: str, lines: list, max_width: int, start_size: int):
    """모든 줄이 max_width에 들어가는 가장 큰 폰트 크기를 찾는다."""
    from PIL import Image, ImageDraw

    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    size = start_size
    while size > 20:
        font = ImageFont.truetype(font_path, size)
        widest = max(
            probe.textbbox((0, 0), line, font=font)[2] for line in lines
        )
        if widest <= max_width:
            return font
        size -= 4
    return ImageFont.truetype(font_path, 20)


def _wrap(text: str, per_line: int) -> list:
    """정중앙 배치를 고려해 2줄 이내로 줄바꿈한다."""
    text = (text or "").strip()
    if not text:
        return [""]
    lines = textwrap.wrap(text, width=per_line) or [text]
    if len(lines) > 2:
        # 3줄 이상이면 두 줄로 압축하고 나머지는 버린다(정중앙 균형 유지).
        lines = [lines[0], " ".join(lines[1:])]
        if len(lines[1]) > per_line + 4:
            lines[1] = lines[1][: per_line + 2].rstrip() + "…"
    return lines


def generate(
    headline: str,
    subline: str = "",
    out_path: str = "",
) -> str:
    """썸네일 이미지를 만들고 저장 경로를 돌려준다.

    headline: 정중앙에 크게 들어갈 문구 (doc의 thumbnail_copy)
    subline : 아래 작게 들어갈 문구 (보통 병원명)
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise ThumbnailError(
            "Pillow가 없습니다. pip install -r requirements.txt 를 실행하세요."
        ) from exc

    font_path = find_font()
    out_path = out_path or os.path.join(
        os.getenv("THUMB_DIR", "thumbnails"), "thumb.jpg"
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 상하 여백 안쪽에 얇은 강조선 - 밋밋함을 덜기 위한 최소 장식
    draw.rectangle([0, 0, WIDTH, 8], fill=ACCENT_COLOR)
    draw.rectangle([0, HEIGHT - 8, WIDTH, HEIGHT], fill=ACCENT_COLOR)

    inner_width = WIDTH - 140
    lines = _wrap(headline, per_line=11)
    font = _fit_font(ImageFont, font_path, lines, inner_width, start_size=96)

    # 정중앙 배치: 전체 텍스트 블록 높이를 구해 중앙에 맞춘다.
    line_h = font.size + 18
    sub_font = ImageFont.truetype(font_path, max(24, font.size // 3))
    sub_h = (sub_font.size + 16) if subline else 0
    block_h = line_h * len(lines) + sub_h
    y = (HEIGHT - block_h) // 2

    for line in lines:
        w = draw.textbbox((0, 0), line, font=font)[2]
        draw.text(((WIDTH - w) // 2, y), line, font=font, fill=FG_COLOR)
        y += line_h

    if subline:
        w = draw.textbbox((0, 0), subline, font=sub_font)[2]
        draw.text(
            ((WIDTH - w) // 2, y + 8), subline, font=sub_font, fill=ACCENT_COLOR
        )

    # 300KB 이하가 될 때까지 품질을 낮춘다.
    for quality in (92, 85, 78, 70, 62, 55, 45):
        img.save(out_path, "JPEG", quality=quality, optimize=True)
        if os.path.getsize(out_path) <= MAX_BYTES:
            logger.info(
                "썸네일 생성: %s (%.0fKB, quality=%d)",
                out_path,
                os.path.getsize(out_path) / 1024,
                quality,
            )
            return out_path

    raise ThumbnailError(
        f"썸네일을 {MAX_BYTES // 1024}KB 이하로 줄이지 못했습니다: {out_path}"
    )


def generate_for(doc: dict, out_dir: str = "") -> str:
    """생성된 글에 맞는 썸네일을 만든다."""
    from content import clinic

    out_dir = out_dir or os.getenv("THUMB_DIR", "thumbnails")
    slug = (doc.get("post_url") or "post")[:40]
    headline = doc.get("thumbnail_copy") or doc.get("primary_keyword") or "문제성발톱"
    return generate(
        headline=headline,
        subline=clinic.SHORT_NAME,
        out_path=os.path.join(out_dir, f"{slug}.jpg"),
    )
