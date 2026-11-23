# -*- coding: utf-8 -*-
# Copyright (C) 2026 by Brendt Wohlberg <brendt@ieee.org>
# All rights reserved. BSD 3-clause License.
# This file is part of the mpl-help package. Details of the copyright
# and user license can be found in the 'LICENSE.txt' file distributed
# with the package.

"""
mpl_help._config
================
Format-agnostic configuration loader for mpl-help.

Supported formats
-----------------
YAML  (.yaml / .yml)   requires  PyYAML  (``pip install pyyaml``)
TOML  (.toml)          stdlib ``tomllib`` — always available
JSON  (.json)          stdlib ``json`` — always available

The theme and palette are presentation concerns and are therefore
*not* part of the config file format.  Pass them as arguments to
the loader functions or directly to :class:`~mpl_help.HelpManager`.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Format parsers
# ---------------------------------------------------------------------------


def _parse_yaml(text: str) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise ImportError(
            "PyYAML is required for YAML config files.\n"
            "Install it with:  pip install 'mpl-help[yaml]'"
        ) from exc
    return yaml.safe_load(text)


def _parse_toml(text: str) -> dict:
    return tomllib.loads(text)


def _parse_json(text: str) -> dict:
    return json.loads(text)


_PARSERS = {
    "yaml": _parse_yaml,
    "yml": _parse_yaml,
    "toml": _parse_toml,
    "json": _parse_json,
}


# ---------------------------------------------------------------------------
# dict → HelpManager
# ---------------------------------------------------------------------------


def manager_from_dict(
    fig,
    config: dict[str, Any],
    theme: str = "dark",
    palette: dict[str, tuple[str, str]] | None = None,
    key_column: float | None = None,
):
    """
    Build a :class:`~mpl_help.HelpManager` from a plain Python dict.

    Parameters
    ----------
    fig :
        The matplotlib Figure to attach to.
    config :
        Parsed configuration dictionary.
    theme :
        ``"dark"`` (default) or ``"light"``.
    palette :
        Optional palette overrides — ``{name: (light_hex, dark_hex)}``.
        See :data:`~mpl_help.DEFAULT_PALETTE` for valid key names.
    key_column :
        Right edge of the key badge column as a fraction of figure width
        (e.g. ``0.24`` for short keyboard labels, ``0.45`` for longer
        mouse-event descriptions).  Overrides any value in *config*.
        If ``None``, the value from *config* is used, falling back to
        the package default (``0.24``).
    """
    from mpl_help._figure import _DEFAULT_KEY_COL, HelpManager, HelpSection, KeyBinding

    title = config.get("title", "Keyboard Shortcuts")
    trigger_key = config.get("trigger_key", "h")
    footer = config.get("footer") or None

    # key_column: programmatic argument takes priority, then config file, then default
    if key_column is None:
        key_column = float(config.get("key_column", _DEFAULT_KEY_COL))

    mgr = HelpManager(
        fig,
        title=title,
        trigger_key=trigger_key,
        footer=footer,
        theme=theme,
        palette=palette,
        key_column=key_column,
    )

    for sec_raw in config.get("sections", []):
        bindings = [
            KeyBinding(
                key=str(b.get("key", "")),
                description=str(b.get("desc", b.get("description", ""))),
            )
            for b in sec_raw.get("bindings", [])
        ]
        # Store accent as-is (name or hex); resolution happens at render time.
        accent = sec_raw.get("accent") or None

        mgr.add_section(
            HelpSection(
                title=sec_raw.get("title", ""),
                bindings=bindings,
                note=sec_raw.get("note") or None,
                accent=accent,
            )
        )

    return mgr


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def loads_manager(
    fig,
    text: str,
    fmt: str,
    theme: str = "dark",
    palette: dict[str, tuple[str, str]] | None = None,
    key_column: float | None = None,
):
    """
    Build a :class:`~mpl_help.HelpManager` by parsing *text*.

    Parameters
    ----------
    fig :
        The matplotlib Figure to attach to.
    text :
        Raw config text (YAML, TOML, or JSON string).
    fmt :
        ``"yaml"`` / ``"yml"``, ``"toml"``, or ``"json"``.
    theme :
        ``"dark"`` (default) or ``"light"``.
    palette :
        Optional palette overrides.
    key_column :
        Right edge of key badge column as a fraction of figure width.
        Overrides any value in the config text.
    """
    fmt = fmt.lower().lstrip(".")
    parser = _PARSERS.get(fmt)
    if parser is None:
        raise ValueError(
            f"Unsupported format {fmt!r}. " f"Choose from: {', '.join(_PARSERS)}"
        )
    return manager_from_dict(
        fig, parser(text), theme=theme, palette=palette, key_column=key_column
    )


def load_manager(
    fig,
    path: str | Path,
    theme: str = "dark",
    palette: dict[str, tuple[str, str]] | None = None,
    key_column: float | None = None,
    encoding: str = "utf-8",
):
    """
    Build a :class:`~mpl_help.HelpManager` from a config file.

    The format is auto-detected from the file extension
    (``.yaml``/``.yml``, ``.toml``, ``.json``).

    Parameters
    ----------
    fig :
        The matplotlib Figure to attach to.
    path :
        Path to the config file.
    theme :
        ``"dark"`` (default) or ``"light"``.
    palette :
        Optional palette overrides.
    key_column :
        Right edge of key badge column as a fraction of figure width.
        Overrides any value in the config file.
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
    return loads_manager(
        fig, text, fmt=suffix, theme=theme, palette=palette, key_column=key_column
    )
