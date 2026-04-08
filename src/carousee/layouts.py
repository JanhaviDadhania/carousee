"""
layouts.py
Slide layout renderers: split, solo, text_card.
Style: dramatic, dark background, light text, bold left-aligned type,
       big portrait cutouts, chaotic/asymmetric alignment, magazine-quality.
All produce 1080x1080 RGBA Images.
"""

import hashlib
import math
import random
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W = H = 1080
MARGIN = 54
BG_COLOR = "#F7F4EE"           # warm off-white, journal paper
LINE_COLOR = "#DDD8CC"         # faint ruled lines
LINE_SPACING = 44              # px between journal lines
ACCENT_COLOR = "#E07B39"       # warm amber for emphasis
BUBBLE_BG = "#FFFFFF"          # white inside bubble
BUBBLE_BORDER = "#111111"      # black border
BUBBLE_TEXT = "#111111"        # black text
BUBBLE_BORDER_W = 3            # border thickness
NAME_COLOR = "#AAAAAA"
BODY_COLOR = "#111111"
COUNTER_COLOR = "#BBBBBB"
SHADOW_COLOR = (0, 0, 0, 55)

BUBBLE_PAD_X = 26
BUBBLE_PAD_Y = 20
TAIL_H = 20
TAIL_W = 22


@dataclass
class CharacterCard:
    name: str
    cutout: Optional[Image.Image]
    quote: Optional[str]


# ── Deterministic chaos ───────────────────────────────────────────────────────

def _rng(name: str) -> random.Random:
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


# ── Font helpers ──────────────────────────────────────────────────────────────

