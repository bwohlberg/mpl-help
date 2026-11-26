# -*- coding: utf-8 -*-
# Copyright (C) 2026 by Brendt Wohlberg <brendt@ieee.org>
# All rights reserved. BSD 3-clause License.
# This file is part of the mpl-help package. Details of the copyright
# and user license can be found in the 'LICENSE.txt' file distributed
# with the package.

"""
mpl_help._figure
================
Core renderer for the mpl-help figure-based help window.

All colours are resolved through a two-theme palette system.
See :data:`DEFAULT_PALETTE` for the built-in colour definitions and
:class:`HelpManager` for how to supply per-instance overrides.
"""

from __future__ import annotations

import functools
import itertools
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

# ---------------------------------------------------------------------------
# Row-height constants  (in row-units)
# ---------------------------------------------------------------------------
_ROW_H_IN = 0.32  # inches per row unit
_PAD_TOP = 2.2  # rows reserved for header
_PAD_BOT = 0.9  # rows reserved for footer
_SECTION_HDR = 1.3  # rows per section title bar
_BINDING_ROW = 1.0  # rows per key-binding line
_NOTE_ROW = 0.85  # rows for an optional note
_SECTION_GAP = 0.45  # gap between sections
_FIG_WIDTH_IN = 7.2  # fixed figure width in inches
# Default trigger key.  '?' is used rather than 'h' because matplotlib binds
# 'h' to keymap.home, which resets the view of the figure being helped.
_DEFAULT_TRIGGER_KEY = "?"
_DEFAULT_KEY_COL = 0.24  # default minimum right edge of key badge column
_KEY_COL_MAX = 0.60  # key badge column is not widened beyond this
_KEY_COL_GAP = 0.03  # fixed gap between key badge and description text
_NOTE_LINE = 0.42  # extra rows per wrapped note line
_BINDING_LINE = 0.46  # extra rows per wrapped description line
_PANEL_LEFT = 0.03  # left edge of the section panel (fraction of axes width)
_PANEL_RIGHT = 0.97  # right edge of the section panel (fraction of axes width)
_NOTE_LEFT = 0.08  # left edge of note text
_NOTE_RIGHT = 0.95  # right limit of note text
_NOTE_BOX_PAD = 0.05  # vertical margin of a note box, in rows
_NOTE_BOX_ROUND = 0.015  # corner rounding of a note box
_NOTE_FONTSIZE = 7.5
_BINDING_FONTSIZE = 8.5
_KEY_FONTSIZE = 8
_KEY_BADGE_PAD = 0.28  # key badge padding, in units of its font size
_WRAP_MARGIN = 0.98  # safety factor applied to measured text widths

# ---------------------------------------------------------------------------
# Palette  {name: (light_hex, dark_hex)}
# ---------------------------------------------------------------------------
# Index 0 = light theme, index 1 = dark theme.
#
# Structural colours (bg, surface, …) differ significantly between themes.
# Named accent colours use darker, more saturated values on light backgrounds
# and lighter, brighter values on dark backgrounds — both chosen for legibility.
#
# Users may override any entry via the ``palette`` argument to HelpManager.

DEFAULT_PALETTE: dict[str, tuple[str, str]] = {
    # ── structural ──────────────────────────── light        dark
    "bg": ("#ffffff", "#0d1117"),
    "surface": ("#f6f8fa", "#161b22"),
    "panel": ("#eaeef2", "#21262d"),
    "border": ("#d0d7de", "#30363d"),
    "text": ("#1f2328", "#e6edf3"),
    "muted": ("#656d76", "#8b949e"),
    "key_bg": ("#eaeef2", "#1c2128"),
    "key_fg": ("#953800", "#ffa657"),
    "note_fg": ("#1a7f37", "#3fb950"),
    "note_bg": ("#dafbe1", "#0f2a0f"),
    "note_border": ("#82cfaa", "#2ea043"),
    "alt_row": ("#f0f2f5", "#12171e"),
    "top_bar": ("#0969da", "#58a6ff"),
    # ── named accent colours ─────────────────── light        dark
    "blue": ("#0969da", "#58a6ff"),
    "purple": ("#8250df", "#bc8cff"),
    "green": ("#1a7f37", "#3fb950"),
    "yellow": ("#9a6700", "#d29922"),
    "orange": ("#bc4c00", "#ffa657"),
    "red": ("#cf222e", "#f85149"),
    "cyan": ("#1b7c83", "#39c5cf"),
}

