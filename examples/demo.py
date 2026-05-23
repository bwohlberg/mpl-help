"""
demo_config.py
==============
Demonstrates all three config-loading routes:

    1.  load_manager()   — reads a file from disk (format auto-detected)
    2.  loads_manager()  — parses an in-process text string
    3.  manager_from_dict() — builds directly from a Python dict

Run with:
    python demo_config.py [file|string|dict]

Default (no argument) uses the file route with example_help.yaml.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from mpl_help import load_manager, loads_manager, manager_from_dict


# ── sample figure ─────────────────────────────────────────────────────────────

# Colours used by the main figure, keyed by theme.
_FIG_COLOURS = {
    "dark":  dict(fig_bg="#0d1117", ax_bg="#161b22", spine="#30363d",
                  tick="#8b949e",  title="#c9d1d9"),
    "light": dict(fig_bg="#ffffff", ax_bg="#f6f8fa", spine="#d0d7de",
                  tick="#656d76",  title="#1f2328"),
}

# Plot line/point colours chosen to work on both backgrounds.
_PLOT_COLOURS = ["#0969da", "#8250df", "#1a7f37", "#cf222e"]


def make_figure(theme="dark"):
    fc  = _FIG_COLOURS[theme]
    rng = np.random.default_rng(0)
    t   = np.linspace(0, 4 * np.pi, 500)

    fig = plt.figure(figsize=(11, 6), facecolor=fc["fig_bg"])
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.35,
                            left=0.08, right=0.97, top=0.88, bottom=0.10)
    axes = [fig.add_subplot(gs[r, c]) for r in range(2) for c in range(2)]

    plots = [
        ("Sine",        t,               np.sin(t),                         _PLOT_COLOURS[0]),
        ("Damped cos",  t,               np.cos(t) * np.exp(-t / 8),        _PLOT_COLOURS[1]),
        ("Random walk", np.arange(300),  rng.standard_normal(300).cumsum(), _PLOT_COLOURS[2]),
        ("Scatter",     rng.standard_normal(200), rng.standard_normal(200), _PLOT_COLOURS[3]),
    ]
    for ax, (title, x, y, color) in zip(axes, plots):
        ax.set_facecolor(fc["ax_bg"])
        for sp in ax.spines.values():
            sp.set_edgecolor(fc["spine"])
        ax.tick_params(colors=fc["tick"], labelsize=8)
        ax.set_title(title, color=fc["title"], fontsize=9, pad=6)
        if title == "Scatter":
            ax.scatter(x, y, c=color, s=14, alpha=0.7, linewidths=0)
        else:
            ax.plot(x, y, color=color, lw=1.4)
    return fig


# ── route 1: load from file ────────────────────────────────────────────────────

def demo_file(fig, theme="dark"):
    print(f"Loading from example_help.yaml  [theme={theme}] …")
    mgr = load_manager(fig, "example_help.yaml", theme=theme)
    fig.suptitle(f"Config demo — file route  [theme={theme}]  (press h)",
                 color=_FIG_COLOURS[theme]["title"], fontsize=12, fontweight="bold", y=0.96)
    mgr.attach()
    return mgr  # must be held alive; mpl_connect uses weak refs for bound methods


# ── route 2: parse an inline YAML string ──────────────────────────────────────

INLINE_YAML = """
title: Inline YAML Help
trigger_key: h
footer: "loaded from an in-process string"

sections:
  - title: General
    accent: blue
    bindings:
      - key: h
        desc: Open / close this help window
      - key: "q / Escape"
        desc: Close figure

  - title: View
    accent: green
    bindings:
      - key: z
        desc: Zoom mode
      - key: p
        desc: Pan mode
      - key: "r / Home"
        desc: Reset view
    note: Click a subplot first to activate it.

  - title: Export
    accent: orange
    bindings:
      - key: s
        desc: Save figure
"""

def demo_string(fig, theme="dark"):
    print(f"Parsing inline YAML string  [theme={theme}] …")
    mgr = loads_manager(fig, INLINE_YAML, fmt="yaml", theme=theme)
    fig.suptitle(f"Config demo — string route  [theme={theme}]  (press h)",
                 color=_FIG_COLOURS[theme]["title"], fontsize=12, fontweight="bold", y=0.96)
    mgr.attach()
    return mgr  # must be held alive; mpl_connect uses weak refs for bound methods


# ── route 3: build from a Python dict ─────────────────────────────────────────

CONFIG_DICT = {
    "title":       "Dict-based Help",
    "trigger_key": "h",
    "footer":      "built from a Python dict",
    "sections": [
        {
            "title":  "General",
            "accent": "cyan",
            "bindings": [
                {"key": "h",          "desc": "Open / close this help window"},
                {"key": "q / Escape", "desc": "Close figure"},
            ],
        },
        {
            "title":  "View Controls",
            "accent": "#ffa657",   # hex colour works too
            "note":   "Pan and Zoom are toggled modes.",
            "bindings": [
                {"key": "z",        "desc": "Zoom mode"},
                {"key": "p",        "desc": "Pan mode"},
                {"key": "r / Home", "desc": "Reset view"},
                {"key": "+ / -",    "desc": "Zoom in / out"},
            ],
        },
    ],
}

def demo_dict(fig, theme="dark"):
    print(f"Building from Python dict  [theme={theme}] …")
    mgr = manager_from_dict(fig, CONFIG_DICT, theme=theme)
    fig.suptitle(f"Config demo — dict route  [theme={theme}]  (press h)",
                 color=_FIG_COLOURS[theme]["title"], fontsize=12, fontweight="bold", y=0.96)
    mgr.attach()
    return mgr  # must be held alive; mpl_connect uses weak refs for bound methods


# ── entry point ───────────────────────────────────────────────────────────────

ROUTES = {"file": demo_file, "string": demo_string, "dict": demo_dict}

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="mpl-help demo — exercise the three config-loading routes."
    )
    parser.add_argument(
        "route",
        nargs="?",
        default="file",
        choices=ROUTES,
        help="Config loading route to demonstrate (default: file)",
    )
    parser.add_argument(
        "--theme",
        default="dark",
        choices=["dark", "light"],
        help="Colour theme for the help window (default: dark)",
    )
    args = parser.parse_args()

    fig = make_figure(theme=args.theme)
    mgr = ROUTES[args.route](fig, theme=args.theme)  # noqa: F841
    plt.show()
