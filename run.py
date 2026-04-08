"""
run.py
CLI entry point for the carousel generation pipeline.

Usage:
    python run.py script.md
    python run.py script.md --output ./my_output --skip-cache
    python run.py script.md --yaml-only      # just parse + print YAML, no images
"""

import argparse
import sys
import yaml
from pathlib import Path
from PIL import Image

import fetch_images
import segment
import compose
import parse_script as ps


def collect_character_names(yaml_data: dict) -> list[str]:
    """Walk all slides and collect unique character names."""
    names = set()
    for slide in yaml_data.get("slides", []):
        for char in slide.get("left", []):
            names.add(char["name"])
        for char in slide.get("right", []):
            names.add(char["name"])
        if slide.get("character"):
            names.add(slide["character"])
    return list(names)


def prefetch_cutouts(names: list[str], skip_cache: bool = False) -> dict[str, Image.Image]:
    """
    Download portraits and segment all unique characters.
    Returns {name: RGBA Image}.
    """
    cutouts = {}
    for name in names:
        try:
            img_path = fetch_images.download_portrait(name, force=skip_cache)
            cutout_path = segment.remove_background(img_path, force=skip_cache)
            cutouts[name] = Image.open(cutout_path).convert("RGBA")
        except Exception as e:
            print(f"  [prefetch] WARNING: Could not get cutout for '{name}': {e}")
            cutouts[name] = None  # layout will skip missing cutouts gracefully
    return cutouts


def download_fonts(font_dir: Path) -> None:
    """Download Inter fonts from Google Fonts if not present."""
    import io
    import zipfile
    import requests

    bold_path = font_dir / "Inter-Bold.ttf"
    reg_path = font_dir / "Inter-Regular.ttf"

    if bold_path.exists() and reg_path.exists():
        return

    print("  [fonts] Downloading Inter font from GitHub...")
    try:
        zip_url = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
        resp = requests.get(zip_url, timeout=60)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for member in zf.namelist():
                name = member.split("/")[-1]
                if name == "Inter-Regular.ttf":
                    reg_path.write_bytes(zf.read(member))
                    print(f"  [fonts] Saved Inter-Regular.ttf")
                elif name == "Inter-Bold.ttf":
                    bold_path.write_bytes(zf.read(member))
                    print(f"  [fonts] Saved Inter-Bold.ttf")
    except Exception as e:
        print(f"  [fonts] Could not download Inter: {e}. Will fall back to system font.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate carousel slides from a script.")
    parser.add_argument("script", help="Path to your script file (.md or .txt)")
    parser.add_argument("--output", default="output", help="Output directory (default: output)")
    parser.add_argument("--skip-cache", action="store_true", help="Re-download and re-segment even if cached")
    parser.add_argument("--yaml-only", action="store_true", help="Parse script to YAML and print, then exit")
    parser.add_argument("--yaml-in", help="Skip LLM parsing — use an existing YAML file directly")
    args = parser.parse_args()

    font_dir = Path("fonts")
    font_dir.mkdir(exist_ok=True)
    compose.OUTPUT_DIR = Path(args.output)

    # ── Step 1: Parse script → YAML ──
    if args.yaml_in:
        print(f"[run] Loading YAML from {args.yaml_in}...")
        yaml_data = yaml.safe_load(Path(args.yaml_in).read_text())
    else:
        print(f"[run] Parsing script: {args.script}")
        raw_text = ps.load_script(args.script)
        yaml_data = ps.parse_script(raw_text)

        # Save YAML for inspection
        yaml_out = Path(args.script).stem + "_parsed.yaml"
        ps.save_yaml(yaml_data, yaml_out)
        print(f"[run] Parsed YAML saved to: {yaml_out}")

    if args.yaml_only:
        print(yaml.dump(yaml_data, allow_unicode=True, sort_keys=False))
        return

    # ── Step 2: Warm up segmentation model ──
    print("[run] Warming up segmentation model...")
    segment.warm_up()

    # ── Step 3: Download fonts ──
    download_fonts(font_dir)

    # ── Step 4: Collect unique characters & prefetch cutouts ──
    names = collect_character_names(yaml_data)
    print(f"[run] Characters detected: {names}")
    cutouts = prefetch_cutouts(names, skip_cache=args.skip_cache)

    # ── Step 5: Compose slides ──
    print("[run] Composing slides...")
    output_paths = compose.compose_all(yaml_data, cutouts, font_dir)

    print(f"\n[run] Done! {len(output_paths)} slide(s) saved to '{args.output}/':")
    for p in output_paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