#: The set of valid named accent colours accepted by config files and
#: :class:`HelpSection`.
ACCENT_NAMES = frozenset("blue purple green yellow orange red cyan".split())

_THEME_IDX: dict[str, int] = {"light": 0, "dark": 1}

# Serial number source for per-instance help figure labels.
_HELP_FIG_COUNTER = itertools.count()


# ---------------------------------------------------------------------------
# Palette helpers
# ---------------------------------------------------------------------------


def _make_colour_map(
    theme: str,
    overrides: dict[str, tuple[str, str]] | None = None,
) -> dict[str, str]:
    """
    Return a flat ``{name: hex}`` colour map for *theme*, applying any
    user-supplied *overrides* on top of :data:`DEFAULT_PALETTE`.

    Parameters
    ----------
    theme :
        ``"dark"`` or ``"light"``.
    overrides :
        Optional dict mapping palette names to ``(light_hex, dark_hex)``
        tuples.  Unknown keys are silently ignored.
    """
    if theme not in _THEME_IDX:
        raise ValueError(f"Unknown theme {theme!r}. Choose 'dark' or 'light'.")
    idx = _THEME_IDX[theme]
    colours = {name: pair[idx] for name, pair in DEFAULT_PALETTE.items()}
    if overrides:
        for name, pair in overrides.items():
            if name in DEFAULT_PALETTE:
                colours[name] = pair[idx]
            # silently ignore unknown keys
    return colours


def _validate_palette(palette: dict[str, tuple[str, str]] | None) -> None:
    """
    Check that *palette* maps names to pairs of valid colours.

    Unknown names are not rejected, matching the documented behaviour that
    they are ignored, but malformed or invalid colour values are, so that
    they are reported here rather than when the window is first opened.
    """
    if not palette:
        return
    for name, pair in palette.items():
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError(
                f"Palette entry {name!r} must be a (light_hex, dark_hex) tuple, "
                f"got {pair!r}."
            )
        for colour in pair:
            if not mcolors.is_color_like(colour):
                raise ValueError(
                    f"Palette entry {name!r} contains invalid colour {colour!r}."
                )


def _resolve_accent(
    name_or_hex: str | None,
    colours: dict[str, str],
) -> str:
    """
    Resolve a section accent value to a hex string.

    * ``None``          → default accent (``"purple"`` palette entry)
    * ``"#rrggbb"``     → returned as-is (user opted out of theme support)
    * palette name      → resolved via *colours* map
    * unknown string    → returned as-is (treated as a literal hex)
    """
    if name_or_hex is None:
        return colours["purple"]
    if name_or_hex.startswith("#"):
        return name_or_hex
    return colours.get(name_or_hex, name_or_hex)


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass
class KeyBinding:
    """A single key → description pair."""

    key: str
    description: str


@dataclass
class HelpSection:
    """A titled group of key bindings with an optional note.

    Parameters
    ----------
    title :
        Section heading text.
    bindings :
        List of :class:`KeyBinding` objects.
    note :
        Optional explanatory note shown below the bindings.
    accent :
        Accent colour for this section's title bar and left stripe.
        Accepts a named palette colour (``"blue"``, ``"green"``, …),
        a hex string (``"#rrggbb"``), or ``None`` for the default
        (``"purple"``).  Named colours resolve per the active theme;
        raw hex strings are used as-is in both themes.
    """

    title: str
    bindings: list[KeyBinding] = field(default_factory=list)
    note: str | None = None
    accent: str | None = None

    def __post_init__(self) -> None:
        if (
            self.accent is not None
            and self.accent not in DEFAULT_PALETTE
            and not mcolors.is_color_like(self.accent)
        ):
            raise ValueError(
                f"Unknown accent {self.accent!r}. Use a palette name "
                f"({', '.join(sorted(ACCENT_NAMES))}) or a colour such as "
                f"'#rrggbb'."
            )


# ---------------------------------------------------------------------------
# Internal layout helpers
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _measuring_canvas() -> FigureCanvasAgg:
    """An off-screen canvas on which text is measured before it is drawn.

    Its figure is of the width of a help window, and is not managed by
    pyplot, so that measuring disturbs neither the figures of the
    application nor the state of pyplot. The canvas is returned rather
    than the figure because the renderer that measures the text belongs
    to it.
    """
    # A fixed dpi, rather than the rcParams value at the moment of the first
    # measurement, so that the measurements of a session are consistent with
    # each other however the configuration changes within it
    figure = Figure(figsize=(_FIG_WIDTH_IN, 1.0), dpi=100.0)
    return FigureCanvasAgg(figure)


