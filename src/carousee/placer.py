"""
placer.py
Asks the LLM to decide x/y/scale/rotation for each visual element in a slide.
Uses Haiku (fast/cheap) since this is layout data, not content generation.
"""

import hashlib
import os
import random
import subprocess

import yaml

PLACER_PROMPT = """You are a dramatic editorial layout designer for 1080×1080 Instagram carousel slides.

Given slide content, output exact placement coordinates for each visual element.

CANVAS: 1080×1080 px. All values are fractions of canvas dimensions.
  x           — horizontal center of element (0.0 = left, 1.0 = right)
  y           — vertical position of element's FEET/bottom (1.0 = canvas bottom)
  scale       — element height as fraction of canvas height. NO constraints — shrink or
                enlarge anything to serve the composition and description.
  rotation    — degrees, any value
  bubble_x    — x of the speech bubble tail tip (where the tail points, near the mouth)
  bubble_y    — y of the speech bubble tail tip
  bubble_side — "left" or "right": which side of the tail tip the bubble body appears on
                (use the side with more empty space)

Only include bubble_x / bubble_y / bubble_side for elements that have a quote.
Place bubbles so they don't overlap each other or cover the faces.

THE SPATIAL DESCRIPTION IS THE ONLY RULE. Follow it exactly and literally.
Ignore any instinct to keep people large — size and position everything to serve the scene.

Output ONLY valid YAML, no commentary, no fences:

placement:
  Isaac Newton:
    x: 0.28
    y: 0.97
    scale: 0.44
    rotation: -1.5
    bubble_x: 0.18
    bubble_y: 0.42
    bubble_side: right
  apple:
    x: 0.62
    y: 0.25
    scale: 0.12
    rotation: -22.0
    bubble_x: 0.72
    bubble_y: 0.12
    bubble_side: left
"""


def get_placement(
    slide: dict,
    people: list[str],
    objects: list[str],
) -> dict[str, dict]:
    """
    Ask the LLM to place elements. Returns {name: {x, y, scale, rotation}}.
    Falls back to deterministic defaults if the LLM call fails.
    """
    all_elements = people + objects
    if not all_elements:
        return {}

    summary = _summarize_slide(slide, people, objects)

    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            result = _place_via_api(summary)
        else:
            result = _place_via_cli(summary)
        # Normalise keys: LLM may omit spaces/capitalisation (e.g. "IsaacNewton")
        result = _normalise_keys(result, all_elements)
        # Fill any still-missing elements with defaults
        defaults = _default_placement(slide, people, objects)
        for name in all_elements:
            if name not in result:
                result[name] = defaults[name]
        print(f"  [placer] placement: {result}")
        return result
    except Exception as e:
        print(f"  [placer] LLM placement failed, using defaults: {e}")
        return _default_placement(slide, people, objects)


def _summarize_slide(slide: dict, people: list[str], objects: list[str]) -> str:
    lines = [
        f"Slide id: {slide.get('id', 1)}, type: {slide.get('type', 'person')}",
        f"People to place: {', '.join(people) if people else 'none'}",
        f"Objects to place: {', '.join(objects) if objects else 'none'}",
    ]
    if slide.get("heading"):
        lines.append(f"Heading (drawn at top): \"{slide['heading']}\"")
    for p in slide.get("people", []):
        lines.append(f"  {p['name']} says: \"{p.get('quote', '')}\"")
    if slide.get("character"):
        lines.append(f"  {slide['character']} says: \"{slide.get('quote', '')}\"")
    for p in slide.get("left", []):
        lines.append(f"  {p['name']} says: \"{p.get('quote', '')}\"")
    for p in slide.get("right", []):
        lines.append(f"  {p['name']} says: \"{p.get('quote', '')}\"")
    obj_quotes = slide.get("object_quotes", {})
    for obj, q in obj_quotes.items():
        lines.append(f"  {obj} says: \"{q}\"")
    if slide.get("description"):
        lines.append(f"Spatial description: {slide['description']}")
    return "\n".join(lines)


def _place_via_api(summary: str) -> dict[str, dict]:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"{PLACER_PROMPT}\n\nSlide:\n{summary}",
        }],
    )
    return _parse_placement(msg.content[0].text.strip())


def _place_via_cli(summary: str) -> dict[str, dict]:
    prompt = f"{PLACER_PROMPT}\n\nSlide:\n{summary}"
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True, text=True, timeout=90,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed: {result.stderr}")
    return _parse_placement(result.stdout.strip())


def _parse_placement(yaml_text: str) -> dict[str, dict]:
    if yaml_text.startswith("```"):
        lines = yaml_text.split("\n")
        yaml_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    data = yaml.safe_load(yaml_text) or {}
    return data.get("placement", {})


def _rng(name: str) -> random.Random:
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def _normalise_keys(result: dict, expected: list[str]) -> dict:
    """Match LLM-returned keys to expected names by stripping spaces/case."""
    def _canon(s: str) -> str:
        return s.lower().replace(" ", "").replace("_", "").replace("-", "")

    canon_to_expected = {_canon(n): n for n in expected}
    normalised = {}
    for key, val in result.items():
        matched = canon_to_expected.get(_canon(key), key)
        normalised[matched] = val
    return normalised


def _default_placement(
    slide: dict,
    people: list[str],
    objects: list[str],
) -> dict[str, dict]:
    """Deterministic fallback placement when the LLM call fails."""
    placement = {}
    n = len(people)
    slide_id = slide.get("id", 1)

    for i, name in enumerate(people):
        rng = _rng(name + str(slide_id))
        if n == 1:
            x = 0.63 if slide_id % 2 == 1 else 0.37
            scale = 0.87 + rng.uniform(-0.05, 0.05)
        else:
            x = 0.15 + (i + 0.5) * (0.70 / n)
            scale = 0.72 - n * 0.03 + rng.uniform(-0.04, 0.04)
        placement[name] = {
            "x": round(x + rng.uniform(-0.03, 0.03), 3),
            "y": round(0.95 + rng.uniform(-0.02, 0.02), 3),
            "scale": round(max(0.45, scale), 3),
            "rotation": round(rng.uniform(-8, 8), 1),
        }

    for i, obj in enumerate(objects):
        rng = _rng(obj + str(slide_id))
        placement[obj] = {
            "x": round(0.25 + i * 0.15 + rng.uniform(-0.05, 0.05), 3),
            "y": round(0.82 + rng.uniform(-0.04, 0.04), 3),
            "scale": round(0.20 + rng.uniform(-0.03, 0.03), 3),
            "rotation": round(rng.uniform(-15, 15), 1),
        }

    return placement
