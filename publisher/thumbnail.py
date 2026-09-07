# -*- coding: utf-8 -*-
"""
썸네일 생성 - 사진 배경 위에 제목을 올리는 방식.

CMS 요구사항 (관리자 화면 안내문)
  880(가로) x 580(세로) · 300KB 이하 · 텍스트는 정중앙 배치 · 등록해야 글이 저장됨

디자인 (기존 발행 썸네일을 그대로 따름)
  center 레이아웃 - 제목을 화면 중앙에 크게, 아래에 세로 구분선, 그 아래 브랜드
  bottom 레이아웃 - 브랜드를 위에, 세로 구분선, 제목을 아래쪽에 크게

사진 위에 글자를 얹으면 배경 밝기에 따라 글씨가 묻힙니다.
그래서 글자가 놓일 영역의 밝기를 실제로 재서 어두움막(scrim) 세기를 자동으로 정합니다.
"""

import glob
import hashlib
import logging
import os
import platform
import re
import textwrap

logger = logging.getLogger(__name__)

WIDTH = 880
HEIGHT = 580
MAX_BYTES = 300 * 1024

# 배경 사진을 넣어 두는 곳. 카테고리별 하위 폴더를 만들면 자동으로 골라 씁니다.
#   assets/thumbnails/발톱무좀치료/*.jpg
#   assets/thumbnails/*.jpg          ← 공용
PHOTO_DIR = os.getenv("THUMB_PHOTO_DIR", "assets/thumbnails")
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# 색상 - 예시 썸네일의 크림색 계열
TEXT_COLOR = os.getenv("THUMB_TEXT_COLOR", "#F5EBDC")
BRAND_TEXT = os.getenv("THUMB_BRAND", "Obliv Clinic")

# 브랜드 로고 이미지(누끼 딴 투명 PNG). 지정하면 브랜드 텍스트 대신 로고를 얹습니다.
LOGO_PATH = os.getenv("THUMB_LOGO", "assets/logo.png")
LOGO_WIDTH = int(os.getenv("THUMB_LOGO_WIDTH", "200"))
# 원본 로고는 보통 진한 글자입니다. 어두운 배경 위에 올리려면 크림색으로 바꿔야 읽힙니다.
LOGO_TINT = os.getenv("THUMB_LOGO_TINT", "1") not in ("0", "false", "False")

# 사진이 없을 때 쓰는 단색 배경
FALLBACK_BG = os.getenv("THUMB_BG", "#2b2622")

LAYOUT_CENTER = "center"   # 제목 중앙 → 구분선 → 브랜드
LAYOUT_BOTTOM = "bottom"   # 브랜드 상단 → 구분선 → 제목 하단
LAYOUT_AUTO = "auto"       # 글마다 번갈아 - 목록이 단조로워지지 않게
LAYOUTS = [LAYOUT_CENTER, LAYOUT_BOTTOM]
DEFAULT_LAYOUT = os.getenv("THUMB_LAYOUT", LAYOUT_AUTO)

# 크림색 글자가 읽히려면 배경이 이 밝기(0~255)보다 어두워야 한다.
TARGET_BACKDROP_LUMA = int(os.getenv("THUMB_TARGET_LUMA", "95"))

_HANGUL = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")


class ThumbnailError(RuntimeError):
    pass