# The fonts in which the text of each kind is drawn, so that it is measured
# as it is drawn: a key badge in particular is in a bold monospace font,
# which is wider than the default font at the same size.
_NOTE_FONT = FontProperties(size=_NOTE_FONTSIZE)
_BINDING_FONT = FontProperties(size=_BINDING_FONTSIZE)
_KEY_FONT = FontProperties(size=_KEY_FONTSIZE, family="monospace", weight="bold")
_KEY_PAD = _KEY_BADGE_PAD * _KEY_FONTSIZE / 72.0 / _FIG_WIDTH_IN  # as a fraction


@functools.lru_cache(maxsize=2048)
def _text_width(text: str, font: FontProperties) -> float:
    """
    Width of *text* in *font*, as a fraction of the figure width.

    The layout is computed before the figure that it describes exists, so
    the text is measured in an off-screen figure of the same width, with
    the renderer that will draw it rather than from the font metrics
    alone: the two do not agree, and by a margin that depends on the
    version of matplotlib, so that a layout computed from the metrics
    leaves text wider than the space allowed for it. The measurement is
    cached, since wrapping measures each line of text once per word.
    """
    canvas = _measuring_canvas()
    artist = canvas.figure.text(0.0, 0.0, text, fontproperties=font)
    extent = artist.get_window_extent(canvas.get_renderer())
    artist.remove()
    return extent.width / canvas.figure.bbox.width


def _wrap(
    text: str,
    font: FontProperties,
    width: float,
    initial_indent: str = "",
    subsequent_indent: str = "",
) -> list[str]:
    """
    Wrap *text* at word boundaries to lines no wider than *width*.

    Parameters
    ----------
    text :
        The text to wrap.
    font :
        The font in which the text is drawn.
    width :
        Available width as a fraction of the figure width.
    initial_indent, subsequent_indent :
        Prefixes for the first and for the remaining lines.  They are
        included in the returned lines and in the width measurement.
    """
    limit = width * _WRAP_MARGIN
    words = text.split()
    if not words:
        return [initial_indent]
    lines: list[str] = []
    indent = initial_indent
    current = ""
    for word in words:
        trial = f"{current} {word}" if current else word
        if current and _text_width(indent + trial, font) > limit:
            lines.append(indent + current)
            indent = subsequent_indent
            current = word
        else:
            current = trial
    lines.append(indent + current)
    return lines


def _description_lines(description: str, key_column: float) -> list[str]:
    """Wrap a binding description to the space right of the key badge."""
    return _wrap(
        description,
        _BINDING_FONT,
        _PANEL_RIGHT - (key_column + _KEY_COL_GAP),
    )


def _key_badge_width(key: str) -> float:
    """Width of the badge of *key* as a fraction of the figure width.

    The badge extends beyond its text by its padding on each side.
    """
    return _text_width(key, _KEY_FONT) + 2 * _KEY_PAD


def _key_lines(key: str, key_column: float) -> list[str]:
    """Wrap a key to the width of the badge column.

    Only a key too wide for the widest column that _fit_key_column will
    use is wrapped, since a key is usually short enough for the column to
    be fitted to it instead.
    """
    return _wrap(key, _KEY_FONT, key_column - _PANEL_LEFT - 2 * _KEY_PAD)


def _fit_key_column(sections: list[HelpSection], key_column: float) -> float:
    """Widen *key_column* as necessary to fit the widest key badge.

    The badges are right-aligned on the key column, so one wider than the
    column extends to the left of the section panel, and beyond the edge
    of the figure if it is wider still, which truncates it. The requested
    column is therefore a minimum, widened here to fit the widest badge,
    but not beyond _KEY_COL_MAX, which leaves the description column
    usable: a key too wide for that column is wrapped by _key_lines.
    """
    widest = max(
        (_key_badge_width(b.key) for s in sections for b in s.bindings),
        default=0.0,
    )
    # The widest badge is allowed the margin by which _wrap underestimates
    # the space available to it, so that a column fitted to a key does not
    # then wrap that key
    return min(max(key_column, _PANEL_LEFT + widest / _WRAP_MARGIN), _KEY_COL_MAX)


