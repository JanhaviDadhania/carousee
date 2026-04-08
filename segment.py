"""
segment.py
Background removal using rembg (U2Net). Produces RGBA cutout PNGs.
"""

import io
from pathlib import Path

from PIL import Image, ImageFilter

CUTOUT_DIR = Path("cache/cutouts")


def _erode_alpha(img: Image.Image, size: int = 3) -> Image.Image:
    """Shrink alpha channel slightly to remove fringe pixels."""
    r, g, b, a = img.split()
    a = a.filter(ImageFilter.MinFilter(size))
    return Image.merge("RGBA", (r, g, b, a))


def _pad_bottom(img: Image.Image, frac: float = 0.25) -> tuple[Image.Image, int]:
    """
    Add white padding at the bottom (helps rembg find a clean cut on bust portraits).
    Returns (padded_image, original_height).
    """
    w, h = img.size
    pad_h = int(h * frac)
    padded = Image.new("RGB", (w, h + pad_h), "white")
    padded.paste(img.convert("RGB"), (0, 0))
    return padded, h


def remove_background(input_path: Path, force: bool = False) -> Path:
    """
    Run rembg on input_path, save RGBA cutout PNG to CUTOUT_DIR.
    Returns Path to the cutout PNG.
    """
    from rembg import remove  # lazy import so the module loads fast

    CUTOUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CUTOUT_DIR / (input_path.stem + "_cutout.png")

    if out_path.exists() and not force:
        print(f"  [segment] Cache hit: {out_path.name}")
        return out_path

    print(f"  [segment] Removing background: {input_path.name}")
    original = Image.open(input_path).convert("RGB")
    padded, orig_h = _pad_bottom(original, frac=0.25)

    # Run rembg on bytes
    buf = io.BytesIO()
    padded.save(buf, format="PNG")
    result_bytes = remove(buf.getvalue())

    result = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
    # Crop back to original height
    result = result.crop((0, 0, result.width, orig_h))
    # Erode alpha to remove fringe
    result = _erode_alpha(result, size=3)

    result.save(out_path, "PNG")
    print(f"  [segment] Saved cutout: {out_path.name}")
    return out_path


def load_cutout(name: str) -> Image.Image:
    """Load a cutout PNG by character name slug."""
    from fetch_images import _slug
    slug = _slug(name)
    path = CUTOUT_DIR / f"{slug}_cutout.png"
    if not path.exists():
        raise FileNotFoundError(f"No cutout found for '{name}' at {path}")
    return Image.open(path).convert("RGBA")


def warm_up() -> None:
    """Pre-download the U2Net model so it doesn't stall mid-pipeline."""
    print("  [segment] Warming up rembg model...")
    from rembg import remove
    # Run on a tiny dummy image to trigger model download
    dummy = Image.new("RGB", (64, 64), "white")
    buf = io.BytesIO()
    dummy.save(buf, format="PNG")
    remove(buf.getvalue())
    print("  [segment] Model ready.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python segment.py <image_path>")
        sys.exit(1)
    p = remove_background(Path(sys.argv[1]), force=True)
    print(f"Cutout saved to: {p}")
