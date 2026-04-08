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
        "medium":  50,
        "large":   62,
        "title":   76,
    }
    fonts = {}
    for key, size in sizes.items():
        bold = key in ("medium", "large", "title")
        # Prefer Caveat (handwriting) — fall back to Inter, then system
        candidates = [
            font_dir / "PatrickHand-Regular.ttf",
            font_dir / ("Caveat-Bold.ttf" if bold else "Caveat-Regular.ttf"),
            font_dir / ("Inter-Bold.ttf"  if bold else "Inter-Regular.ttf"),
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

def layout_split(slide: dict, fonts: dict, cutouts: dict) -> Image.Image:
    """
    Left group — characters as equal ensemble.
    Right single character — dominant if present.
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

    n = len(left_chars)
    FLOOR = H + 40
    has_right = bool(right_chars)

    if not has_right:
        # ── 3-column bottom-aligned layout — no overlap ─────────────────────
        # Divide canvas into equal slots; scale each figure to fit its slot.
        slot_count = min(n, 3)
        slot_w = (W - 2 * MARGIN) // slot_count
        FLOOR = H - 30  # all feet at this y
        bubble_sides = ["right", "right", "left"]

        # Stagger bubble anchor y so adjacent bubbles don't collide:
        # left & right go high, center sits a bit lower
        bubble_anchor_y_fracs = [0.30, 0.42, 0.30]

        for i, char in enumerate(left_chars[:slot_count]):
            rng = _rng(char.name)
            slot_left = MARGIN + i * slot_w
            slot_cx   = slot_left + slot_w // 2

            if char.cutout:
                # Scale so width fits inside slot (no overlap guarantee)
                max_w = slot_w - 24
                cw, ch = char.cutout.size
                scale  = min(max_w / cw, 820 / ch)
                img_w  = int(cw * scale)
                img_h  = int(ch * scale)
                img = char.cutout.resize((img_w, img_h), Image.LANCZOS)
                angle = rng.uniform(-6, 6)
                img = _rotate_cutout(img, angle)

                px = slot_cx - img.width // 2
                py = FLOOR - img.height
                _paste_with_shadow(canvas, img, (px, py))
                draw = ImageDraw.Draw(canvas)
                face_cx = px + img.width // 2
            else:
                face_cx = slot_cx

            # Bubble anchored at a fixed staggered y in the upper portion of canvas
            anchor_y = int(H * bubble_anchor_y_fracs[i])

            draw.text(
                (slot_cx, H - 14), char.name.upper(),
                font=fonts["tiny"], fill=NAME_COLOR, anchor="mt",
            )

            if char.quote:
                bside = bubble_sides[i] if i < len(bubble_sides) else "right"
                bbox = draw_speech_bubble(
                    draw, char.quote, fonts["small"],
                    anchor_xy=(face_cx, anchor_y),
                    side=bside,
                    max_width=slot_w - 10,
                    above=True,
                )
                _tape_over_bubble(canvas, bbox, rng)
                draw = ImageDraw.Draw(canvas)

    else:
        # ── Standard split layout (left group + right dominant) ───────────
        slot_w = (W // 2 - 20 - MARGIN // 2) // max(n, 1)
        base_h = 340

        for i, char in enumerate(left_chars):
            rng = _rng(char.name)
            fig_h = base_h + rng.randint(-60, 80)
            floor_offset = rng.randint(0, 80)
            foot_y = FLOOR - floor_offset
            slot_cx = MARGIN // 2 + i * slot_w + slot_w // 2

            if char.cutout:
                img = _scale_to_height(char.cutout, fig_h)
                angle = rng.uniform(-5, 5)
                img = _rotate_cutout(img, angle)
                px = slot_cx - img.width // 2
                py = foot_y - img.height
                _paste_with_shadow(canvas, img, (px, py))
                face_y  = py + int(img.height * 0.20)
                face_cx = px + img.width // 2
            else:
                face_y  = foot_y - fig_h + 80
                face_cx = slot_cx

            name_x = max(MARGIN, slot_cx - slot_w // 2)
            name_y = min(foot_y + 4, H - 8)
            draw.text((name_x, name_y), char.name.upper(), font=fonts["tiny"], fill=NAME_COLOR)

            if char.quote:
                bside = "right" if i % 2 == 0 else "left"
                draw_speech_bubble(
                    draw, char.quote, fonts["small"],
                    anchor_xy=(face_cx, face_y),
                    side=bside,
                    max_width=min(slot_w + 120, 340),
                    above=True,
                )

    # Right character: large, dominant
    if has_right:
        RIGHT_X0 = W // 2 + 10
        char = right_chars[0]
        rng = _rng(char.name + "_right")
        fig_h = 760 + rng.randint(-30, 50)

        if char.cutout:
            img = _scale_to_height(char.cutout, fig_h)
            angle = rng.uniform(-5, 5)
            img = _rotate_cutout(img, angle)
            right_cx = RIGHT_X0 + (W - RIGHT_X0) // 2 + rng.randint(-40, 40)
            px = max(RIGHT_X0 - 20, right_cx - img.width // 2)
            py = FLOOR - img.height
            _paste_with_shadow(canvas, img, (px, py))
            face_y = py + int(img.height * 0.14)
            face_cx = px + img.width // 2
        else:
            face_y = H // 4
            face_cx = RIGHT_X0 + (W - RIGHT_X0) // 2

        draw.text(
            (RIGHT_X0 + MARGIN, H - 24),
            char.name.upper(),
            font=fonts["tiny"], fill=NAME_COLOR,
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

    _draw_slide_counter(draw, fonts, slide)
    return canvas.convert("RGBA")


# ── Layout: solo ──────────────────────────────────────────────────────────────

def layout_solo(slide: dict, fonts: dict, cutouts: dict) -> Image.Image:
    """
    Single character. Large. Pushed left or right — never centered.
    Quote bubble commands the negative space on the other side.
    """
    canvas = Image.new("RGBA", (W, H), BG_COLOR)
    _draw_journal_bg(canvas)
    draw = ImageDraw.Draw(canvas)

    name = slide.get("character", "")
    quote = slide.get("quote", "")
    cutout = cutouts.get(name)
    # Seed with slide id so same character looks different across slides
    rng = _rng(name + str(slide.get("id", "")))

    FLOOR = H + 40
    fig_h = 900 + rng.randint(-40, 60)

    # Odd slide ids push right, even push left — ensures visual contrast
    slide_id = slide.get("id", 1)
    if slide_id % 2 == 0:
        cx = int(W * rng.uniform(0.30, 0.45))   # left-leaning
    else:
        cx = int(W * rng.uniform(0.52, 0.65))   # right-leaning

    if cutout:
        img = _scale_to_height(cutout, fig_h)
        angle = rng.uniform(-12, 12)
        img = _rotate_cutout(img, angle)
        px = cx - img.width // 2
        py = FLOOR - img.height
        _paste_with_shadow(canvas, img, (px, py))
        draw = ImageDraw.Draw(canvas)
        face_y = py + int(img.height * 0.12)
        face_cx = px + img.width // 2
    else:
        face_y = H // 5
        face_cx = cx

    # Name: bottom-left, uppercase, muted
    draw.text((MARGIN, H - MARGIN + 10), name.upper(), font=fonts["small"], fill=NAME_COLOR)

    if quote:
        # Choose font based on quote length
        q_font = fonts["large"] if len(quote) < 60 else fonts["medium"]
        # Bubble always on the side with more negative space
        if face_cx < W // 2:
            bside = "right"
            anchor_x = face_cx + rng.randint(10, 40)
        else:
            bside = "left"
            anchor_x = face_cx - rng.randint(10, 40)

        bubble_bbox = draw_speech_bubble(
            draw, quote, q_font,
            anchor_xy=(anchor_x, face_y + rng.randint(0, 40)),
            side=bside,
            max_width=580,
            above=True,
        )
        _tape_over_bubble(canvas, bubble_bbox, rng)
        draw = ImageDraw.Draw(canvas)

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

    # Vertical accent bar — left edge, warm amber
    draw.rectangle([(MARGIN, MARGIN), (MARGIN + 10, H - MARGIN)], fill=ACCENT_COLOR)

    title = slide.get("title") or ""
    body = slide.get("body", "")
    text_x = MARGIN + 36
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

    _draw_slide_counter(draw, fonts, slide)
    return canvas.convert("RGBA")


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
