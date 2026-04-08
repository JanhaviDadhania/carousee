"""
segmenter.py
Background removal using rembg (U2Net). Produces RGBA cutout PNGs.
"""

import io
from pathlib import Path

from PIL import Image, ImageFilter

from carousee.fetcher import _slug


def _erode_alpha(img: Image.Image, size: int = 3) -> Image.Image:
    r, g, b, a = img.split()
    a = a.filter(ImageFilter.MinFilter(size))
    return Image.merge("RGBA", (r, g, b, a))


def _pad_bottom(img: Image.Image, frac: float = 0.25) -> tuple[Image.Image, int]:
    w, h = img.size
    pad_h = int(h * frac)
    padded = Image.new("RGB", (w, h + pad_h), "white")
    padded.paste(img.convert("RGB"), (0, 0))
    return padded, h


def remove_background(input_path: Path, cutout_dir: Path, force: bool = False) -> Path:
    from rembg import remove

    cutout_dir.mkdir(parents=True, exist_ok=True)
    out_path = cutout_dir / (input_path.stem + "_cutout.png")

    if out_path.exists() and not force:
        print(f"  [segment] Cache hit: {out_path.name}")
        return out_path

    print(f"  [segment] Removing background: {input_path.name}")
    original = Image.open(input_path).convert("RGB")
    padded, orig_h = _pad_bottom(original, frac=0.25)

    buf = io.BytesIO()
    padded.save(buf, format="PNG")
    result_bytes = remove(buf.getvalue())

    result = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
    result = result.crop((0, 0, result.width, orig_h))
    result = _erode_alpha(result, size=3)
    result.save(out_path, "PNG")
    print(f"  [segment] Saved cutout: {out_path.name}")
    return out_path


def warm_up() -> None:
    print("  [segment] Warming up rembg model...")
    from rembg import remove
    dummy = Image.new("RGB", (64, 64), "white")
    buf = io.BytesIO()
    dummy.save(buf, format="PNG")
    remove(buf.getvalue())
    print("  [segment] Model ready.")
