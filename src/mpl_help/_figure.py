"""
mpl_help._figure
================
Core renderer for the mpl-help figure-based help window.

All colours are resolved through a two-theme palette system.
See :data:`DEFAULT_PALETTE` for the built-in colour definitions and
:class:`HelpManager` for how to supply per-instance overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Row-height constants  (in row-units)
# ---------------------------------------------------------------------------
_ROW_H_IN     = 0.32   # inches per row unit
_PAD_TOP      = 2.2    # rows reserved for header
_PAD_BOT      = 0.9    # rows reserved for footer
_SECTION_HDR  = 1.3    # rows per section title bar
_BINDING_ROW  = 1.0    # rows per key-binding line
_NOTE_ROW     = 0.85   # rows for an optional note
_SECTION_GAP  = 0.45   # gap between sections
_FIG_WIDTH_IN = 7.2    # fixed figure width in inches

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

DEFAULT_PALETTE: Dict[str, Tuple[str, str]] = {
    # ── structural ──────────────────────────── light        dark
    "bg":          ("#ffffff", "#0d1117"),
    "surface":     ("#f6f8fa", "#161b22"),
    "panel":       ("#eaeef2", "#21262d"),
    "border":      ("#d0d7de", "#30363d"),
    "text":        ("#1f2328", "#e6edf3"),
    "muted":       ("#656d76", "#8b949e"),
    "key_bg":      ("#eaeef2", "#1c2128"),
    "key_fg":      ("#953800", "#ffa657"),
    "note_fg":     ("#1a7f37", "#3fb950"),
    "note_bg":     ("#dafbe1", "#0f2a0f"),
    "note_border": ("#82cfaa", "#2ea043"),
    "alt_row":     ("#f0f2f5", "#1c2128"),
    "top_bar":     ("#0969da", "#58a6ff"),
    # ── named accent colours ─────────────────── light        dark
    "blue":        ("#0969da", "#58a6ff"),
    "purple":      ("#8250df", "#bc8cff"),
    "green":       ("#1a7f37", "#3fb950"),
    "yellow":      ("#9a6700", "#d29922"),
    "orange":      ("#bc4c00", "#ffa657"),
    "red":         ("#cf222e", "#f85149"),
    "cyan":        ("#1b7c83", "#39c5cf"),
}

#: The set of valid named accent colours accepted by config files and
#: :class:`HelpSection`.
ACCENT_NAMES = frozenset(
    "blue purple green yellow orange red cyan".split()
)

_THEME_IDX: Dict[str, int] = {"light": 0, "dark": 1}


# ---------------------------------------------------------------------------
# Palette helpers
# ---------------------------------------------------------------------------

def _make_colour_map(
    theme: str,
    overrides: Optional[Dict[str, Tuple[str, str]]] = None,
) -> Dict[str, str]:
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
        raise ValueError(
            f"Unknown theme {theme!r}. Choose 'dark' or 'light'."
        )
    idx = _THEME_IDX[theme]
    colours = {name: pair[idx] for name, pair in DEFAULT_PALETTE.items()}
    if overrides:
        for name, pair in overrides.items():
            if name in DEFAULT_PALETTE:
                colours[name] = pair[idx]
            # silently ignore unknown keys
    return colours


def _resolve_accent(
    name_or_hex: Optional[str],
    colours: Dict[str, str],
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
    bindings: List[KeyBinding] = field(default_factory=list)
    note: Optional[str] = None
    accent: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal layout helpers
# ---------------------------------------------------------------------------

def _section_height(section: HelpSection) -> float:
    """Total row-units consumed by one section (excluding trailing gap)."""
    h = _SECTION_HDR + len(section.bindings) * _BINDING_ROW
    if section.note:
        h += _NOTE_ROW
    return h


def _total_rows(sections: List[HelpSection]) -> float:
    rows = _PAD_TOP + _PAD_BOT
    for i, s in enumerate(sections):
        rows += _section_height(s)
        if i < len(sections) - 1:
            rows += _SECTION_GAP
    return rows


# ---------------------------------------------------------------------------
# Figure renderer
# ---------------------------------------------------------------------------

def _build_help_figure(
    sections: List[HelpSection],
    title: str,
    footer: str,
    theme: str = "dark",
    palette_overrides: Optional[Dict[str, Tuple[str, str]]] = None,
) -> mpl.figure.Figure:
    """Create and return the fully rendered help figure."""

    C = _make_colour_map(theme, palette_overrides)

    n_rows = _total_rows(sections)
    fig_h  = max(n_rows * _ROW_H_IN, 3.0)

    old_toolbar = mpl.rcParams["toolbar"]
    mpl.rcParams["toolbar"] = "None"
    fig = plt.figure(
        figsize=(_FIG_WIDTH_IN, fig_h),
        facecolor=C["bg"],
        num="__mpl_help__",
    )
    mpl.rcParams["toolbar"] = old_toolbar
    fig.clf()

    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, n_rows)
    ax.axis("off")
    ax.set_facecolor(C["bg"])

    # ── top accent bar ────────────────────────────────────────────────
    ax.add_patch(mpatches.FancyBboxPatch(
        (0, n_rows - 0.18), 1, 0.18,
        boxstyle="square,pad=0",
        facecolor=C["top_bar"], edgecolor="none",
        transform=ax.transData, clip_on=False, zorder=3,
    ))

    # ── header title ──────────────────────────────────────────────────
    ax.text(
        0.04, n_rows - 0.75, title,
        fontsize=13, fontweight="bold",
        color=C["text"], va="center", ha="left",
        transform=ax.transData,
    )
    ax.text(
        0.97, n_rows - 0.75,
        "press  h / q / Esc  to close",
        fontsize=7, color=C["muted"],
        va="center", ha="right",
        transform=ax.transData,
    )
    ax.axhline(
        n_rows - _PAD_TOP + 0.22,
        xmin=0.03, xmax=0.97,
        color=C["border"], linewidth=0.7, zorder=2,
    )

    # ── sections ──────────────────────────────────────────────────────
    y = n_rows - _PAD_TOP

    for section in sections:
        sec_h      = _section_height(section)
        sec_accent = _resolve_accent(section.accent, C)

        # Section background panel
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.03, y - sec_h), 0.94, sec_h,
            boxstyle="round,pad=0.0",
            facecolor=C["surface"], edgecolor=C["border"],
            linewidth=0.6, transform=ax.transData, zorder=1,
        ))

        # Section title bar background
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.03, y - _SECTION_HDR), 0.94, _SECTION_HDR,
            boxstyle="square,pad=0",
            facecolor=C["panel"], edgecolor="none",
            transform=ax.transData, zorder=2,
        ))

        # Accent stripe on left edge
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.03, y - _SECTION_HDR), 0.004, _SECTION_HDR,
            boxstyle="square,pad=0",
            facecolor=sec_accent, edgecolor="none",
            transform=ax.transData, zorder=3,
        ))

        # Section title text
        ax.text(
            0.055, y - _SECTION_HDR / 2,
            "  ".join(section.title.upper()),
            fontsize=7.5, fontweight="bold",
            color=sec_accent, va="center", ha="left",
            transform=ax.transData, zorder=4,
        )

        y -= _SECTION_HDR

        # Key-binding rows
        for i, kb in enumerate(section.bindings):
            row_bg  = C["alt_row"] if i % 2 == 0 else C["surface"]
            row_mid = y - _BINDING_ROW / 2

            ax.add_patch(mpatches.FancyBboxPatch(
                (0.03, y - _BINDING_ROW), 0.94, _BINDING_ROW,
                boxstyle="square,pad=0",
                facecolor=row_bg, edgecolor="none",
                transform=ax.transData, zorder=2,
            ))
            ax.text(
                0.24, row_mid, kb.key,
                fontsize=8, fontweight="bold", fontfamily="monospace",
                color=C["key_fg"], va="center", ha="right",
                bbox=dict(
                    boxstyle="round,pad=0.28",
                    facecolor=C["key_bg"],
                    edgecolor=C["border"],
                    linewidth=0.6,
                ),
                transform=ax.transData, zorder=3,
            )
            ax.text(
                0.27, row_mid, kb.description,
                fontsize=8.5, color=C["text"],
                va="center", ha="left",
                transform=ax.transData, zorder=3,
            )
            y -= _BINDING_ROW

        # Optional note
        if section.note:
            ax.add_patch(mpatches.FancyBboxPatch(
                (0.05, y - _NOTE_ROW + 0.08), 0.90, _NOTE_ROW - 0.08,
                boxstyle="round,pad=0.05",
                facecolor=C["note_bg"], edgecolor=C["note_border"],
                linewidth=0.5, transform=ax.transData, zorder=3,
            ))
            ax.text(
                0.08, y - _NOTE_ROW / 2 + 0.04,
                f"ℹ  {section.note}",
                fontsize=7.5, color=C["note_fg"],
                va="center", ha="left",
                wrap=True, transform=ax.transData, zorder=4,
            )
            y -= _NOTE_ROW

        y -= _SECTION_GAP

    # ── footer ────────────────────────────────────────────────────────
    ax.axhline(
        _PAD_BOT - 0.15,
        xmin=0.03, xmax=0.97,
        color=C["border"], linewidth=0.7,
    )
    ax.text(
        0.04, _PAD_BOT / 2 - 0.1, footer,
        fontsize=7, color=C["muted"],
        va="center", ha="left",
        transform=ax.transData,
    )
    ax.text(
        0.97, _PAD_BOT / 2 - 0.1, "mpl-help",
        fontsize=7, color=C["muted"],
        va="center", ha="right",
        transform=ax.transData,
    )

    return fig


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
        Key that opens / closes the help figure (default ``"h"``).
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
        Unknown keys are silently ignored.
    """

    def __init__(
        self,
        fig,
        title: str = "Keyboard Shortcuts",
        trigger_key: str = "h",
        footer: Optional[str] = None,
        theme: str = "dark",
        palette: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> None:
        self._fig         = fig
        self._title       = title
        self._trigger_key = trigger_key
        self._footer      = footer or f"press  {trigger_key}  to reopen"
        self._theme       = theme
        self._palette     = palette
        self._sections: List[HelpSection] = []
        self._cid         = None
        self._help_fig: Optional[mpl.figure.Figure] = None

    # ── public API ────────────────────────────────────────────────────

    def add_section(self, section: HelpSection) -> "HelpManager":
        """Append a :class:`HelpSection` and return self (chainable)."""
        self._sections.append(section)
        return self

    def attach(self) -> "HelpManager":
        """Start listening for keypresses on the main figure canvas."""
        if self._cid is not None:
            return self
        self._cid = self._fig.canvas.mpl_connect(
            "key_press_event", self._on_key_press
        )
        return self

    def detach(self) -> "HelpManager":
        """Stop listening and close the help figure if open."""
        if self._cid is not None:
            self._fig.canvas.mpl_disconnect(self._cid)
            self._cid = None
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

    def _help_is_open(self) -> bool:
        return (
            self._help_fig is not None
            and plt.fignum_exists(self._help_fig.number)
        )

    def _open_help(self) -> None:
        if self._help_is_open():
            self._help_fig.canvas.manager.window.raise_()
            return

        self._help_fig = _build_help_figure(
            self._sections, self._title, self._footer,
            theme=self._theme, palette_overrides=self._palette,
        )
        for key in (self._trigger_key, "q", "escape"):
            self._help_fig.canvas.mpl_connect(
                "key_press_event",
                lambda e, k=key: self._close_help() if e.key == k else None,
            )
        self._help_fig.canvas.manager.set_window_title(
            f"{self._title}  —  press h / q / Esc to close"
        )
        self._help_fig.show()

    def _close_help(self) -> None:
        if self._help_is_open():
            plt.close(self._help_fig)
        self._help_fig = None