def load_fonts(font_dir) -> dict:
    # Handwriting sizes — slightly larger since Caveat reads small
    sizes = {
        "tiny":    24,
        "small":   32,
        "regular": 40,
        "medium":  58,
        "large":   80,
        "title":   96,
    }
    fonts = {}
    for key, size in sizes.items():
        bold = key in ("medium", "large", "title")
        # Prefer Caveat (handwriting) — fall back to Inter, then system
        bubble = key in ("small", "tiny")
        candidates = [
            font_dir / "Lora-Bold.ttf" if bubble else font_dir / "ApfelGrotezk-Fett.otf",
            font_dir / "ApfelGrotezk-Regular.otf",
            font_dir / "Inter-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for fpath in candidates:
            try:
                fonts[key] = ImageFont.truetype(str(fpath), size)
                break
            except Exception:
                pass
        else:
            fonts[key] = ImageFont.load_default()
    return fonts


# ── Journal background ────────────────────────────────────────────────────────

def _draw_journal_bg(canvas: Image.Image) -> None:
    """Fill canvas with warm off-white + faint graph paper grid (horizontal + vertical lines)."""
    canvas.paste(BG_COLOR, [0, 0, W, H])
    draw = ImageDraw.Draw(canvas)
    # Horizontal lines
    y = LINE_SPACING
    while y < H:
        draw.line([(0, y), (W, y)], fill=LINE_COLOR, width=1)
        y += LINE_SPACING
    # Vertical lines — same spacing → graph paper / grid
    x = LINE_SPACING
    while x < W:
        draw.line([(x, 0), (x, H)], fill=LINE_COLOR, width=1)
        x += LINE_SPACING


# ── Deal With It glasses ──────────────────────────────────────────────────────

def _draw_deal_with_it_glasses(canvas: Image.Image, cx: int, eye_y: int, width: int) -> None:
    """
    Draw chunky 8-bit pixel sunglasses centered at (cx, eye_y).
    width: total span of both lenses + bridge.
    """
    pixel = max(4, width // 40)          # pixel block size for 8-bit feel
    lens_w = int(width * 0.42)
    lens_h = int(lens_w * 0.38)
    bridge_w = int(width * 0.08)
    bridge_h = pixel * 2

    # Slight tilt — left lens a touch higher than right (swagger)
    tilt = int(lens_h * 0.08)

    # Left lens (slightly higher)
    lx0 = cx - bridge_w // 2 - lens_w
    ly0 = eye_y - lens_h // 2 - tilt
    # Right lens (slightly lower)
    rx0 = cx + bridge_w // 2
    ry0 = eye_y - lens_h // 2 + tilt

    def _pixelated_rect(img, x0, y0, w, h, color):
        """Fill a rectangle with pixel blocks for chunky 8-bit look."""
        d = ImageDraw.Draw(img)
        p = pixel
        for row in range(0, h, p):
            for col in range(0, w, p):
                bx = x0 + col
                by = y0 + row
                # Slight highlight on top-left pixels for depth
                c = (40, 40, 40, 255) if (row < p or col < p) else color
                d.rectangle([(bx, by), (bx + p - 1, by + p - 1)], fill=c)

    BLACK = (10, 10, 10, 255)

    _pixelated_rect(canvas, lx0, ly0, lens_w, lens_h, BLACK)
    _pixelated_rect(canvas, rx0, ry0, lens_w, lens_h, BLACK)

    # Bridge connecting lenses
    draw = ImageDraw.Draw(canvas)
    bridge_y = eye_y - bridge_h // 2
    draw.rectangle([(lx0 + lens_w, bridge_y), (rx0, bridge_y + bridge_h)], fill=BLACK)

    # Thin arms extending outward
    arm_len = int(width * 0.12)
    arm_h = pixel
    draw.rectangle([(lx0 - arm_len, ly0 + lens_h // 2 - arm_h // 2),
                    (lx0, ly0 + lens_h // 2 + arm_h // 2)], fill=BLACK)
    draw.rectangle([(rx0 + lens_w, ry0 + lens_h // 2 - arm_h // 2),
                    (rx0 + lens_w + arm_len, ry0 + lens_h // 2 + arm_h // 2)], fill=BLACK)


# ── Image helpers ─────────────────────────────────────────────────────────────

def _scale_to_height(cutout: Image.Image, target_h: int) -> Image.Image:
    cw, ch = cutout.size
    scale = target_h / ch
    return cutout.resize((int(cw * scale), target_h), Image.LANCZOS)


def _rotate_cutout(img: Image.Image, angle: float) -> Image.Image:
    return img.rotate(angle, expand=True, resample=Image.BICUBIC)


def _paste_with_shadow(canvas: Image.Image, cutout: Image.Image, pos: tuple[int, int]) -> None:
    """Paste cutout with a soft drop shadow beneath it."""
    shadow_offset = (12, 18)
    shadow_blur = 20

    # Build shadow layer same size as cutout
    shadow = Image.new("RGBA", cutout.size, (0, 0, 0, 0))
    r, g, b, a = cutout.split()
    shadow_fill = Image.new("RGBA", cutout.size, SHADOW_COLOR)
    shadow.paste(shadow_fill, mask=a)
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))

    sx = pos[0] + shadow_offset[0]
    sy = pos[1] + shadow_offset[1]

    # Expand canvas region if shadow bleeds — just clamp
    canvas.paste(shadow, (sx, sy), mask=shadow)
    canvas.paste(cutout, pos, mask=cutout)


# ── Washi tape ───────────────────────────────────────────────────────────────

def _make_tape_strip(tape_w: int, tape_h: int, color: tuple) -> Image.Image:
    """Build a single tape strip RGBA image with subtle texture lines."""
    tape_img = Image.new("RGBA", (tape_w, tape_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(tape_img)
    d.rectangle([(0, 0), (tape_w - 1, tape_h - 1)], fill=color)
    # Subtle vertical grain lines
    r, g, b, a = color
    line_col = (max(0, r - 20), max(0, g - 20), max(0, b - 20), 80)
    for x in range(0, tape_w, 10):
        d.line([(x, 0), (x, tape_h)], fill=line_col, width=1)
    # Slightly darker edges (top/bottom) for thickness feel
    edge_col = (max(0, r - 30), max(0, g - 30), max(0, b - 30), a)
    d.line([(0, 0), (tape_w, 0)], fill=edge_col, width=2)
    d.line([(0, tape_h - 1), (tape_w, tape_h - 1)], fill=edge_col, width=2)
    return tape_img


def _tape_over_bubble(canvas: Image.Image, bubble_bbox: tuple, rng: random.Random) -> None:
    """
    Lay a single washi tape strip over a speech bubble, centered on it.
    The tape is semi-transparent so bubble text remains readable.
    bubble_bbox: (bx0, by0, bx1, by1)
    """
    bx0, by0, bx1, by1 = bubble_bbox
    bw = bx1 - bx0
    bh = by1 - by0

    tape_w = bw + rng.randint(60, 100)   # overhang on each side
    tape_h = 44
    opacity = 140                         # semi-transparent — text shows through
    tape_color = (228, 210, 155, opacity)

    strip = _make_tape_strip(tape_w, tape_h, tape_color)
    angle = rng.uniform(-8, 8)
    strip = strip.rotate(angle, expand=True, resample=Image.BICUBIC)

    # Center strip on the middle of the bubble
    cx = (bx0 + bx1) // 2
    cy = (by0 + by1) // 2
    tx = cx - strip.width // 2
    ty = cy - strip.height // 2
    canvas.paste(strip, (tx, ty), mask=strip)


# ── Hand-drawn wobbly bubble ──────────────────────────────────────────────────

def _wobbly_oval(draw: ImageDraw.Draw, bbox: tuple, color: str, width: int, rng: random.Random) -> None:
    """
    Draw a slightly wobbly oval outline — approximated with a polygon of many points
    with small random perturbations, giving a hand-drawn feel.
    bbox: (x0, y0, x1, y1)
    """
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    steps = 48
    wobble = min(rx, ry) * 0.045   # subtle wobble amplitude
    pts = []
    for k in range(steps):
        theta = 2 * math.pi * k / steps
        r_jitter = rng.uniform(-wobble, wobble)
        x = cx + (rx + r_jitter) * math.cos(theta)
        y = cy + (ry + r_jitter) * math.sin(theta)
        pts.append((x, y))
    # No fill — transparent interior, just the wobbly outline
    draw.line(pts + [pts[0]], fill=color, width=width)


# ── Text helpers ──────────────────────────────────────────────────────────────

def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        try:
            w = font.getlength(test)
        except AttributeError:
            w = len(test) * 10
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    try:
        bb = font.getbbox("Ay")
        return bb[3] - bb[1]
    except Exception:
        return 30


# ── Speech bubble (circular pill, black border, white fill) ──────────────────

def draw_speech_bubble(
    draw: ImageDraw.Draw,
    text: str,
    font: ImageFont.FreeTypeFont,
    anchor_xy: tuple[int, int],
    side: str,       # 'left' | 'right' — which side tail points from
    max_width: int,
    above: bool = True,
    dry_run: bool = False,   # if True, return bbox without drawing anything
) -> tuple[int, int, int, int]:
    lines = _wrap_text(text, font, max_width - 2 * BUBBLE_PAD_X)
    lh = _line_height(font)
    spacing = int(lh * 0.28)
    th = len(lines) * lh + max(0, len(lines) - 1) * spacing

    tw = 0
    for line in lines:
        try:
            tw = max(tw, int(font.getlength(line)))
        except AttributeError:
            tw = max(tw, len(line) * 10)

    bw = tw + 2 * BUBBLE_PAD_X
    bh = th + 2 * BUBBLE_PAD_Y
    # Pill shape: radius is half the height so it's fully circular on ends
    radius = bh // 2
    ax, ay = anchor_xy

    if above:
        by1 = ay - TAIL_H
        by0 = by1 - bh
    else:
        by0 = ay + TAIL_H
        by1 = by0 + bh

    if side == "right":
        bx0 = ax - 14
        bx1 = bx0 + bw
    else:
        bx1 = ax + 14
        bx0 = bx1 - bw

    # Clamp to canvas
    if bx1 > W - 14:
        bx0 -= (bx1 - (W - 14))
        bx1 = W - 14
    if bx0 < 14:
        bx1 += (14 - bx0)
        bx0 = 14
    by0 = max(14, by0)
    by1 = min(H - 14, by1)

    if dry_run:
        return (bx0, by0, bx1, by1)

    # Seed wobble from text content so same quote always looks the same
    brng = random.Random(hash(text) & 0xFFFFFFFF)

    # Wobbly oval — hand-drawn feel
    _wobbly_oval(draw, (bx0, by0, bx1, by1), BUBBLE_BORDER, BUBBLE_BORDER_W, brng)

    # Hand-drawn tail: a slightly curved arrow line, not a filled triangle
    tail_base_y = by1 if above else by0
    if side == "right":
        tail_x = bx0 + max(20, (bx1 - bx0) // 4)
    else:
        tail_x = bx1 - max(20, (bx1 - bx0) // 4)

    # Two-segment kinked line for hand-drawn arrow feel
    mid_x = tail_x + brng.randint(-8, 8)
    mid_y = (tail_base_y + ay) // 2 + brng.randint(-10, 10)
    draw.line([(tail_x, tail_base_y), (mid_x, mid_y), (ax, ay)],
              fill=BUBBLE_BORDER, width=BUBBLE_BORDER_W)
    # Small arrowhead at tip
    ah = 10
    draw.line([(ax, ay), (ax - ah, ay - ah)], fill=BUBBLE_BORDER, width=BUBBLE_BORDER_W)
    draw.line([(ax, ay), (ax + ah, ay - ah)], fill=BUBBLE_BORDER, width=BUBBLE_BORDER_W)

    # Text inside
    ty = by0 + BUBBLE_PAD_Y
    for line in lines:
        draw.text((bx0 + BUBBLE_PAD_X, ty), line, font=font, fill=BUBBLE_TEXT)
        ty += lh + spacing

    return (bx0, by0, bx1, by1)


# ── Layout: split (group of scientists) ──────────────────────────────────────

def layout_split(slide: dict, fonts: dict, cutouts: dict, placement: dict = None) -> Image.Image:
    """
    Group of characters. Heading/subheading at top. LLM-driven placement when available.
    Falls back to equal-slot layout when placement is not provided.
    """
    canvas = Image.new("RGBA", (W, H), BG_COLOR)
    _draw_journal_bg(canvas)
    draw = ImageDraw.Draw(canvas)

    left_chars = [
        CharacterCard(c["name"], cutouts.get(c["name"]), c.get("quote"))
        for c in slide.get("left", [])
    ]
    right_chars = [
        CharacterCard(c["name"], cutouts.get(c["name"]), c.get("quote"))
        for c in slide.get("right", [])
    ]
    all_chars = left_chars + right_chars
    n = len(left_chars)
    has_right = bool(right_chars)

    # ── Heading / subheading ───────────────────────────────────────────────────
    heading = slide.get("heading", "")
    subheading = slide.get("subheading", "")
    text_y = MARGIN
    if heading:
        h_lines = _wrap_text(heading, fonts["title"], W - 2 * MARGIN)
        lh = _line_height(fonts["title"])
        for line in h_lines:
            draw.text((MARGIN, text_y), line, font=fonts["title"], fill=BODY_COLOR)
            text_y += lh + 8
    if subheading:
        draw.text((MARGIN, text_y + 4), subheading, font=fonts["regular"], fill="#888888")

    # ── Place characters ───────────────────────────────────────────────────────
    def _place_char(char: CharacterCard, fallback_cx: int, fallback_h: int, fallback_floor: int, fallback_angle: float):
        p = (placement or {}).get(char.name, {})
        if p:
            cx     = int(p["x"] * W)
            foot_y = int(p["y"] * H)
            fig_h  = int(p["scale"] * H)
            angle  = float(p.get("rotation", 0))
        else:
            cx     = fallback_cx
            foot_y = fallback_floor
            fig_h  = fallback_h
            angle  = fallback_angle

        face_cx, face_y = cx, H // 4
        if char.cutout:
            img = _scale_to_height(char.cutout, fig_h)
            img = _rotate_cutout(img, angle)
            px = cx - img.width // 2
            py = foot_y - img.height
            _paste_with_shadow(canvas, img, (px, py))
            draw2 = ImageDraw.Draw(canvas)
            face_cx = px + img.width // 2
            face_y  = py + int(img.height * 0.18)
            return face_cx, face_y, draw2
        return face_cx, face_y, ImageDraw.Draw(canvas)

    if not has_right:
        slot_count = min(n, 3)
        slot_w = (W - 2 * MARGIN) // max(slot_count, 1)
        FLOOR = H - 30
        bubble_sides = ["right", "right", "left"]
        bubble_anchor_y_fracs = [0.47, 0.57, 0.47]

        for i, char in enumerate(left_chars[:slot_count]):
            rng = _rng(char.name)
            slot_cx = MARGIN + i * slot_w + slot_w // 2
            cw, ch = char.cutout.size if char.cutout else (1, 1)
            max_w = slot_w - 24
            fallback_h = int(min(max_w / cw, 820 / ch) * ch) if char.cutout else 600
            fallback_angle = rng.uniform(-6, 6)

            face_cx, face_y, draw = _place_char(
                char, slot_cx, fallback_h, FLOOR, fallback_angle
            )

            if char.quote:
                cp = (placement or {}).get(char.name, {})
                if cp.get("bubble_x") is not None:
                    anchor_x = int(cp["bubble_x"] * W)
                    anchor_y = int(cp["bubble_y"] * H)
                    bside    = cp.get("bubble_side", "left" if anchor_x > W // 2 else "right")
                else:
                    bside    = bubble_sides[i] if i < len(bubble_sides) else "right"
                    anchor_x = face_cx
                    anchor_y = int(H * bubble_anchor_y_fracs[i])
                kw = dict(anchor_xy=(anchor_x, anchor_y), side=bside,
                          max_width=slot_w - 10, above=True)
                bbox = draw_speech_bubble(draw, char.quote, fonts["small"], **kw, dry_run=True)
                _tape_over_bubble(canvas, bbox, rng)
                draw = ImageDraw.Draw(canvas)
                draw_speech_bubble(draw, char.quote, fonts["small"], **kw)

    else:
        # Old split schema: left group + right dominant character
        slot_w = (W // 2 - 20 - MARGIN // 2) // max(n, 1)

        for i, char in enumerate(left_chars):
            rng = _rng(char.name)
            fallback_h = 340 + rng.randint(-60, 80)
            fallback_floor = H + 40 - rng.randint(0, 80)
            slot_cx = MARGIN // 2 + i * slot_w + slot_w // 2

            face_cx, face_y, draw = _place_char(
                char, slot_cx, fallback_h, fallback_floor, rng.uniform(-5, 5)
            )
            if char.quote:
                cp = (placement or {}).get(char.name, {})
                if cp.get("bubble_x") is not None:
                    bside    = cp.get("bubble_side", "right")
                    face_cx  = int(cp["bubble_x"] * W)
                    face_y   = int(cp["bubble_y"] * H)
                else:
                    bside = "right" if i % 2 == 0 else "left"
                draw_speech_bubble(
                    draw, char.quote, fonts["small"],
                    anchor_xy=(face_cx, face_y),
                    side=bside,
                    max_width=min(slot_w + 120, 340),
                    above=True,
                )

        char = right_chars[0]
        rng = _rng(char.name + "_right")
        face_cx, face_y, draw = _place_char(
            char,
            fallback_cx=W // 2 + 10 + (W - W // 2) // 2 + rng.randint(-40, 40),
            fallback_h=760 + rng.randint(-30, 50),
            fallback_floor=H + 40,
            fallback_angle=rng.uniform(-5, 5),
        )
        if char.quote:
            bub_side = "left" if face_cx > W * 0.6 else "right"
            draw_speech_bubble(
                draw, char.quote, fonts["medium"],
                anchor_xy=(face_cx, face_y + 80),
                side=bub_side,
                max_width=460,
                above=True,
            )

    # ── Objects ────────────────────────────────────────────────────────────────
    obj_quotes = slide.get("object_quotes", {})
    for obj_name in slide.get("objects", []):
        obj_cutout = cutouts.get(obj_name)
        if not obj_cutout:
            continue
        op = (placement or {}).get(obj_name, {})
        obj_rng = _rng(obj_name)
        obj_cx    = int(op["x"] * W)     if op else int(W * obj_rng.uniform(0.2, 0.8))
        obj_foot  = int(op["y"] * H)     if op else int(H * 0.82)
        obj_h     = int(op["scale"] * H) if op else int(H * 0.22)
        obj_angle = float(op.get("rotation", 0)) if op else obj_rng.uniform(-15, 15)
        obj_img = _scale_to_height(obj_cutout, obj_h)
        obj_img = _rotate_cutout(obj_img, obj_angle)
        _paste_with_shadow(canvas, obj_img, (obj_cx - obj_img.width // 2, obj_foot - obj_img.height))
        draw = ImageDraw.Draw(canvas)
        obj_quote = obj_quotes.get(obj_name)
        if obj_quote:
            if op.get("bubble_x") is not None:
                ob_ax = int(op["bubble_x"] * W)
                ob_ay = int(op["bubble_y"] * H)
                ob_side = op.get("bubble_side", "left" if ob_ax > W // 2 else "right")
            else:
                ob_ay = obj_foot - int(obj_h * 0.5)
                ob_ax = obj_cx
                ob_side = "left" if obj_cx > W // 2 else "right"
            draw_speech_bubble(draw, obj_quote, fonts["small"],
                               anchor_xy=(ob_ax, ob_ay),
                               side=ob_side, max_width=320, above=True)

    _draw_slide_counter(draw, fonts, slide)
    return canvas.convert("RGBA")


# ── Layout: solo ──────────────────────────────────────────────────────────────

def layout_solo(slide: dict, fonts: dict, cutouts: dict, placement: dict = None) -> Image.Image:
    """
    Single character. Large. Pushed left or right — never centered.
    Quote bubble commands the negative space on the other side.
    Accepts optional LLM-provided placement; falls back to rng-based positioning.
    """
    canvas = Image.new("RGBA", (W, H), BG_COLOR)
    _draw_journal_bg(canvas)
    draw = ImageDraw.Draw(canvas)

    name = slide.get("character", "")
    quote = slide.get("quote", "")
    heading = slide.get("heading", "")
    cutout = cutouts.get(name)
    rng = _rng(name + str(slide.get("id", "")))

    # Optional heading above the portrait
    text_y = MARGIN
    if heading:
        h_lines = _wrap_text(heading, fonts["regular"], W - 2 * MARGIN)
        lh = _line_height(fonts["regular"])
        for line in h_lines:
            draw.text((MARGIN, text_y), line, font=fonts["regular"], fill="#888888")
            text_y += lh + 6

    # ── Position from LLM placement or rng fallback ────────────────────────────
    p = (placement or {}).get(name, {})
    if p:
        cx     = int(p["x"] * W)
        foot_y = int(p["y"] * H)
        fig_h  = int(p["scale"] * H)
        angle  = float(p.get("rotation", 0))
    else:
        slide_id = slide.get("id", 1)
        fig_h  = 900 + rng.randint(-40, 60)
        foot_y = H + 40
        cx     = int(W * (rng.uniform(0.52, 0.65) if slide_id % 2 == 1 else rng.uniform(0.30, 0.45)))
        angle  = rng.uniform(-12, 12)

    if cutout:
        img = _scale_to_height(cutout, fig_h)
        img = _rotate_cutout(img, angle)
        px = cx - img.width // 2
        py = foot_y - img.height
        _paste_with_shadow(canvas, img, (px, py))
        draw = ImageDraw.Draw(canvas)
        face_y  = py + int(img.height * 0.12)
        face_cx = px + img.width // 2
    else:
        face_y  = H // 5
        face_cx = cx

    # ── Objects ────────────────────────────────────────────────────────────────
    obj_quotes = slide.get("object_quotes", {})
    for obj_name in slide.get("objects", []):
        obj_cutout = cutouts.get(obj_name)
        if not obj_cutout:
            continue
        op = (placement or {}).get(obj_name, {})
        obj_rng = _rng(obj_name)
        obj_cx    = int(op["x"] * W)     if op else int(W * obj_rng.uniform(0.2, 0.8))
        obj_foot  = int(op["y"] * H)     if op else int(H * 0.82)
        obj_h     = int(op["scale"] * H) if op else int(H * 0.22)
        obj_angle = float(op.get("rotation", 0)) if op else obj_rng.uniform(-15, 15)
        obj_img = _scale_to_height(obj_cutout, obj_h)
        obj_img = _rotate_cutout(obj_img, obj_angle)
        _paste_with_shadow(canvas, obj_img, (obj_cx - obj_img.width // 2, obj_foot - obj_img.height))
        draw = ImageDraw.Draw(canvas)
        obj_quote = obj_quotes.get(obj_name)
        if obj_quote:
            if op.get("bubble_x") is not None:
                ob_ax = int(op["bubble_x"] * W)
                ob_ay = int(op["bubble_y"] * H)
                ob_side = op.get("bubble_side", "left" if ob_ax > W // 2 else "right")
            else:
                ob_ay = obj_foot - int(obj_h * 0.5)
                ob_ax = obj_cx
                ob_side = "left" if obj_cx > W // 2 else "right"
            draw_speech_bubble(draw, obj_quote, fonts["small"],
                               anchor_xy=(ob_ax, ob_ay),
                               side=ob_side, max_width=320, above=True)

    # ── Speech bubble ──────────────────────────────────────────────────────────
    if quote:
        q_font = fonts["large"] if len(quote) < 60 else fonts["medium"]
        if p.get("bubble_x") is not None:
            anchor_x = int(p["bubble_x"] * W)
            anchor_y = int(p["bubble_y"] * H)
            bside    = p.get("bubble_side", "left" if anchor_x > W // 2 else "right")
        else:
            if face_cx < W // 2:
                bside = "right"
                anchor_x = face_cx + rng.randint(10, 40)
            else:
                bside = "left"
                anchor_x = face_cx - rng.randint(10, 40)
            anchor_y = face_y + rng.randint(0, 40)

        kw = dict(anchor_xy=(anchor_x, anchor_y), side=bside, max_width=580, above=True)
        bbox = draw_speech_bubble(draw, quote, q_font, **kw, dry_run=True)
        _tape_over_bubble(canvas, bbox, rng)
        draw = ImageDraw.Draw(canvas)
        draw_speech_bubble(draw, quote, q_font, **kw)

    _draw_slide_counter(draw, fonts, slide)
    return canvas.convert("RGBA")


# ── Layout: text_card ─────────────────────────────────────────────────────────

def layout_text_card(slide: dict, fonts: dict, cutouts: dict) -> Image.Image:
    """
    Bold typographic card. Left-aligned. Asymmetric accent bar on left edge.
    Text is big — readable at a glance.
    """
    canvas = Image.new("RGBA", (W, H), BG_COLOR)
    _draw_journal_bg(canvas)
    draw = ImageDraw.Draw(canvas)

    title = slide.get("title") or ""
    body = slide.get("body", "")
    short_statement = not title and len(body.replace("[small]", "").replace("\n", "")) < 160

    # Vertical accent bar only for long-form text cards
    if not short_statement:
        draw.rectangle([(MARGIN, MARGIN), (MARGIN + 10, H - MARGIN)], fill=ACCENT_COLOR)

    text_x = MARGIN + (36 if not short_statement else 0)
    text_w = W - text_x - MARGIN
    y = MARGIN + 20

    if title:
        title_lines = _wrap_text(title, fonts["title"], text_w)
        lh = _line_height(fonts["title"])
        for line in title_lines:
            draw.text((text_x, y), line, font=fonts["title"], fill=BODY_COLOR)
            y += lh + 12
        y += 32

    if body:
        # Short punchy statement (no title, under ~120 chars) → big type filling page
        if short_statement:
            font_big = fonts["title"]
            lh_big = _line_height(font_big)
            font_sm = fonts["regular"]
            lh_sm = _line_height(font_sm)

            # Parse segments: lines starting with [small] use smaller font,
            # \n alone inserts extra gap
            raw_segments = body.split("\n")
            # [small] tag applies only to that one segment, then resets to big
            rendered = []
            for seg in raw_segments:
                if seg.startswith("[small]"):
                    fnt, lh = font_sm, lh_sm
                    seg = seg[len("[small]"):]
                else:
                    fnt, lh = font_big, lh_big
                wrapped = _wrap_text(seg.strip(), fnt, text_w)
                rendered.append((wrapped, fnt, lh))

            total_h = sum(
                len(lines) * lh + (len(lines) - 1) * int(lh * 0.20) + int(lh_big * 0.35)
                for lines, _, lh in rendered
            )
            y = (H - total_h) // 2
            for lines, fnt, lh in rendered:
                for line in lines:
                    draw.text((text_x, y), line, font=fnt, fill=BODY_COLOR)
                    y += lh + int(lh * 0.20)
                y += int(lh_big * 0.35)  # gap between segments
        else:
            # First sentence in larger bold as a pull quote
            sentences = body.split(". ", 1)
            pull = sentences[0].strip() + ("." if len(sentences) > 1 else "")
            rest = sentences[1].strip() if len(sentences) > 1 else ""

            pull_lines = _wrap_text(pull, fonts["small"], text_w)
            lh_pull = _line_height(fonts["small"])
            for line in pull_lines:
                draw.text((text_x, y), line, font=fonts["small"], fill="#111111")
                y += lh_pull + int(lh_pull * 0.30)
            y += 36

            if rest:
                rest_lines = _wrap_text(rest, fonts["regular"], text_w)
                lh_rest = _line_height(fonts["regular"])
                for line in rest_lines:
                    draw.text((text_x, y), line, font=fonts["regular"], fill="#333333")
                    y += lh_rest + int(lh_rest * 0.65)

    if slide.get("logo"):
        _draw_45d_logo(canvas, draw, fonts)

    _draw_slide_counter(draw, fonts, slide)
    return canvas.convert("RGBA")


# ── 45d logo ─────────────────────────────────────────────────────────────────

def _draw_45d_logo(canvas: Image.Image, draw: ImageDraw.Draw, fonts: dict) -> None:
    """
    Render a styled '45d' text logo in the bottom-right corner.
    Replace this with an image paste once a real logo file is provided.
    """
    logo_font = fonts["medium"]
    text = "45d"
    try:
        tw = int(logo_font.getlength(text))
    except AttributeError:
        tw = len(text) * 30
    lh = _line_height(logo_font)

    pad = MARGIN
    x = W - pad - tw
    y = H - pad - lh

    # Subtle dark background pill
    draw.rounded_rectangle(
        [(x - 16, y - 10), (x + tw + 16, y + lh + 10)],
        radius=8, fill="#111111"
    )
    draw.text((x, y), text, font=logo_font, fill="#FFFFFF")


# ── Shared ────────────────────────────────────────────────────────────────────

def _draw_slide_counter(draw: ImageDraw.Draw, fonts: dict, slide: dict) -> None:
    slide_id = slide.get("id", "")
    if slide_id:
        draw.text(
            (W - MARGIN, H - MARGIN + 20),
            str(slide_id),
            font=fonts["small"],
            fill=COUNTER_COLOR,
            anchor="rt",
        )