def _note_lines(note: str) -> list[str]:
    """Wrap a section note to the width of its box, keeping the info glyph."""
    return _wrap(
        note,
        _NOTE_FONT,
        _NOTE_RIGHT - _NOTE_LEFT,
        initial_indent="\u2139  ",
        subsequent_indent="   ",
    )


def _binding_height(binding: KeyBinding, key_column: float) -> float:
    """Row-units consumed by one key-binding row, including wrapped lines."""
    extra = (
        max(
            len(_description_lines(binding.description, key_column)),
            len(_key_lines(binding.key, key_column)),
        )
        - 1
    )
    return _BINDING_ROW + extra * _BINDING_LINE


def _note_height(note: str) -> float:
    """Row-units consumed by a section note, including wrapped lines."""
    return _NOTE_ROW + (len(_note_lines(note)) - 1) * _NOTE_LINE


def _section_height(
    section: HelpSection, key_column: float = _DEFAULT_KEY_COL
) -> float:
    """Total row-units consumed by one section (excluding trailing gap)."""
    h = _SECTION_HDR + sum(_binding_height(b, key_column) for b in section.bindings)
    if section.note:
        h += _note_height(section.note)
    return h


def _total_rows(
    sections: list[HelpSection], key_column: float = _DEFAULT_KEY_COL
) -> float:
    rows = _PAD_TOP + _PAD_BOT
    for i, s in enumerate(sections):
        rows += _section_height(s, key_column)
        if i < len(sections) - 1:
            rows += _SECTION_GAP
    return rows


# ---------------------------------------------------------------------------
# Figure renderer
# ---------------------------------------------------------------------------


