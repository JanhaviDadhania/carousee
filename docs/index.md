# carousee

Generate Instagram/LinkedIn carousel slides from a plain text script.

```
pip install carousee
```

Requires an Anthropic API key for LLM parsing:
```
export ANTHROPIC_API_KEY=sk-...
```

---

## Usage

### CLI

```bash
carousee my_script.md
```

Options:

- `--output <dir>` — output directory (default: `./output`)
- `--yaml-only` — parse to YAML and print, then exit (no images)
- `--yaml-in <file>` — skip LLM parsing, use an existing YAML file directly
- `--skip-cache` — re-download and re-segment even if cached

### Python

```python
from carousee import load_script, parse_script, save_yaml, compose_all

raw = load_script("my_script.md")
yaml_data = parse_script(raw)
save_yaml(yaml_data, "parsed.yaml")

paths = compose_all(yaml_data, output_dir="output")
```

---

## Script format

Write slides in plain text — carousee uses an LLM to parse them into YAML automatically.

```
slide 1: Einstein and Bohr arguing
* Einstein: "God does not play dice."
* Bohr: "Stop telling God what to do."

slide 2: text only
this argument lasted 30 years.
neither of them was entirely wrong.

slide 3: only Einstein
* Einstein: "I still don't like it."
```

---

## Custom images

By default carousee fetches portraits from Wikipedia and objects from Wikimedia Commons.
You can supply your own images instead.

**1. Set the custom images folder:**

```python
import carousee
carousee.set_custom_dir("/path/to/my/images")
```

**2. Reference the filename in your script:**

```
slide 1: Einstein
* Einstein: "God does not play dice."
* image: my_einstein.jpg
```

For objects, just use the filename with an extension — carousee detects it automatically:

```
slide 1: Newton
* Newton: "What goes up..."
* objects: [apple.png, telescope]
```

- `apple.png` — loaded from your custom folder (has extension)
- `telescope` — fetched from the internet (no extension)

---

## YAML schema

You can also write or edit the YAML directly and pass it in with `--yaml-in`.

```yaml
slides:
  - id: 1
    type: text | person | group
```

### `type: text` — text-only slide

```yaml
- id: 1
  type: text
  body: "this changed everything.\nno one saw it coming."
```

- `body` — the text to display
- Use `\n` to split into separate segments
- Prefix a segment with `[small]` to render it at a smaller font size

### `type: person` — single character with quote

```yaml
- id: 2
  type: person
  name: "Albert Einstein"
  quote: "God does not play dice."
  heading: "Einstein, 1926"
  image: "my_einstein.jpg"           # optional — use custom image instead of Wikipedia
  objects:
    - apple
  description: "apple falling on Einstein's head from top-right"
```

### `type: group` — multiple characters side by side

```yaml
- id: 3
  type: group
  heading: "The Great Debate"
  subheading: "Solvay Conference, 1927"
  people:
    - name: "Albert Einstein"
      quote: "God does not play dice."
      image: "my_einstein.jpg"       # optional custom image per person
    - name: "Niels Bohr"
      quote: "Stop telling God what to do."
  objects:
    - chalkboard
  description: "chalkboard behind both of them"
```

---

## How portraits work

Carousee fetches portraits from Wikipedia automatically using the character's name. Images are cached in `~/.carousee/cache/` after the first download.

If a portrait isn't found automatically, you can add a name override in `fetcher.py`:

```python
NAME_OVERRIDES = {
    "Bohr": "Niels Bohr",
}
```

---

## Output

Slides are saved as 1080×1080 PNG files in the output directory:

```
output/
  slide_001.png
  slide_002.png
  ...
```
