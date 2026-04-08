"""
cli.py
`carousee` terminal command entry point.
"""

import argparse
import sys
import yaml
from pathlib import Path

from carousee.parser import load_script, parse_script, save_yaml
from carousee.composer import compose_all


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="carousee",
        description="Generate carousel slides from a plain text script.",
    )
    parser.add_argument("script", help="Path to script file (.md or .txt)")
    parser.add_argument("--output", default="output", help="Output directory (default: ./output)")
    parser.add_argument("--skip-cache", action="store_true", help="Re-download and re-segment even if cached")
    parser.add_argument("--yaml-only", action="store_true", help="Parse to YAML and print, then exit")
    parser.add_argument("--yaml-in", help="Skip LLM parsing — use an existing YAML file")
    args = parser.parse_args()

    # Step 1: get YAML
    if args.yaml_in:
        print(f"[carousee] Loading YAML from {args.yaml_in}...")
        yaml_data = yaml.safe_load(Path(args.yaml_in).read_text())
    else:
        print(f"[carousee] Parsing script: {args.script}")
        raw_text = load_script(args.script)
        yaml_data = parse_script(raw_text)
        yaml_out = Path(args.script).stem + "_parsed.yaml"
        save_yaml(yaml_data, yaml_out)
        print(f"[carousee] Parsed YAML saved to: {yaml_out}")

    if args.yaml_only:
        print(yaml.dump(yaml_data, allow_unicode=True, sort_keys=False))
        return

    # Step 2: compose
    paths = compose_all(yaml_data, output_dir=args.output, skip_cache=args.skip_cache)
    print(f"\n[carousee] Done! {len(paths)} slide(s) in '{args.output}/':")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