def _build_help_figure(
    sections: list[HelpSection],
    title: str,
    footer: str,
    theme: str = "dark",
    palette_overrides: dict[str, tuple[str, str]] | None = None,
    key_column: float = _DEFAULT_KEY_COL,
    trigger_key: str = _DEFAULT_TRIGGER_KEY,
    num: str | None = None,
) -> mpl.figure.Figure:
    """
    Create and return the fully rendered help figure.

    *num* is the figure label: each :class:`HelpManager` passes its own, so
    that managers attached to different figures never share a help window.
    """

    C = _make_colour_map(theme, palette_overrides)

    # The requested key column is a minimum, widened to fit the key badges
    key_column = _fit_key_column(sections, key_column)

    n_rows = _total_rows(sections, key_column)
    fig_h = max(n_rows * _ROW_H_IN, 3.0)

    # rc_context, rather than assignment, so that a failure during figure
    # creation cannot leave the toolbar suppressed for the whole session.
    with mpl.rc_context({"toolbar": "None"}):
        fig = plt.figure(
            figsize=(_FIG_WIDTH_IN, fig_h),
            facecolor=C["bg"],
            num=num,
        )

    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, n_rows)
    ax.axis("off")
    ax.set_facecolor(C["bg"])

    # ── top accent bar ────────────────────────────────────────────────
    ax.add_patch(
        mpatches.FancyBboxPatch(
            (0, n_rows - 0.18),
            1,
            0.18,
            boxstyle="square,pad=0",
            facecolor=C["top_bar"],
            edgecolor="none",
            transform=ax.transData,
            clip_on=False,
            zorder=3,
        )
    )

    # ── header title ──────────────────────────────────────────────────
    ax.text(
        0.04,
        n_rows - 0.75,
        title,
        fontsize=13,
        fontweight="bold",
        color=C["text"],
        va="center",
        ha="left",
        transform=ax.transData,
    )
    ax.text(
        0.97,
        n_rows - 0.75,
        f"press  {trigger_key} / q / Esc  to close",
        fontsize=7,
        color=C["muted"],
        va="center",
        ha="right",
        transform=ax.transData,
    )
    ax.axhline(
        n_rows - _PAD_TOP + 0.22,
        xmin=_PANEL_LEFT,
        xmax=0.97,
        color=C["border"],
        linewidth=0.7,
        zorder=2,
    )

    # ── sections ──────────────────────────────────────────────────────
    y = n_rows - _PAD_TOP

    for i, section in enumerate(sections):
        if i:
            y -= _SECTION_GAP
        sec_h = _section_height(section, key_column)
        sec_accent = _resolve_accent(section.accent, C)

        # Section background panel
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (_PANEL_LEFT, y - sec_h),
                _PANEL_RIGHT - _PANEL_LEFT,
                sec_h,
                boxstyle="round,pad=0.0",
                facecolor=C["surface"],
                edgecolor=C["border"],
                linewidth=0.6,
                transform=ax.transData,
                zorder=1,
            )
        )

        # Section title bar background
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (_PANEL_LEFT, y - _SECTION_HDR),
                _PANEL_RIGHT - _PANEL_LEFT,
                _SECTION_HDR,
                boxstyle="square,pad=0",
                facecolor=C["panel"],
                edgecolor="none",
                transform=ax.transData,
                zorder=2,
            )
        )

        # Accent stripe on left edge
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (_PANEL_LEFT, y - _SECTION_HDR),
                0.004,
                _SECTION_HDR,
                boxstyle="square,pad=0",
                facecolor=sec_accent,
                edgecolor="none",
                transform=ax.transData,
                zorder=3,
            )
        )

        # Section title text
        ax.text(
            0.055,
            y - _SECTION_HDR / 2,
            "  ".join(section.title.upper()),
            fontsize=7.5,
            fontweight="bold",
            color=sec_accent,
            va="center",
            ha="left",
            transform=ax.transData,
            zorder=4,
        )

        y -= _SECTION_HDR

        # Key-binding rows
        for i, kb in enumerate(section.bindings):
            row_bg = C["alt_row"] if i % 2 == 0 else C["surface"]
            row_h = _binding_height(kb, key_column)
            row_mid = y - row_h / 2

            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (_PANEL_LEFT, y - row_h),
                    _PANEL_RIGHT - _PANEL_LEFT,
                    row_h,
                    boxstyle="square,pad=0",
                    facecolor=row_bg,
                    edgecolor="none",
                    transform=ax.transData,
                    zorder=2,
                )
            )
            ax.text(
                key_column,
                row_mid,
                "\n".join(_key_lines(kb.key, key_column)),
                fontsize=_KEY_FONTSIZE,
                fontweight="bold",
                fontfamily="monospace",
                color=C["key_fg"],
                va="center",
                ha="right",
                bbox=dict(
                    boxstyle="round,pad=0.28",
                    facecolor=C["key_bg"],
                    edgecolor=C["border"],
                    linewidth=0.6,
                ),
                transform=ax.transData,
                zorder=3,
            )
            ax.text(
                key_column + _KEY_COL_GAP,
                row_mid,
                "\n".join(_description_lines(kb.description, key_column)),
                fontsize=_BINDING_FONTSIZE,
                color=C["text"],
                va="center",
                ha="left",
                linespacing=1.3,
                transform=ax.transData,
                zorder=3,
            )
            y -= row_h

        # Optional note
        if section.note:
            note_h = _note_height(section.note)
            ax.add_patch(
                # The padding of a boxstyle is in data coordinates, which
                # span the figure width in x but the rows of the layout in
                # y, so a padding wide enough to be seen in y takes the box
                # outside the figure in x. The margins are therefore part of
                # the geometry of the box here, which aligns it with the
                # section panel that it belongs to.
                mpatches.FancyBboxPatch(
                    (_PANEL_LEFT, y - note_h + 0.08 - _NOTE_BOX_PAD),
                    _PANEL_RIGHT - _PANEL_LEFT,
                    note_h - 0.08 + 2 * _NOTE_BOX_PAD,
                    boxstyle=f"round,pad=0,rounding_size={_NOTE_BOX_ROUND}",
                    facecolor=C["note_bg"],
                    edgecolor=C["note_border"],
                    linewidth=0.5,
                    transform=ax.transData,
                    zorder=3,
                )
            )
            ax.text(
                _NOTE_LEFT,
                y - note_h / 2 + 0.04,
                "\n".join(_note_lines(section.note)),
                fontsize=_NOTE_FONTSIZE,
                color=C["note_fg"],
                va="center",
                ha="left",
                linespacing=1.3,
                transform=ax.transData,
                zorder=4,
            )
            y -= note_h

    # ── footer ────────────────────────────────────────────────────────
    ax.axhline(
        _PAD_BOT - 0.15,
        xmin=_PANEL_LEFT,
        xmax=0.97,
        color=C["border"],
        linewidth=0.7,
    )
    ax.text(
        0.04,
        _PAD_BOT / 2 - 0.1,
        footer,
        fontsize=7,
        color=C["muted"],
        va="center",
        ha="left",
        transform=ax.transData,
    )
    ax.text(
        0.97,
        _PAD_BOT / 2 - 0.1,
        "mpl-help",
        fontsize=7,
        color=C["muted"],
        va="center",
        ha="right",
        transform=ax.transData,
    )

    return fig


