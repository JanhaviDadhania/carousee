"""
fetch_images.py
Downloads portrait images from Wikimedia Commons with local cache.
"""

import hashlib
import urllib.parse
from pathlib import Path

import requests

CACHE_DIR = Path("cache/images")
WIKIMEDIA_API = "https://en.wikipedia.org/w/api.php"
TIMEOUT = 15
# Wikipedia requires a descriptive User-Agent to avoid 403s
HEADERS = {
    "User-Agent": "CarouselGenerator/1.0 (educational tool; https://github.com/example) python-requests/2.31"
}

# Override article titles for names that don't match Wikipedia directly
NAME_OVERRIDES = {
    "Michelson": "Albert A. Michelson",
    "Poincaré": "Henri Poincaré",
    "Poincare": "Henri Poincaré",
    "Lorentz": "Hendrik Lorentz",
    "Einstein": "Albert Einstein",
    "Boyle": "Robert Boyle",
    "Miller": "Dayton Miller",
}


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("é", "e").replace("ó", "o")


def _wikimedia_thumb_url(filename: str, width: int = 800) -> str:
    """Construct deterministic Wikimedia thumbnail URL from filename."""
    encoded = filename.replace(" ", "_")
    md5 = hashlib.md5(encoded.encode()).hexdigest()
    a, ab = md5[0], md5[:2]
    quoted = urllib.parse.quote(encoded, safe="")
    base = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{a}/{ab}/{quoted}/{width}px-{quoted}"
    # SVG files need .png appended
    if encoded.lower().endswith(".svg"):
        base += ".png"
    return base


def search_portrait(name: str) -> str | None:
    """Query Wikipedia for the lead image filename of a person's article."""
    article_title = NAME_OVERRIDES.get(name, name)
    params = {
        "action": "query",
        "titles": article_title,
        "prop": "pageimages",
        "piprop": "name",
        "pithumbsize": 800,
        "format": "json",
        "redirects": 1,
    }
    try:
        resp = requests.get(WIKIMEDIA_API, params=params, timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        pages = resp.json()["query"]["pages"]
        page = next(iter(pages.values()))
        return page.get("pageimage")
    except Exception as e:
        print(f"  [fetch] Wikipedia search failed for '{name}': {e}")
        return None


def download_portrait(name: str, force: bool = False) -> Path:
    """
    Download and cache portrait for a character name.
    Returns local Path to cached image.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)

    # Check cache first
    for ext in ("jpg", "jpeg", "png", "webp"):
        cached = CACHE_DIR / f"{slug}.{ext}"
        if cached.exists() and not force:
            print(f"  [fetch] Cache hit: {cached.name}")
            return cached

    print(f"  [fetch] Searching Wikimedia for '{name}'...")
    filename = search_portrait(name)
    if not filename:
        raise FileNotFoundError(f"No portrait found on Wikipedia for '{name}'")

    url = _wikimedia_thumb_url(filename, width=800)
    print(f"  [fetch] Downloading: {url}")

    resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
    resp.raise_for_status()

    # Infer extension
    content_type = resp.headers.get("content-type", "")
    if "png" in content_type:
        ext = "png"
    elif "webp" in content_type:
        ext = "webp"
    else:
        ext = "jpg"

    out_path = CACHE_DIR / f"{slug}.{ext}"
    out_path.write_bytes(resp.content)
    print(f"  [fetch] Saved: {out_path}")
    return out_path


def prefetch_all(names: list[str]) -> dict[str, Path]:
    """Download portraits for all unique names. Returns {name: path}."""
    results = {}
    for name in names:
        try:
            results[name] = download_portrait(name)
        except Exception as e:
            print(f"  [fetch] FAILED for '{name}': {e}")
    return results


if __name__ == "__main__":
    import sys
    names = sys.argv[1:] or ["Albert Einstein", "Michelson"]
    for n in names:
        try:
            p = download_portrait(n)
            print(f"OK: {p}")
        except Exception as e:
            print(f"FAIL: {e}")
