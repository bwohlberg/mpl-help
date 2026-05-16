"""
matplotlib_help_config.py
=========================
Format-agnostic configuration loader for the matplotlib help system.

Supported formats
-----------------
YAML  (.yaml / .yml)   requires  PyYAML  (``pip install pyyaml``)
TOML  (.toml)          stdlib ``tomllib`` (Python ≥ 3.11) or
                       ``tomli``  (``pip install tomli``)  for older Pythons
JSON  (.json)          stdlib ``json`` — always available, zero extra deps

Loading
-------
From a file (format auto-detected from extension)::

    from matplotlib_help_config import load_manager
    help_mgr = load_manager(fig, "my_app_help.yaml")
    help_mgr.attach()

From an in-process string (format must be stated)::

    from matplotlib_help_config import loads_manager
    help_mgr = loads_manager(fig, yaml_text, fmt="yaml")
    help_mgr.attach()

From a dict already in memory::

    from matplotlib_help_config import manager_from_dict
    help_mgr = manager_from_dict(fig, config_dict)
    help_mgr.attach()

Backends
--------
Pass ``backend="figure"`` (default), ``"html"``, or ``"tkinter"``
to select which HelpManager implementation is used.

Config schema
-------------
See ``example_help.yaml`` for a fully annotated example.  The minimum
valid config is::

    title: My App Help
    sections:
      - title: General
        bindings:
          - key: h
            desc: Show this help window

Top-level keys
~~~~~~~~~~~~~~
title       str   Window / page heading.
trigger_key str   Key that opens the help window  (default: "h").
footer      str   Small note at the bottom        (default: auto).
sections    list  Ordered list of section blocks  (required).

Section keys
~~~~~~~~~~~~
title    str   Section heading text  (required).
accent   str   Accent colour — hex (#rrggbb) or a palette name:
               blue | purple | green | yellow | orange | red | cyan | muted
               (default: "purple")
bindings list  List of {key, desc} pairs  (required).
note     str   Optional explanatory note shown below the bindings.

Binding keys
~~~~~~~~~~~~
key   str  Key label, e.g. "h", "Ctrl+Z", "q / Escape", "← → ↑ ↓"
desc  str  Human-readable description of the action.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Union


# ---------------------------------------------------------------------------
# Palette name → hex  (mirrors the palette in matplotlib_help_figure.py)
# ---------------------------------------------------------------------------
NAMED_COLOURS: Dict[str, str] = {
    "blue":   "#58a6ff",
    "purple": "#bc8cff",
    "green":  "#3fb950",
    "yellow": "#d29922",
    "orange": "#ffa657",
    "red":    "#f85149",
    "cyan":   "#39c5cf",
    "muted":  "#8b949e",
}

Backend = Literal["figure"]


# ---------------------------------------------------------------------------
# Format parsers
# ---------------------------------------------------------------------------

def _parse_yaml(text: str) -> dict:
    try:
        import yaml  # PyYAML
    except ImportError as exc:
        raise ImportError(
            "PyYAML is required for YAML config files.\n"
            "Install it with:  pip install pyyaml"
        ) from exc
    return yaml.safe_load(text)


def _parse_toml(text: str) -> dict:
    # tomllib is stdlib in Python 3.11+; fall back to tomli for older versions.
    if sys.version_info >= (3, 11):
        import tomllib
        return tomllib.loads(text)
    try:
        import tomli
        return tomli.loads(text)
    except ImportError as exc:
        raise ImportError(
            "TOML support on Python < 3.11 requires the 'tomli' package.\n"
            "Install it with:  pip install tomli"
        ) from exc


def _parse_json(text: str) -> dict:
    return json.loads(text)


_PARSERS = {
    "yaml": _parse_yaml,
    "yml":  _parse_yaml,
    "toml": _parse_toml,
    "json": _parse_json,
}


# ---------------------------------------------------------------------------
# Colour resolver
# ---------------------------------------------------------------------------

def resolve_colour(value: Optional[str]) -> Optional[str]:
    """Return a hex colour string from a palette name or pass hex through."""
    if value is None:
        return None
    lower = value.strip().lower()
    return NAMED_COLOURS.get(lower, value)   # unknown names pass through as-is


# ---------------------------------------------------------------------------
# dict → data objects
# ---------------------------------------------------------------------------

def _import_backend(backend: Backend):
    """Import and return (HelpManager, HelpSection, KeyBinding) for backend."""
    if backend == "figure":
        from mpl_help._figure import HelpManager, HelpSection, KeyBinding
    elif backend == "html":
        raise ValueError(
            "The 'html' backend is not included in mpl-help. "
            "Use backend='figure' (the default)."
        )
    elif backend == "tkinter":
        raise ValueError(
            "The 'tkinter' backend is not included in mpl-help. "
            "Use backend='figure' (the default)."
        )
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. "
            "Choose 'figure', 'html', or 'tkinter'."
        )
    return HelpManager, HelpSection, KeyBinding


def manager_from_dict(
    fig,
    config: Dict[str, Any],
    backend: Backend = "figure",
):
    """
    Build a :class:`HelpManager` from a plain Python dict.

    This is the core builder; the other load helpers all call it after
    parsing their respective formats.

    Parameters
    ----------
    fig :
        The matplotlib Figure to attach to.
    config :
        Parsed configuration dictionary (see module docstring for schema).
    backend :
        Which rendering backend to use: ``"figure"`` (default),
        ``"html"``, or ``"tkinter"``.

    Returns
    -------
    HelpManager
        Fully configured manager, *not yet attached*.  Call ``.attach()``
        to start listening for the trigger key.
    """
    HelpManager, HelpSection, KeyBinding = _import_backend(backend)

    title       = config.get("title", "Keyboard Shortcuts")
    trigger_key = config.get("trigger_key", "h")
    footer      = config.get("footer", None)

    mgr = HelpManager(fig, title=title, trigger_key=trigger_key, footer=footer)

    for sec_raw in config.get("sections", []):
        bindings = [
            KeyBinding(
                key         = str(b.get("key", "")),
                description = str(b.get("desc", b.get("description", ""))),
            )
            for b in sec_raw.get("bindings", [])
        ]
        accent = resolve_colour(sec_raw.get("accent"))

        # Build kwargs — only pass accent if the dataclass accepts it
        # (figure backend does; html/tkinter don't use it yet)
        import inspect
        sig = inspect.signature(HelpSection.__init__)
        kw: Dict[str, Any] = dict(
            title    = sec_raw.get("title", ""),
            bindings = bindings,
            note     = sec_raw.get("note") or None,
        )
        if "accent" in sig.parameters:
            kw["accent"] = accent

        mgr.add_section(HelpSection(**kw))

    return mgr


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

def loads_manager(
    fig,
    text: str,
    fmt: str,
    backend: Backend = "figure",
):
    """
    Build a HelpManager by parsing *text* as the given format.

    Parameters
    ----------
    fig :
        The matplotlib Figure to attach to.
    text :
        Raw config text (YAML, TOML, or JSON string).
    fmt :
        ``"yaml"`` / ``"yml"``, ``"toml"``, or ``"json"``.
    backend :
        Rendering backend (``"figure"`` / ``"html"`` / ``"tkinter"``).
    """
    fmt = fmt.lower().lstrip(".")
    parser = _PARSERS.get(fmt)
    if parser is None:
        raise ValueError(
            f"Unsupported format {fmt!r}. "
            f"Choose from: {', '.join(_PARSERS)}"
        )
    config = parser(text)
    return manager_from_dict(fig, config, backend=backend)


def load_manager(
    fig,
    path: Union[str, Path],
    backend: Backend = "figure",
    encoding: str = "utf-8",
):
    """
    Build a HelpManager by reading a config file from disk.

    The format is auto-detected from the file extension
    (``.yaml``/``.yml``, ``.toml``, ``.json``).

    Parameters
    ----------
    fig :
        The matplotlib Figure to attach to.
    path :
        Path to the config file.
    backend :
        Rendering backend (``"figure"`` / ``"html"`` / ``"tkinter"``).
    encoding :
        File encoding (default ``"utf-8"``).
    """
    path = Path(path)
    suffix = path.suffix.lstrip(".").lower()
    if suffix not in _PARSERS:
        raise ValueError(
            f"Cannot infer format from extension {path.suffix!r}. "
            f"Supported: {', '.join(f'.{k}' for k in _PARSERS)}"
        )
    text = path.read_text(encoding=encoding)
    return loads_manager(fig, text, fmt=suffix, backend=backend)
