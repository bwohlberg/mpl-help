# mpl-help

Backend-independent help windows for [matplotlib](https://matplotlib.org) figures.

Press a configurable trigger key (default **h**) inside any matplotlib figure to
open a styled help panel listing your application's keyboard shortcuts and mouse
controls.

- **No external GUI toolkit** — the help window is itself a matplotlib figure
- **Config-file driven** — define shortcuts in YAML, TOML, or JSON; no code changes needed per figure type
- **Dark and light themes**, with full per-colour overrides
- **Per-section accent colours** — named palette or arbitrary hex
- **Adjustable key column width** — accommodates both short keyboard shortcuts and longer mouse-event descriptions
- **Works with any matplotlib backend** — TkAgg, Qt5Agg, Qt6Agg, WxAgg, …

---

## Installation

### Local (editable) install

```bash
git clone https://github.com/bwohlberg/mpl-help
cd mpl-help
pip install -e ".[config]"   # includes PyYAML + tomli for config file support
```

### From PyPI (once published)

```bash
pip install mpl-help                  # matplotlib only, JSON config works out of the box
pip install "mpl-help[yaml]"          # add YAML support
pip install "mpl-help[toml]"          # add TOML support  (stdlib on Python ≥ 3.11)
pip install "mpl-help[config]"        # add both
```

---

## Quickstart

### Programmatic API

```python
import matplotlib.pyplot as plt
from mpl_help import HelpManager, HelpSection, KeyBinding

fig, ax = plt.subplots()
ax.plot([1, 2, 3])

help_mgr = HelpManager(fig, title="My App — Help", theme="dark")
help_mgr.add_section(HelpSection(
    title="Navigation",
    accent="blue",
    bindings=[
        KeyBinding("h",          "Show this help window"),
        KeyBinding("q / Escape", "Close figure"),
        KeyBinding("← → ↑ ↓",   "Pan the active axes"),
    ],
    note="Click a subplot first to make it active.",
))
help_mgr.attach()

plt.show()
```

> **Important:** keep a reference to the `HelpManager` alive (here: `help_mgr`) for
> the duration of `plt.show()`. matplotlib's callback registry uses weak references,
> so if the manager is garbage-collected the keypress handler silently stops working.
> If `attach()` happens in a function that returns before `plt.show()` is called,
> return the manager from that function and hold onto it at the call site.

### Config-file API

```python
from mpl_help import load_manager

help_mgr = load_manager(fig, "my_app_help.yaml")
help_mgr.attach()
plt.show()
```

`load_manager` auto-detects the format from the file extension. The equivalent
in-process variants are also available:

```python
from mpl_help import loads_manager, manager_from_dict

help_mgr = loads_manager(fig, yaml_text, fmt="yaml")
help_mgr = manager_from_dict(fig, config_dict)
```

---

## Config file format

A minimal YAML config:

```yaml
title: My App — Keyboard Shortcuts

sections:
  - title: Navigation
    accent: blue
    bindings:
      - key: h
        desc: Show this help window
      - key: "q / Escape"
        desc: Close figure
    note: Optional callout text shown below the bindings.
```

Top-level keys:

| Key | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | `"Keyboard Shortcuts"` | Heading shown in the help window |
| `trigger_key` | `str` | `"h"` | Key that opens / closes the help window |
| `footer` | `str` | auto | Small note at the bottom of the window |
| `key_column` | `float` | `0.24` | Right edge of the key badge column, as a fraction of figure width |
| `sections` | `list` | — | Ordered list of section blocks (required) |

Section keys:

| Key | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | — | Section heading (required) |
| `accent` | `str` | `"purple"` | Named palette colour or hex string |
| `bindings` | `list` | — | List of `{key, desc}` pairs (required) |
| `note` | `str` | none | Optional explanatory text below the bindings |

The config file deliberately has **no theme or per-colour content** — those are
presentation concerns, set at load time (see [Themes and palettes](#themes-and-palettes)
below), so the same config file works correctly under both themes.

See [`examples/example_help.yaml`](examples/example_help.yaml) for a fully
annotated template, and [`examples/imview_help.yaml`](examples/imview_help.yaml) /
[`examples/volview_help.yaml`](examples/volview_help.yaml) for real-world
examples with a wider key column for mouse-event descriptions.

### Supported formats

| Format | Extra dependency |
|---|---|
| YAML (`.yaml` / `.yml`) | `pip install mpl-help[yaml]` |
| TOML (`.toml`) | stdlib on Python ≥ 3.11; `pip install mpl-help[toml]` on older Pythons |
| JSON (`.json`) | none — always available |

The same content can also be supplied directly as a Python dict — see
[`examples/imview_help_dict.py`](examples/imview_help_dict.py) for an example.

---

## Themes and palettes

Two built-in themes are available: `"dark"` (default) and `"light"`. Pass
`theme=` to `HelpManager` or to any of the loader functions:

```python
HelpManager(fig, theme="light")
load_manager(fig, "my_app_help.yaml", theme="light")
```

Named accent colours (`blue`, `green`, `orange`, …) resolve to *different* hex
values depending on the active theme — deeper, more saturated tones on light
backgrounds and brighter tones on dark backgrounds — both chosen for
legibility. The config file only ever specifies the colour *name*; the
resolved value is purely a function of the active theme at render time.

| Name | Light hex | Dark hex |
|---|---|---|
| `blue`   | `#0969da` | `#58a6ff` |
| `purple` | `#8250df` | `#bc8cff` |
| `green`  | `#1a7f37` | `#3fb950` |
| `yellow` | `#9a6700` | `#d29922` |
| `orange` | `#bc4c00` | `#ffa657` |
| `red`    | `#cf222e` | `#f85149` |
| `cyan`   | `#1b7c83` | `#39c5cf` |

Any CSS hex colour (`"#f0a040"`) is also accepted as an accent and is used
as-is in both themes.

### Overriding individual colours

Pass a `palette` dict to override any entry in `DEFAULT_PALETTE`, structural
or accent. Each value is a `(light_hex, dark_hex)` tuple:

```python
from mpl_help import HelpManager, DEFAULT_PALETTE

print(DEFAULT_PALETTE.keys())
# dict_keys(['bg', 'surface', 'panel', 'border', 'text', 'muted',
#            'key_bg', 'key_fg', 'note_fg', 'note_bg', 'note_border',
#            'alt_row', 'top_bar', 'blue', 'purple', 'green',
#            'yellow', 'orange', 'red', 'cyan'])

help_mgr = HelpManager(
    fig,
    theme="light",
    palette={
        "blue": ("#1a5fb4", "#6ab0f5"),   # (light_hex, dark_hex)
        "bg":   ("#fafafa", "#0a0d12"),
    },
)
```

Unknown palette keys are silently ignored. `palette` is a presentation
argument like `theme` — it is never read from the config file.

---

## Key column width

Short keyboard shortcuts (`h`, `q / Escape`) fit comfortably in the default
key column. Longer descriptions of mouse interactions — e.g.
`"Mouse wheel (colorbar bottom half)"` — need more room and will be clipped
or overflow the left margin at the default width. Widen the column with
`key_column` (a fraction of figure width, default `0.24`):

```python
load_manager(fig, "my_app_help.yaml", key_column=0.45)
```

`key_column` can also be set directly in the config file:

```yaml
key_column: 0.45
```

A programmatic `key_column=` argument always overrides a value present in
the config file.

---

## Examples

The [`examples/`](examples) directory includes:

- [`demo.py`](examples/demo.py) — exercises all three config-loading routes
  (file / string / dict) and both themes. Can be run from any directory:
  ```bash
  python examples/demo.py file --theme light
  python examples/demo.py string --theme dark
  python examples/demo.py dict --theme light
  ```
- [`example_help.yaml`](examples/example_help.yaml) /
  [`example_help.toml`](examples/example_help.toml) — fully annotated config
  templates covering every option
- [`imview_help.yaml`](examples/imview_help.yaml),
  [`imview_help.toml`](examples/imview_help.toml),
  [`imview_help_dict.py`](examples/imview_help_dict.py) — real-world config
  for an image-viewing function, in all three supported formats
- [`volview_help.yaml`](examples/volview_help.yaml),
  [`volview_help.toml`](examples/volview_help.toml),
  [`volview_help_dict.py`](examples/volview_help_dict.py) — same, extended
  with volume-slice controls

---

## API reference

### `HelpManager(fig, title, trigger_key, footer, theme, palette, key_column)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `fig` | `Figure` | — | The matplotlib figure to monitor |
| `title` | `str` | `"Keyboard Shortcuts"` | Heading in the help window |
| `trigger_key` | `str` | `"h"` | Key that opens / closes the help window |
| `footer` | `str \| None` | auto | Note at the bottom of the window |
| `theme` | `str` | `"dark"` | `"dark"` or `"light"` |
| `palette` | `dict \| None` | `None` | Per-instance palette overrides |
| `key_column` | `float` | `0.24` | Right edge of key badge column (figure-width fraction) |

**Methods:**

- `.add_section(section)` — append a `HelpSection`; chainable
- `.attach()` — start listening for the trigger key on `fig`
- `.detach()` — stop listening and close the help window if open
- `.show()` — open the help window programmatically

### `HelpSection(title, bindings, note, accent)`

A titled group of key bindings. `accent` accepts a named palette colour, a
hex string, or `None` (defaults to `"purple"`).

### `KeyBinding(key, description)`

A single key/description pair.

### `load_manager(fig, path, theme="dark", palette=None, key_column=None, encoding="utf-8")`
Builds a `HelpManager` from a config file. Format auto-detected from extension.

### `loads_manager(fig, text, fmt, theme="dark", palette=None, key_column=None)`
Builds a `HelpManager` by parsing a config string. `fmt` is `"yaml"`, `"toml"`, or `"json"`.

### `manager_from_dict(fig, config, theme="dark", palette=None, key_column=None)`
Builds a `HelpManager` directly from a Python dict.

### `DEFAULT_PALETTE`
Dict of `{name: (light_hex, dark_hex)}` — the built-in colour set. Pass a
subset to `palette=` to override individual entries.

### `ACCENT_NAMES`
The set of valid named accent colours: `blue`, `purple`, `green`, `yellow`,
`orange`, `red`, `cyan`.

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

---

## Acknowledgements

Development of this package involved extensive use if Claude Sonnet 4.6
(Anthropic).
