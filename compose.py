"""
compose.py
Orchestrates slide composition: dispatches to layout functions,
loads cutouts, saves output PNGs.
"""

from pathlib import Path

from PIL import Image

import layouts

OUTPUT_DIR = Path("output")


def compose_slide(
    slide_spec: dict,
    fonts: dict,
    cutouts: dict[str, Image.Image],
) -> Image.Image:
    """Dispatch to the appropriate layout function."""
    slide_type = slide_spec.get("type", "text_card")

    if slide_type == "split":
        return layouts.layout_split(slide_spec, fonts, cutouts)
    elif slide_type == "solo":
        return layouts.layout_solo(slide_spec, fonts, cutouts)
    elif slide_type == "text_card":
        return layouts.layout_text_card(slide_spec, fonts, cutouts)
    else:
        raise ValueError(f"Unknown slide type: '{slide_type}'")


def save_slide(img: Image.Image, slide_id: int) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"slide_{slide_id:03d}.png"
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  [compose] Saved: {out_path}")
    return out_path


def compose_all(yaml_data: dict, cutouts: dict[str, Image.Image], font_dir: Path) -> list[Path]:
    """Compose all slides from parsed YAML. Returns list of output paths."""
    fonts = layouts.load_fonts(font_dir)
    paths = []
    for slide_spec in yaml_data.get("slides", []):
        slide_id = slide_spec.get("id", len(paths) + 1)
        print(f"  [compose] Rendering slide {slide_id} ({slide_spec.get('type', '?')})...")
        img = compose_slide(slide_spec, fonts, cutouts)
        paths.append(save_slide(img, slide_id))
    return paths