# ---------------------------------------------------------------------------
# Window utilities
# ---------------------------------------------------------------------------


def _disable_default_keymap(fig: mpl.figure.Figure) -> None:
    """
    Detach matplotlib's default key bindings from *fig*.

    The help figure is a rendered document, not a plot: leaving the default
    bindings connected lets keys such as ``l`` (log scale), ``s`` (save) and
    ``g`` (grid) act on the axes the help text is drawn in, destroying the
    layout.
    """
    manager = fig.canvas.manager
    cid = getattr(manager, "key_press_handler_id", None)
    if cid is not None:
        fig.canvas.mpl_disconnect(cid)


def _closing_all_figures() -> bool:
    """Report whether pyplot is in the middle of closing every figure.

    ``plt.close("all")`` and interpreter exit both destroy the figure
    managers held in a snapshot of pyplot's registry, taken before the
    loop and not updated as it goes.  A figure closed from a
    ``close_event`` handler raised inside that loop is therefore
    destroyed a second time when the loop reaches it, which the Tk
    backend reports as ``TclError: can't invoke "destroy" command``.
    matplotlib is already closing every figure in that case, so the help
    figure needs no help.

    pyplot exposes no flag for this, hence the stack inspection; a false
    negative merely restores the unguarded behaviour.
    """
    frame: Any = sys._getframe(1)
    while frame is not None:
        if (
            frame.f_code.co_name == "destroy_all"
            and frame.f_globals.get("__name__") == "matplotlib._pylab_helpers"
        ):
            return True
        frame = frame.f_back
    return False


def _raise_window(fig: mpl.figure.Figure) -> None:
    """Raise the window of ``fig`` above other windows, if supported.

    The window object and the method used to raise it are both
    backend-specific, and are entirely absent for non-interactive
    backends, so the request is silently ignored when the active backend
    provides no mechanism for it.
    """
    manager = fig.canvas.manager
    if manager is None:
        return
    window = getattr(manager, "window", None)
    raise_ = getattr(window, "raise_", None)
    if callable(raise_):
        raise_()


# ---------------------------------------------------------------------------
# HelpManager
# ---------------------------------------------------------------------------


