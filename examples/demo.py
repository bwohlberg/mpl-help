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

import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from mpl_help import load_manager, loads_manager, manager_from_dict


# ── sample figure ─────────────────────────────────────────────────────────────

def make_figure():
    rng = np.random.default_rng(0)
    t   = np.linspace(0, 4 * np.pi, 500)

    fig = plt.figure(figsize=(11, 6), facecolor="#0d1117")
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.35,
                            left=0.08, right=0.97, top=0.88, bottom=0.10)
    axes = [fig.add_subplot(gs[r, c]) for r in range(2) for c in range(2)]

    plots = [
        ("Sine",         t,              np.sin(t),                   "#7aa2f7"),
        ("Damped cos",   t,              np.cos(t)*np.exp(-t/8),      "#bc8cff"),
        ("Random walk",  np.arange(300), rng.standard_normal(300).cumsum(), "#3fb950"),
        ("Scatter",      rng.standard_normal(200), rng.standard_normal(200), "#f85149"),
    ]
    for ax, (title, x, y, color) in zip(axes, plots):
        ax.set_facecolor("#161b22")
        for sp in ax.spines.values(): sp.set_edgecolor("#30363d")
        ax.tick_params(colors="#8b949e", labelsize=8)
        ax.set_title(title, color="#c9d1d9", fontsize=9, pad=6)
        if title == "Scatter":
            ax.scatter(x, y, c=color, s=14, alpha=0.7, linewidths=0)
        else:
            ax.plot(x, y, color=color, lw=1.4)
    return fig


# ── route 1: load from file ────────────────────────────────────────────────────

def demo_file(fig):
    print("Loading from example_help.yaml …")
    mgr = load_manager(fig, "example_help.yaml", backend="figure")
    fig.suptitle("Config demo — file route  (press h)",
                 color="#e6edf3", fontsize=12, fontweight="bold", y=0.96)
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

def demo_string(fig):
    print("Parsing inline YAML string …")
    mgr = loads_manager(fig, INLINE_YAML, fmt="yaml", backend="figure")
    fig.suptitle("Config demo — string route  (press h)",
                 color="#e6edf3", fontsize=12, fontweight="bold", y=0.96)
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

def demo_dict(fig):
    print("Building from Python dict …")
    mgr = manager_from_dict(fig, CONFIG_DICT, backend="figure")
    fig.suptitle("Config demo — dict route  (press h)",
                 color="#e6edf3", fontsize=12, fontweight="bold", y=0.96)
    mgr.attach()
    return mgr  # must be held alive; mpl_connect uses weak refs for bound methods


# ── entry point ───────────────────────────────────────────────────────────────

ROUTES = {"file": demo_file, "string": demo_string, "dict": demo_dict}

if __name__ == "__main__":
    route = sys.argv[1] if len(sys.argv) > 1 else "file"
    if route not in ROUTES:
        print(f"Usage: python demo_config.py [{' | '.join(ROUTES)}]")
        sys.exit(1)

    fig = make_figure()
    mgr = ROUTES[route](fig)  # noqa: F841 — must stay in scope for callbacks to fire
    plt.show()
