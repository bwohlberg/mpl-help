# mpl-help

Backend-independent help windows for [matplotlib](https://matplotlib.org) figures.

Press a configurable trigger key (default **h**) inside any matplotlib figure to
open a styled help panel listing your application's keyboard shortcuts.

- **No external GUI toolkit** — the help window is itself a matplotlib figure
- **Config-file driven** — define shortcuts in YAML, TOML, or JSON; no code changes needed per figure type
- **Per-section accent colours** — named palette or arbitrary hex
- **Works with any matplotlib backend** — TkAgg, Qt5Agg, Qt6Agg, WxAgg, …

---

## Installation

### Local (editable) install

```bash
git clone https://github.com/yourname/mpl-help
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

help_mgr = HelpManager(fig, title="My App — Help")
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

### Config-file API

```python
from mpl_help import load_manager

help_mgr = load_manager(fig, "my_app_help.yaml")
help_mgr.attach()
plt.show()
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

See [`examples/example_help.yaml`](examples/example_help.yaml) for a fully
annotated template covering all options.

### Accent colours

Named colours from the built-in palette:

| Name | Hex | Typical use |
|---|---|---|
| `blue`   | `#58a6ff` | primary actions |
| `purple` | `#bc8cff` | default |
| `green`  | `#3fb950` | safe / confirm |
| `cyan`   | `#39c5cf` | tools / modes |
| `orange` | `#ffa657` | export / file |
| `yellow` | `#d29922` | caution |
| `red`    | `#f85149` | warnings / experimental |
| `muted`  | `#8b949e` | de-emphasis |

Any CSS hex colour (`"#f0a040"`) is also accepted.

### Supported formats

| Format | Extra dependency |
|---|---|
| YAML (`.yaml` / `.yml`) | `pip install mpl-help[yaml]` |
| TOML (`.toml`) | stdlib on Python ≥ 3.11; `pip install mpl-help[toml]` on older Pythons |
| JSON (`.json`) | none — always available |

---

## API reference

### `HelpManager(fig, title, trigger_key, footer)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `fig` | `Figure` | — | The matplotlib figure to monitor |
| `title` | `str` | `"Keyboard Shortcuts"` | Heading in the help window |
| `trigger_key` | `str` | `"h"` | Key that opens the help window |
| `footer` | `str \| None` | auto | Note at the bottom of the window |

**Methods:** `.add_section(section)`, `.attach()`, `.detach()`, `.show()`

### `HelpSection(title, bindings, note, accent)`

### `KeyBinding(key, description)`

### `load_manager(fig, path, encoding)`
Auto-detects format from file extension.

### `loads_manager(fig, text, fmt)`
Parses a config string; `fmt` is `"yaml"`, `"toml"`, or `"json"`.

### `manager_from_dict(fig, config)`
Builds directly from a Python dict.

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

---

## Changelog

### 0.1.0 (2026-05-15)
- Initial release
- Figure-based help window with per-section accent colours
- YAML, TOML, and JSON config file support
