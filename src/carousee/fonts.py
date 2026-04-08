"""
fonts.py
Downloads and caches all required fonts on first run.
Fonts are stored in ~/.carousee/fonts/
"""

import io
import zipfile
from pathlib import Path

import requests

FONT_URLS = {
    "Inter-Bold.ttf":         "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip",
    "Inter-Regular.ttf":      "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip",
    "BebasNeue-Regular.ttf":  "https://github.com/googlefonts/bebasneue/raw/main/fonts/ttf/BebasNeue-Regular.ttf",
    "Lora-Regular.ttf":       "https://github.com/googlefonts/lora-fonts/raw/main/fonts/ttf/Lora-Regular.ttf",
    "Lora-Bold.ttf":          "https://github.com/googlefonts/lora-fonts/raw/main/fonts/ttf/Lora-Bold.ttf",
    "ApfelGrotezk-Fett.otf":  "https://raw.githubusercontent.com/collletttivo/apfel-grotezk/main/fonts/ApfelGrotezk-Fett.otf",
    "ApfelGrotezk-Regular.otf": "https://raw.githubusercontent.com/collletttivo/apfel-grotezk/main/fonts/ApfelGrotezk-Regular.otf",
}

# Fonts that live inside a zip archive
ZIP_MEMBERS = {"Inter-Bold.ttf", "Inter-Regular.ttf"}


def ensure_fonts(font_dir: Path) -> None:
    """Download any missing fonts into font_dir."""
    font_dir.mkdir(parents=True, exist_ok=True)

    # Inter comes in a zip — download once for both files
    inter_needed = [f for f in ZIP_MEMBERS if not (font_dir / f).exists()]
    if inter_needed:
        _download_inter(font_dir)

    # All other fonts are direct downloads
    for name, url in FONT_URLS.items():
        if name in ZIP_MEMBERS:
            continue
        dest = font_dir / name
        if dest.exists():
            continue
        print(f"  [fonts] Downloading {name}...")
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            print(f"  [fonts] Saved {name}")
        except Exception as e:
            print(f"  [fonts] Could not download {name}: {e}")


def _download_inter(font_dir: Path) -> None:
    zip_url = FONT_URLS["Inter-Bold.ttf"]
    print("  [fonts] Downloading Inter font...")
    try:
        resp = requests.get(zip_url, timeout=60)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for member in zf.namelist():
                name = member.split("/")[-1]
                if name in ZIP_MEMBERS:
                    (font_dir / name).write_bytes(zf.read(member))
                    print(f"  [fonts] Saved {name}")
    except Exception as e:
        print(f"  [fonts] Could not download Inter: {e}")
