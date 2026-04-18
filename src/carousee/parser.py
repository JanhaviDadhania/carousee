"""
parser.py
Converts raw carousel script text → structured YAML.
Uses Anthropic API if ANTHROPIC_API_KEY is set, falls back to `claude -p` CLI.
"""

import os
import subprocess
import yaml
from pathlib import Path

SYSTEM_PROMPT = """You convert raw carousel scripts into structured YAML.

Output ONLY valid YAML — no markdown fences, no commentary, no extra keys.

Schema:
slides:
  - id: <int>
    type: text | person | group

    # for type: text
    body: <str>           # supports \\n for hard line breaks, [small] tag for smaller text

    # for type: person
    name: <str>
    quote: <str>
    heading: <str>        # optional label above the photo
    image: <str>          # optional custom image filename (e.g. "einstein.jpg") — overrides internet search
    objects:              # optional list of prop/object images to place on the slide
      - <str>             # object name (e.g. "apple") OR custom filename (e.g. "my_apple.jpg") — filename if it has an extension
    description: <str>   # optional spatial hint for the layout engine, e.g.
                          # "apple falling on Newton's head from top-right"

    # for type: group
    heading: <str>
    subheading: <str>     # optional
    people:
      - name: <str>
        quote: <str>
        image: <str>      # optional custom image filename for this person
    objects:              # optional — same as person
      - <str>
    description: <str>   # optional spatial hint

Rules:
- "text"   = no characters, just text (short punchy statement or longer body)
- "person" = single character with one quote
- "group"  = multiple characters side by side with a heading at top
- Keep quotes verbatim from the script.
- Infer slide type from context.
- Infer objects from context (e.g. "apple falls on head" → objects: [apple]).
- Write a description only when the script implies a specific spatial arrangement.
"""


def _parse_via_api(raw_text: str) -> dict:
    """Use Anthropic Python SDK."""
    import anthropic
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"{SYSTEM_PROMPT}\n\nScript to convert:\n{raw_text}"
        }]
    )
    yaml_text = message.content[0].text.strip()
    return _clean_and_parse(yaml_text)


def _parse_via_cli(raw_text: str) -> dict:
    """Fall back to `claude -p` subprocess."""
    prompt = f"{SYSTEM_PROMPT}\n\nScript to convert:\n{raw_text}"
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed:\n{result.stderr}")
    return _clean_and_parse(result.stdout.strip())


def _clean_and_parse(yaml_text: str) -> dict:
    if yaml_text.startswith("```"):
        lines = yaml_text.split("\n")
        yaml_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return yaml.safe_load(yaml_text)


def parse_script(raw_text: str) -> dict:
    """Parse script → YAML dict. Tries API first, falls back to CLI."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _parse_via_api(raw_text)
    return _parse_via_cli(raw_text)


def load_script(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def save_yaml(data: dict, path: str | Path) -> None:
    Path(path).write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
