"""
matplotlib_help_figure.py
=========================
Backend-independent help window for matplotlib figures that renders
the help content inside a second matplotlib figure — no subprocess,
no browser, no GUI toolkit outside matplotlib itself.

Pressing "h" opens (or raises) a styled help figure.  Pressing "h",
"q", or Escape inside the help figure closes it.

Layout engine
-------------
Everything is drawn in a single full-figure Axes whose coordinate
system is defined in *row units*:

    x  ∈  [0, 1]        (figure width)
    y  ∈  [0, n_rows]   (top = n_rows, bottom = 0)

Each element consumes a fixed number of row units:

    SECTION_HEADER  1.4 rows
    BINDING_ROW     1.0 row
    NOTE_ROW        0.9 row
    SECTION_GAP     0.5 rows
    TOP / BOT PAD   1.0 row each

The figure height in inches is then  n_rows × ROW_H_IN,
which keeps every element at a consistent pixel height regardless
of how many sections there are.

Usage
-----
    from matplotlib_help_figure import HelpManager, HelpSection, KeyBinding

    help_mgr = HelpManager(fig, title="My App — Help")
    help_mgr.add_section(HelpSection(
        title="Navigation",
        bindings=[
            KeyBinding("h",          "Show this help window"),
            KeyBinding("q / Escape", "Close figure"),
        ],
    ))
    help_mgr.attach()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Row-height constants  (in row-units)
# ---------------------------------------------------------------------------
_ROW_H_IN      = 0.32   # inches per row unit  → sets overall figure height
_PAD_TOP       = 2.2    # rows reserved for header
_PAD_BOT       = 0.9    # rows reserved for footer
_SECTION_HDR   = 1.3    # rows per section title bar
_BINDING_ROW   = 1.0    # rows per key-binding line
_NOTE_ROW      = 0.85   # rows for an optional note
_SECTION_GAP   = 0.45   # gap between sections
_FIG_WIDTH_IN  = 7.2    # fixed figure width in inches

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
C = dict(
    bg        = "#0d1117",
    surface   = "#161b22",
    panel     = "#21262d",
    border    = "#30363d",
    accent    = "#58a6ff",
    accent2   = "#bc8cff",
    green     = "#3fb950",
    text      = "#e6edf3",
    muted     = "#8b949e",
    key_bg    = "#1c2128",
    key_fg    = "#ffa657",
    note_fg   = "#3fb950",
    alt_row   = "#161b22",
)


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
        Hex colour string (``"#rrggbb"``) that overrides the default
        accent colour for this section's title bar and stripe.
        Pass ``None`` (default) to use the global palette colour.
    """
    title: str
    bindings: List[KeyBinding] = field(default_factory=list)
    note: Optional[str] = None
    accent: Optional[str] = None   # per-section accent colour (hex or None)


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
) -> mpl.figure.Figure:
    """Create and return the fully rendered help figure."""

    n_rows = _total_rows(sections)
    fig_h  = max(n_rows * _ROW_H_IN, 3.0)

    old_toolbar = mpl.rcParams['toolbar']
    mpl.rcParams['toolbar'] = 'None'
    fig = plt.figure(
        figsize=(_FIG_WIDTH_IN, fig_h),
        facecolor=C["bg"],
        num="__mpl_help__",
    )
    mpl.rcParams['toolbar'] = old_toolbar
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
        facecolor=C["accent"], edgecolor="none",
        transform=ax.transData, clip_on=False, zorder=3,
    ))

    # ── header title ──────────────────────────────────────────────────
    ax.text(
        0.04, n_rows - 0.75, title,
        fontsize=13, fontweight="bold",
        color=C["text"], va="center", ha="left",
        transform=ax.transData,
    )
    # "HELP" badge
    ax.text(
        0.04 + len(title) * 0.0115 + 0.045,
        n_rows - 0.75,
        "  HELP  ",
        fontsize=6.5, fontweight="bold", color=C["accent"],
        va="center", ha="left",
        bbox=dict(
            boxstyle="round,pad=0.25", facecolor="none",
            edgecolor=C["accent"], linewidth=0.8,
        ),
        transform=ax.transData,
    )
    # dismiss hint
    ax.text(
        0.97, n_rows - 0.75,
        "press  h / q / Esc  to close",
        fontsize=7, color=C["muted"],
        va="center", ha="right",
        transform=ax.transData,
    )
    # header separator
    ax.axhline(
        n_rows - _PAD_TOP + 0.22,
        xmin=0.03, xmax=0.97,
        color=C["border"], linewidth=0.7, zorder=2,
    )

    # ── sections ──────────────────────────────────────────────────────
    y = n_rows - _PAD_TOP   # cursor: current top of next element

    for sec_idx, section in enumerate(sections):
        sec_h = _section_height(section)

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
        # Resolve accent colour: per-section override or global palette default
        sec_accent = section.accent if section.accent else C["accent2"]

        # Accent stripe on left edge of title bar
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.03, y - _SECTION_HDR), 0.004, _SECTION_HDR,
            boxstyle="square,pad=0",
            facecolor=sec_accent, edgecolor="none",
            transform=ax.transData, zorder=3,
        ))
        # Section title text
        ax.text(
            0.055, y - _SECTION_HDR / 2,
            "  ".join(section.title.upper()),   # spaced letters via string
            fontsize=7.5, fontweight="bold",
            color=sec_accent, va="center", ha="left",
            transform=ax.transData, zorder=4,
        )

        y -= _SECTION_HDR

        # Key-binding rows
        for i, kb in enumerate(section.bindings):
            row_bg = C["alt_row"] if i % 2 == 0 else C["surface"]
            ax.add_patch(mpatches.FancyBboxPatch(
                (0.03, y - _BINDING_ROW), 0.94, _BINDING_ROW,
                boxstyle="square,pad=0",
                facecolor=row_bg, edgecolor="none",
                transform=ax.transData, zorder=2,
            ))

            row_mid = y - _BINDING_ROW / 2

            # Key badge
            ax.text(
                0.24, row_mid,
                kb.key,
                fontsize=8, fontweight="bold",
                fontfamily="monospace",
                color=C["key_fg"], va="center", ha="right",
                bbox=dict(
                    boxstyle="round,pad=0.28",
                    facecolor=C["key_bg"],
                    edgecolor=C["border"],
                    linewidth=0.6,
                ),
                transform=ax.transData, zorder=3,
            )

            # Description
            ax.text(
                0.27, row_mid,
                kb.description,
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
                facecolor="#0f2a0f", edgecolor=C["green"],
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
        0.04, _PAD_BOT / 2 - 0.1,
        footer,
        fontsize=7, color=C["muted"],
        va="center", ha="left",
        transform=ax.transData,
    )
    ax.text(
        0.97, _PAD_BOT / 2 - 0.1,
        "matplotlib-help-figure",
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
        Key that opens the help figure (default ``"h"``).
    footer : str, optional
        Small note at the bottom of the help figure.
    """

    def __init__(
        self,
        fig,
        title: str = "Keyboard Shortcuts",
        trigger_key: str = "h",
        footer: Optional[str] = None,
    ) -> None:
        self._fig         = fig
        self._title       = title
        self._trigger_key = trigger_key
        self._footer      = footer or f"press  {trigger_key}  to reopen"
        self._sections: List[HelpSection] = []
        self._cid         = None      # canvas connection id on main figure
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
            self._sections, self._title, self._footer
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