class HelpManager:
    """
    Attach to a matplotlib Figure to show a help figure on keypress.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to monitor.
    title : str
        Heading displayed at the top of the help figure.
    trigger_key : str
        Key that opens / closes the help figure (default ``"?"``).
        Note that matplotlib binds some keys by default, including ``"h"``
        to ``keymap.home``, which resets the monitored figure's view; a
        trigger key that is also bound by matplotlib will do both.
    footer : str, optional
        Small note at the bottom of the help figure.
    theme : str
        Colour theme — ``"dark"`` (default) or ``"light"``.
    palette : dict, optional
        Per-instance palette overrides.  Supply a dict mapping palette
        key names to ``(light_hex, dark_hex)`` tuples, e.g.::

            palette = {
                "blue":   ("#1a6bc4", "#75b3ff"),
                "bg":     ("#f5f5f5", "#0a0e15"),
            }

        Any key present in :data:`DEFAULT_PALETTE` may be overridden.
        Unknown keys are silently ignored, but invalid colour values are
        rejected here rather than when the window is first opened.
    key_column : float
        Minimum right edge of the key badge column, as a fraction of the
        figure width.  Must lie strictly between 0 and 1.  The badges are
        right-aligned on the column, so a badge wider than the column
        would extend past the left edge of the figure; the column is
        therefore widened as necessary to fit the widest badge, up to 0.6
        of the figure width, beyond which a key is instead wrapped onto
        as many lines as it needs.
    close_with_figure : bool
        If ``True`` (default), close the help figure automatically when
        the monitored figure is closed.  Set to ``False`` to leave the
        help figure open, in which case it must be closed by the user
        or via :meth:`detach`.

    Notes
    -----
    Keep a reference to the manager alive for as long as the monitored
    figure is in use.  matplotlib's callback registry holds the keypress
    handler weakly, so a garbage-collected manager stops responding
    without any error being reported.
    """

    def __init__(
        self,
        fig: mpl.figure.Figure,
        title: str = "Keyboard Shortcuts",
        trigger_key: str = _DEFAULT_TRIGGER_KEY,
        footer: str | None = None,
        theme: str = "dark",
        palette: dict[str, tuple[str, str]] | None = None,
        key_column: float = _DEFAULT_KEY_COL,
        close_with_figure: bool = True,
    ) -> None:
        if theme not in _THEME_IDX:
            raise ValueError(f"Unknown theme {theme!r}. Choose 'dark' or 'light'.")
        if not 0.0 < key_column < 1.0:
            raise ValueError(
                f"key_column must lie strictly between 0 and 1, got {key_column!r}."
            )
        _validate_palette(palette)
        self._fig = fig
        self._title = title
        self._trigger_key = trigger_key
        self._footer = footer or f"press  {trigger_key}  to reopen"
        self._theme = theme
        self._palette = palette
        self._key_column = key_column
        self._close_with_figure = close_with_figure
        self._sections: list[HelpSection] = []
        self._cid: int | None = None
        self._close_cid: int | None = None
        self._help_fig: mpl.figure.Figure | None = None
        # Own figure label, so that managers on different figures do not
        # share, resize and close one another's help window.
        self._help_fig_num = f"__mpl_help_{next(_HELP_FIG_COUNTER)}__"

    # ── public API ────────────────────────────────────────────────────

    def add_section(self, section: HelpSection) -> "HelpManager":
        """Append a :class:`HelpSection` and return self (chainable)."""
        self._sections.append(section)
        return self

    def attach(self) -> "HelpManager":
        """Start listening for keypresses on the main figure canvas."""
        if self._cid is not None:
            return self
        self._cid = self._fig.canvas.mpl_connect("key_press_event", self._on_key_press)
        self._connect_close_hook()
        return self

    def detach(self) -> "HelpManager":
        """Stop listening and close the help figure if open."""
        if self._cid is not None:
            self._fig.canvas.mpl_disconnect(self._cid)
            self._cid = None
        if self._close_cid is not None:
            self._fig.canvas.mpl_disconnect(self._close_cid)
            self._close_cid = None
        self._close_help()
        return self

    def show(self) -> None:
        """Programmatically open the help figure."""
        self._open_help()

    # ── internals ─────────────────────────────────────────────────────

    def _on_key_press(self, event) -> None:
        if event.key == self._trigger_key:
            if self._help_is_open():
                self._close_help()
            else:
                self._open_help()

    def _connect_close_hook(self) -> None:
        """Arrange for the help figure to close with the monitored figure.

        Idempotent, and a no-op when ``close_with_figure`` is ``False``.
        Called from both :meth:`attach` and :meth:`_open_help`, so that a
        help figure opened by :meth:`show` alone is also covered.
        """
        if not self._close_with_figure or self._close_cid is not None:
            return
        self._close_cid = self._fig.canvas.mpl_connect(
            "close_event", self._on_figure_close
        )

    def _on_figure_close(self, event: Any) -> None:
        del event  # the only figure this is connected to is self._fig
        if _closing_all_figures():
            return
        self._close_help()

    def _help_is_open(self) -> bool:
        return self._help_fig is not None and plt.fignum_exists(self._help_fig.number)

    def _close_on_key(self, key: str) -> Callable[[Any], None]:
        """Construct a key_press_event handler closing the help figure on ``key``."""

        def handler(event: Any) -> None:
            if event.key == key:
                self._close_help()

        return handler

    def _open_help(self) -> None:
        self._connect_close_hook()
        if self._help_fig is not None and self._help_is_open():
            _raise_window(self._help_fig)
            return

        help_fig = _build_help_figure(
            self._sections,
            self._title,
            self._footer,
            theme=self._theme,
            palette_overrides=self._palette,
            key_column=self._key_column,
            trigger_key=self._trigger_key,
            num=self._help_fig_num,
        )
        self._help_fig = help_fig
        _disable_default_keymap(help_fig)
        for key in (self._trigger_key, "q", "escape"):
            help_fig.canvas.mpl_connect("key_press_event", self._close_on_key(key))
        manager = help_fig.canvas.manager
        if manager is not None:
            manager.set_window_title(
                f"{self._title}  —  press {self._trigger_key} / q / Esc to close"
            )
        help_fig.show()

    def _close_help(self) -> None:
        if self._help_fig is not None and self._help_is_open():
            plt.close(self._help_fig)
        self._help_fig = None
