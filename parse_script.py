"""
parse_script.py
Converts raw carousel script text → structured YAML via `claude -p` CLI.
"""

import subprocess
import yaml
from pathlib import Path

SYSTEM_PROMPT = """You convert raw carousel scripts into structured YAML.

Output ONLY valid YAML — no markdown fences, no commentary, no extra keys.

Schema:
background: "#111111"
slides:
  - id: <int>
    type: split | solo | text_card
    # for type: split
    left:
      - name: <str>
        quote: <str>      # null if no quote
    right:
      - name: <str>
        quote: <str>
    # for type: solo
    character: <str>
    quote: <str>
    # for type: text_card
    title: <str>          # optional
    body: <str>

Rules:
- "split" = two groups of characters facing each other (left side vs right side)
- "solo" = single character with one quote, centered
- "text_card" = no characters, just text
- Keep quotes verbatim from the script. If a slide has characters but no explicit quotes shown, set quote to null.
- Infer slide type from context. "only X saying Y" -> solo. Narrative text block -> text_card.
- Always output background: "#111111"
"""


def parse_script(raw_text: str) -> dict:
    """Shell out to `claude -p` to convert raw script → YAML dict."""
    prompt = f"{SYSTEM_PROMPT}\n\nScript to convert:\n{raw_text}"

    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed:\n{result.stderr}")

    yaml_text = result.stdout.strip()

    # Strip markdown fences if Claude added them anyway
    if yaml_text.startswith("```"):
        lines = yaml_text.split("\n")
        yaml_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return yaml.safe_load(yaml_text)


def load_script(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def save_yaml(data: dict, path: str | Path) -> None:
    Path(path).write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 parse_script.py <script_file>")
        sys.exit(1)
    raw = load_script(sys.argv[1])
    data = parse_script(raw)
    print(yaml.dump(data, allow_unicode=True, sort_keys=False))
