"""
composer.py
Orchestrates the full pipeline: parse → fetch → segment → layout → save PNGs.
"""

from pathlib import Path

from PIL import Image

from carousee import layouts
from carousee.fetcher import download_portrait, download_object
from carousee.placer import get_placement
from carousee.segmenter import remove_background, warm_up
from carousee.fonts import ensure_fonts

_custom_dir: Path | None = None


def set_custom_dir(path: str | Path) -> None:
    """Set the directory where user-supplied images are stored."""
    global _custom_dir
    _custom_dir = Path(path)


def _default_dirs() -> tuple[Path, Path, Path, Path]:
    base = Path.home() / ".carousee"
    return (
        base / "fonts",
        base / "cache" / "images",
        base / "cache" / "cutouts",
    )


def collect_names(yaml_data: dict) -> list[str]:
    names = set()
    for slide in yaml_data.get("slides", []):
        for p in slide.get("people", []):
            names.add(p["name"])
        if slide.get("name"):
            names.add(slide["name"])
        for p in slide.get("left", []):
            names.add(p["name"])
        for p in slide.get("right", []):
            names.add(p["name"])
        if slide.get("character"):
            names.add(slide["character"])
    return list(names)


def collect_object_names(yaml_data: dict) -> list[str]:
    objects = set()
    for slide in yaml_data.get("slides", []):
        for obj in slide.get("objects", []):
            objects.add(obj)
    return list(objects)


def collect_image_overrides(yaml_data: dict) -> dict[str, str]:
    """Return {person_name: custom_image_filename} for slides with an explicit image field."""
    overrides = {}
    for slide in yaml_data.get("slides", []):
        if slide.get("image"):
            name = slide.get("name") or slide.get("character")
            if name:
                overrides[name] = slide["image"]
        for person in slide.get("people", []):
            if person.get("image") and person.get("name"):
                overrides[person["name"]] = person["image"]
    return overrides


def prefetch_cutouts(
    names: list[str],
    object_names: list[str],
    image_dir: Path,
    cutout_dir: Path,
    skip_cache: bool = False,
    image_overrides: dict[str, str] | None = None,
) -> dict[str, Image.Image]:
    image_overrides = image_overrides or {}
    cutouts = {}
    for name in names:
        try:
            img_path = download_portrait(
                name, image_dir, force=skip_cache,
                custom_image=image_overrides.get(name),
                custom_dir=_custom_dir,
            )
            cutout_path = remove_background(img_path, cutout_dir, force=skip_cache)
            cutouts[name] = Image.open(cutout_path).convert("RGBA")
        except Exception as e:
            print(f"  [composer] WARNING: no cutout for '{name}': {e}")
            cutouts[name] = None
    for obj in object_names:
        try:
            img_path = download_object(obj, image_dir, force=skip_cache, custom_dir=_custom_dir)
            cutout_path = remove_background(img_path, cutout_dir, force=skip_cache)
            cutouts[obj] = Image.open(cutout_path).convert("RGBA")
        except Exception as e:
            print(f"  [composer] WARNING: no cutout for object '{obj}': {e}")
            cutouts[obj] = None
    return cutouts


def _dispatch(slide: dict, fonts: dict, cutouts: dict) -> Image.Image:
    t = slide.get("type", "text")
    if t in ("group", "split"):
        s = _normalise_group(slide)
        people = [c["name"] for c in s.get("left", [])]
        objects = slide.get("objects", [])
        placement = get_placement(slide, people, objects)
        return layouts.layout_split(s, fonts, cutouts, placement=placement)
    elif t in ("person", "solo"):
        s = _normalise_person(slide)
        people = [s["character"]] if s.get("character") else []
        objects = slide.get("objects", [])
        placement = get_placement(slide, people, objects)
        return layouts.layout_solo(s, fonts, cutouts, placement=placement)
    else:
        return layouts.layout_text_card(slide, fonts, cutouts)


def _normalise_group(slide: dict) -> dict:
    """Map new 'group' schema → layout_split's expected format."""
    s = dict(slide)
    if "people" in s and "left" not in s:
        s["left"] = s.pop("people")
        s["right"] = []
    return s


def _normalise_person(slide: dict) -> dict:
    """Map new 'person' schema → layout_solo's expected format."""
    s = dict(slide)
    if "name" in s and "character" not in s:
        s["character"] = s.pop("name")
    return s


def compose_all(
    yaml_data: dict,
    output_dir: Path,
    skip_cache: bool = False,
    font_dir: Path | None = None,
    image_dir: Path | None = None,
    cutout_dir: Path | None = None,
) -> list[Path]:
    """
    Full pipeline. Returns list of saved PNG paths.
    All cache/font dirs default to ~/.carousee/
    """
    default_font, default_img, default_cut = _default_dirs()
    font_dir   = font_dir   or default_font
    image_dir  = image_dir  or default_img
    cutout_dir = cutout_dir or default_cut
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[carousee] Warming up segmentation model...")
    warm_up()

    print("[carousee] Checking fonts...")
    ensure_fonts(font_dir)

    names = collect_names(yaml_data)
    object_names = collect_object_names(yaml_data)
    image_overrides = collect_image_overrides(yaml_data)
    print(f"[carousee] Characters: {names}")
    if object_names:
        print(f"[carousee] Objects: {object_names}")
    if image_overrides:
        print(f"[carousee] Custom images: {image_overrides}")
    cutouts = prefetch_cutouts(names, object_names, image_dir, cutout_dir, skip_cache, image_overrides)

    fonts = layouts.load_fonts(font_dir)
    paths = []
    for slide in yaml_data.get("slides", []):
        slide_id = slide.get("id", len(paths) + 1)
        print(f"[carousee] Rendering slide {slide_id} ({slide.get('type', '?')})...")
        img = _dispatch(slide, fonts, cutouts)
        out = output_dir / f"slide_{slide_id:03d}.png"
        img.convert("RGB").save(out, "PNG", optimize=True)
        print(f"[carousee] Saved: {out}")
        paths.append(out)

    return paths
