"""
fetcher.py
Downloads portrait images from Wikimedia Commons with local cache.
"""

import hashlib
import urllib.parse
from pathlib import Path

import requests

TIMEOUT = 15
WIKIMEDIA_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": "Carousee/0.1 (educational carousel generator; https://github.com/example) python-requests/2.31"
}

NAME_OVERRIDES = {
    "Michelson": "Albert A. Michelson",
    "Poincaré":  "Henri Poincaré",
    "Poincare":  "Henri Poincaré",
    "Lorentz":   "Hendrik Lorentz",
    "Einstein":  "Albert Einstein",
    "Boyle":     "Robert Boyle",
    "Miller":    "Dayton Miller",
}


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("é", "e").replace("ó", "o")


def _wikimedia_thumb_url(filename: str, width: int = 800) -> str:
    encoded = filename.replace(" ", "_")
    md5 = hashlib.md5(encoded.encode()).hexdigest()
    a, ab = md5[0], md5[:2]
    quoted = urllib.parse.quote(encoded, safe="")
    base = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{a}/{ab}/{quoted}/{width}px-{quoted}"
    if encoded.lower().endswith(".svg"):
        base += ".png"
    return base


def search_portrait(name: str) -> str | None:
    article_title = NAME_OVERRIDES.get(name, name)
    params = {
        "action": "query", "titles": article_title,
        "prop": "pageimages", "piprop": "name",
        "pithumbsize": 800, "format": "json", "redirects": 1,
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


def search_object(name: str) -> str | None:
    """Search Wikimedia Commons for an object image filename."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srnamespace": 6,   # File namespace on Commons
        "srlimit": 5,
        "format": "json",
    }
    try:
        resp = requests.get(COMMONS_API, params=params, timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        results = resp.json()["query"]["search"]
        if not results:
            return None
        # Title looks like "File:Apple.jpg" — strip the prefix
        return results[0]["title"].replace("File:", "")
    except Exception as e:
        print(f"  [fetch] Commons search failed for '{name}': {e}")
        return None


def download_object(name: str, cache_dir: Path, force: bool = False, custom_dir: Path | None = None) -> Path:
    """Download an object image from Wikimedia Commons, or use a custom image if name is a filename."""
    # If name looks like a filename (has extension), use custom dir
    if custom_dir and Path(name).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        custom_path = custom_dir / name
        if custom_path.exists():
            print(f"  [fetch] Using custom object image: {custom_path}")
            return custom_path
        raise FileNotFoundError(f"Custom object image not found: {custom_path}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    slug = "obj_" + _slug(name)

    for ext in ("jpg", "jpeg", "png", "webp"):
        cached = cache_dir / f"{slug}.{ext}"
        if cached.exists() and not force:
            print(f"  [fetch] Cache hit: {cached.name}")
            return cached

    print(f"  [fetch] Searching Commons for object '{name}'...")
    filename = search_object(name)
    if not filename:
        raise FileNotFoundError(f"No image found on Wikimedia Commons for '{name}'")

    url = _wikimedia_thumb_url(filename, width=600)
    print(f"  [fetch] Downloading: {url}")
    resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    ext = "png" if "png" in content_type else "webp" if "webp" in content_type else "jpg"
    out_path = cache_dir / f"{slug}.{ext}"
    out_path.write_bytes(resp.content)
    print(f"  [fetch] Saved: {out_path}")
    return out_path


def download_portrait(
    name: str,
    cache_dir: Path,
    force: bool = False,
    custom_image: str | None = None,
    custom_dir: Path | None = None,
) -> Path:
    # Use custom image if specified
    if custom_image and custom_dir:
        custom_path = custom_dir / custom_image
        if custom_path.exists():
            print(f"  [fetch] Using custom image: {custom_path}")
            return custom_path
        raise FileNotFoundError(f"Custom image not found: {custom_path}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)

    for ext in ("jpg", "jpeg", "png", "webp"):
        cached = cache_dir / f"{slug}.{ext}"
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

    content_type = resp.headers.get("content-type", "")
    ext = "png" if "png" in content_type else "webp" if "webp" in content_type else "jpg"
    out_path = cache_dir / f"{slug}.{ext}"
    out_path.write_bytes(resp.content)
    print(f"  [fetch] Saved: {out_path}")
    return out_path