# ── 폰트 ─────────────────────────────────────────────────────────────
# 명조/세리프 계열을 우선한다. 예시 썸네일이 세리프체다.
_KO_SERIF = {
    "Windows": [
        r"C:\Windows\Fonts\NanumMyeongjo.ttf",
        r"C:\Windows\Fonts\batang.ttc",
        r"C:\Windows\Fonts\BATANG.TTC",
    ],
    "Darwin": [
        "/Library/Fonts/NanumMyeongjo.ttf",
        "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf",
    ],
    "Linux": [
        "/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf",
        "/usr/share/fonts/truetype/nanum/NanumMyeongjoBold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ],
}

_LATIN_SERIF = {
    "Windows": [
        r"C:\Windows\Fonts\georgia.ttf",
        r"C:\Windows\Fonts\times.ttf",
        r"C:\Windows\Fonts\constan.ttf",
    ],
    "Darwin": [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    ],
    "Linux": [
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    ],
}

# 한글 세리프가 아예 없을 때 최후의 보루 (고딕이라도 글자는 나와야 한다)
_KO_FALLBACK = [
    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    r"C:\Windows\Fonts\malgun.ttf",
]


def _first_existing(paths) -> str:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return ""


def _find_font(korean: bool) -> str:
    """스크립트에 맞는 폰트 파일 경로를 찾는다."""
    override = os.getenv("THUMB_FONT_KO" if korean else "THUMB_FONT_EN", "") or os.getenv(
        "THUMB_FONT", ""
    )
    if override:
        if os.path.exists(override):
            return override
        raise ThumbnailError(f"지정한 폰트 파일이 없습니다: {override}")

    system = platform.system()
    table = _KO_SERIF if korean else _LATIN_SERIF
    found = _first_existing(table.get(system, []) + table.get("Linux", []))
    if found:
        return found

    if korean:
        found = _first_existing(_KO_FALLBACK)
        if found:
            logger.warning("한글 명조체를 찾지 못해 대체 폰트를 씁니다: %s", found)
            return found
        for pattern in ("/usr/share/fonts/**/*Nanum*.ttf", "/usr/share/fonts/**/*CJK*.*"):
            hits = glob.glob(pattern, recursive=True)
            if hits:
                return hits[0]

    hits = glob.glob("/usr/share/fonts/**/*Serif*.ttf", recursive=True)
    if hits:
        return hits[0]

    raise ThumbnailError(
        "폰트를 찾지 못했습니다. .env에 THUMB_FONT_KO / THUMB_FONT_EN으로 "
        "폰트 파일 경로를 지정하세요. (윈도우 예: C:\\Windows\\Fonts\\batang.ttc)"
    )


def font_for(text: str):
    """텍스트에 한글이 있으면 명조, 아니면 라틴 세리프를 쓴다."""
    return _find_font(korean=bool(_HANGUL.search(text or "")))


# ── 배경 사진 ────────────────────────────────────────────────────────
def list_photos(category: str = "") -> list:
    """쓸 수 있는 배경 사진 목록. 카테고리 폴더를 우선한다."""
    pools = []
    if category:
        pools.append(os.path.join(PHOTO_DIR, category))
    pools.append(PHOTO_DIR)

    for pool in pools:
        if not os.path.isdir(pool):
            continue
        hits = sorted(
            f
            for f in glob.glob(os.path.join(pool, "*"))
            if f.lower().endswith(PHOTO_EXTS) and os.path.isfile(f)
        )
        if hits:
            return hits
    return []


def resolve_layout(layout: str, key: str = "") -> str:
    """auto면 슬러그 해시로 레이아웃을 정한다(같은 글은 항상 같은 결과)."""
    if layout in LAYOUTS:
        return layout
    digest = hashlib.sha256((key or "").encode("utf-8")).hexdigest()
    return LAYOUTS[int(digest[8:16], 16) % len(LAYOUTS)]


def pick_photo(key: str, category: str = "") -> str:
    """글마다 같은 사진이 나오도록 슬러그 해시로 고른다.

    무작위로 고르면 재생성할 때마다 썸네일이 바뀌어 관리가 어렵습니다.
    """
    photos = list_photos(category)
    if not photos:
        return ""
    digest = hashlib.sha256((key or "").encode("utf-8")).hexdigest()
    return photos[int(digest[:8], 16) % len(photos)]


def _cover(img, width: int = WIDTH, height: int = HEIGHT):
    """비율을 유지한 채 화면을 꽉 채우도록 자른다(CSS object-fit: cover)."""
    from PIL import Image

    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_h = height
        new_w = round(height * src_ratio)
    else:
        new_w = width
        new_h = round(width / src_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return img.crop((left, top, left + width, top + height))


# ── 브랜드 로고 ──────────────────────────────────────────────────────
def load_logo(path: str = "", width: int = 0):
    """누끼 딴 로고 PNG를 불러와 크기와 색을 맞춘다.

    로고 원본은 흰 배경에 진한 글자인 경우가 많습니다. 투명 PNG로 잘라 두면
    알파 채널에 글자 모양이 남으므로, 그 모양만 크림색으로 다시 칠합니다.
    """
    from PIL import Image

    path = path or LOGO_PATH
    if not path:
        return None
    if not os.path.exists(path):
        # 조용히 텍스트로 넘어가면 왜 로고가 안 나오는지 알 수가 없다.
        logger.warning(
            "로고 파일이 없어 텍스트('%s')로 대체합니다: %s\n"
            "  배경을 지운(누끼) 투명 PNG를 그 경로에 두거나 .env에 THUMB_LOGO로 경로를 지정하세요.",
            BRAND_TEXT, os.path.abspath(path),
        )
        return None

    try:
        logo = Image.open(path).convert("RGBA")
    except Exception as exc:
        logger.warning("로고를 열지 못해 텍스트로 대체합니다 (%s): %s", path, exc)
        return None

    opaque = logo.getchannel("A").getextrema() == (255, 255)
    if opaque:
        logger.warning(
            "로고에 투명 영역이 없습니다: %s\n"
            "  배경이 사각형으로 그대로 얹힙니다. 배경을 지운 PNG로 교체하세요.",
            os.path.abspath(path),
        )

    width = width or LOGO_WIDTH
    if logo.width != width:
        height = max(1, round(logo.height * width / logo.width))
        logo = logo.resize((width, height), Image.LANCZOS)

    # 투명 영역이 없는 이미지를 크림색으로 칠하면 통째로 크림색 사각형이 된다.
    # 그러면 원인을 알 수 없으므로, 그럴 때는 원본을 그대로 얹어 문제가 눈에 보이게 한다.
    if LOGO_TINT and not opaque:
        tinted = Image.new("RGBA", logo.size, TEXT_COLOR)
        tinted.putalpha(logo.getchannel("A"))
        return tinted
    return logo


def logo_status(path: str = "") -> dict:
    """로고 설정 상태. 화면과 CLI에서 사람에게 보여 주기 위한 것."""
    path = path or LOGO_PATH
    abs_path = os.path.abspath(path) if path else ""
    if not path or not os.path.exists(path):
        return {
            "ok": False,
            "path": abs_path,
            "message": f"로고 미등록 — {abs_path}에 배경을 지운 투명 PNG를 넣으면 "
                       f"텍스트 '{BRAND_TEXT}' 대신 로고가 들어갑니다.",
        }
    try:
        from PIL import Image

        img = Image.open(path).convert("RGBA")
    except Exception as exc:
        return {"ok": False, "path": abs_path, "message": f"로고를 열지 못했습니다: {exc}"}

    if img.getchannel("A").getextrema() == (255, 255):
        return {
            "ok": False,
            "path": abs_path,
            "message": "로고에 투명 영역이 없습니다. 배경이 사각형으로 얹힙니다. "
                       "배경을 지운 PNG로 교체하세요.",
        }
    return {"ok": True, "path": abs_path, "message": f"로고 사용 중 ({os.path.basename(path)})"}


# ── 텍스트 ───────────────────────────────────────────────────────────
def _tracked_width(draw, text: str, font, tracking: float) -> int:
    if not text:
        return 0
    total = sum(draw.textbbox((0, 0), ch, font=font)[2] for ch in text)
    return round(total + tracking * (len(text) - 1))


def _draw_tracked(draw, x: int, y: int, text: str, font, fill, tracking: float) -> None:
    """자간을 벌려 그린다. PIL에는 자간 기능이 없어 글자 단위로 그린다."""
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textbbox((0, 0), ch, font=font)[2] + tracking


def _fit_font(ImageFont, path: str, draw, lines: list, max_width: int,
              start: int, tracking: float):
    """모든 줄이 max_width에 들어가는 가장 큰 크기를 찾는다."""
    size = start
    while size > 18:
        font = ImageFont.truetype(path, size)
        widest = max(_tracked_width(draw, line, font, tracking) for line in lines)
        if widest <= max_width:
            return font
        size -= 3
    return ImageFont.truetype(path, 18)


def _wrap(text: str, korean: bool) -> list:
    """제목을 2줄 이내로 나눈다."""
    text = (text or "").strip()
    if not text:
        return [""]
    limit = 10 if korean else 16
    if len(text) <= limit:
        return [text]
    lines = textwrap.wrap(text, width=limit) or [text]
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return lines[:2]


# ── 어두움막 (가독성) ─────────────────────────────────────────────────
def _band_luma(img, top: int, bottom: int) -> float:
    """글자가 놓일 가로 띠의 평균 밝기를 잰다."""
    band = img.crop((0, max(0, top), WIDTH, min(HEIGHT, bottom))).convert("L")
    # ImageStat은 Pillow 버전에 관계없이 안정적이다.
    from PIL import ImageStat

    return ImageStat.Stat(band).mean[0]


def _apply_scrim(img, bands: list):
    """글자가 놓이는 영역마다 필요한 만큼만 반투명 검정을 덧씌운다.

    세기를 고정하면 밝은 사진에서는 글씨가 묻히고 어두운 사진에서는 답답해집니다.
    영역별로 실제 밝기를 재서 각각에 필요한 농도를 정하고, 경계는 부드럽게 잇습니다.

    bands: [(top, bottom, feather)] - feather는 위아래로 번지는 픽셀 수
    """
    from PIL import Image, ImageFilter

    profile = [0.0] * HEIGHT
    for top, bottom, feather in bands:
        luma = _band_luma(img, top, bottom)
        needed = (
            0.0
            if luma <= TARGET_BACKDROP_LUMA
            else (luma - TARGET_BACKDROP_LUMA) / 255.0 * 1.9
        )
        strength = min(0.74, max(0.16, needed + 0.16))
        for y in range(HEIGHT):
            if top <= y <= bottom:
                value = strength
            else:
                dist = (top - y) if y < top else (y - bottom)
                if dist >= feather:
                    continue
                # smoothstep - 영역 경계와 끝점 모두에서 기울기가 0이라 띠가 생기지 않는다
                t = dist / feather
                value = strength * (1 - (3 * t * t - 2 * t * t * t))
            if value > profile[y]:
                profile[y] = value

    # 전체를 아주 살짝 눌러 톤을 정리한다.
    floor = 0.10
    overlay = Image.new("L", (1, HEIGHT), 0)
    px = overlay.load()
    for y in range(HEIGHT):
        px[0, y] = int(max(0, min(255, max(profile[y], floor) * 255)))

    # 남은 미세한 층을 지운다.
    overlay = overlay.filter(ImageFilter.GaussianBlur(18))

    mask = overlay.resize((WIDTH, HEIGHT))
    dark = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    return Image.composite(dark, img, mask)


# ── 합성 ─────────────────────────────────────────────────────────────
def compose(
    title: str,
    brand: str = "",
    photo: str = "",
    layout: str = "",
    out_path: str = "",
    logo: str = "",
) -> str:
    """사진 위에 제목을 올린 썸네일을 만든다."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise ThumbnailError(
            "Pillow가 없습니다. pip install -r requirements.txt 를 실행하세요."
        ) from exc

    layout = resolve_layout(layout or DEFAULT_LAYOUT, title)
    brand = brand or BRAND_TEXT
    out_path = out_path or os.path.join(os.getenv("THUMB_DIR", "thumbnails"), "thumb.jpg")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # 배경
    if photo and os.path.exists(photo):
        try:
            base = _cover(Image.open(photo).convert("RGB"))
        except Exception as exc:
            raise ThumbnailError(f"배경 사진을 열지 못했습니다 ({photo}): {exc}") from exc
    else:
        base = Image.new("RGB", (WIDTH, HEIGHT), FALLBACK_BG)
        logger.warning(
            "배경 사진이 없어 단색으로 만듭니다. %s 폴더에 사진을 넣어 주세요.", PHOTO_DIR
        )

    korean = bool(_HANGUL.search(title))
    title_font_path = font_for(title)
    brand_font_path = font_for(brand)

    probe = ImageDraw.Draw(base)
    lines = _wrap(title, korean)

    # 레이아웃별 크기·자간
    if layout == LAYOUT_BOTTOM:
        max_w, start_size, tracking = WIDTH - 110, 92, 2.0
    else:
        max_w, start_size, tracking = WIDTH - 150, 118, 1.0

    title_font = _fit_font(ImageFont, title_font_path, probe, lines, max_w, start_size, tracking)
    brand_font = ImageFont.truetype(brand_font_path, 25 if korean else 27)
    brand_tracking = 3.0

    line_h = round(title_font.size * 1.16)
    title_h = line_h * len(lines)
    divider_h = 76
    gap = 22

    logo_img = load_logo(logo)
    brand_h = logo_img.height if logo_img else brand_font.size + 8

    # 배치 계산 + 어두움막을 씌울 영역
    if layout == LAYOUT_BOTTOM:
        brand_y = 46
        divider_y = brand_y + brand_h + 14
        title_y = HEIGHT - 78 - title_h
        bands = [
            # 상단 브랜드 + 구분선
            (brand_y - 24, divider_y + divider_h + 16, 130),
            # 하단 제목
            (title_y - 26, HEIGHT, 190),
        ]
    else:
        block_h = title_h + gap + divider_h + gap + brand_h
        title_y = (HEIGHT - block_h) // 2
        divider_y = title_y + title_h + gap
        brand_y = divider_y + divider_h + gap
        bands = [(title_y - 30, brand_y + brand_h + 30, 150)]

    img = _apply_scrim(base, bands)
    draw = ImageDraw.Draw(img)

    # 제목
    y = title_y
    for line in lines:
        w = _tracked_width(draw, line, title_font, tracking)
        _draw_tracked(draw, (WIDTH - w) // 2, y, line, title_font, TEXT_COLOR, tracking)
        y += line_h

    # 세로 구분선
    draw.rectangle(
        [WIDTH // 2, divider_y, WIDTH // 2 + 1, divider_y + divider_h], fill=TEXT_COLOR
    )

    # 브랜드 - 로고가 있으면 로고를, 없으면 텍스트를 얹는다
    if logo_img:
        img.paste(logo_img, ((WIDTH - logo_img.width) // 2, brand_y), logo_img)
    elif brand:
        w = _tracked_width(draw, brand, brand_font, brand_tracking)
        _draw_tracked(
            draw, (WIDTH - w) // 2, brand_y, brand, brand_font, TEXT_COLOR, brand_tracking
        )

    # 300KB 이하로 저장
    for quality in (92, 86, 80, 74, 68, 60, 52, 44):
        img.save(out_path, "JPEG", quality=quality, optimize=True, progressive=True)
        if os.path.getsize(out_path) <= MAX_BYTES:
            logger.info(
                "썸네일 생성: %s (%.0fKB, quality=%d, layout=%s)",
                out_path, os.path.getsize(out_path) / 1024, quality, layout,
            )
            return out_path

    raise ThumbnailError(
        f"썸네일을 {MAX_BYTES // 1024}KB 이하로 줄이지 못했습니다: {out_path}"
    )


def generate(headline: str, subline: str = "", out_path: str = "", photo: str = "",
             layout: str = "", logo: str = "") -> str:
    """이전 인터페이스 유지용 얇은 래퍼."""
    return compose(
        title=headline, brand=subline or BRAND_TEXT, photo=photo,
        layout=layout, out_path=out_path, logo=logo,
    )


def generate_for(doc: dict, out_dir: str = "", layout: str = "", logo: str = "") -> str:
    """생성된 글에 맞는 썸네일을 만든다."""
    out_dir = out_dir or os.getenv("THUMB_DIR", "thumbnails")
    slug = (doc.get("post_url") or "post")[:40]
    category = doc.get("category", "")
    title = doc.get("thumbnail_copy") or doc.get("primary_keyword") or "문제성발톱"

    return compose(
        title=title,
        brand=BRAND_TEXT,
        photo=pick_photo(slug, category),
        layout=resolve_layout(layout or DEFAULT_LAYOUT, slug),
        out_path=os.path.join(out_dir, f"{slug}.jpg"),
        logo=logo,
    )
