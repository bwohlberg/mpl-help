"""
mpl-help
========
Backend-independent help windows for matplotlib figures.

Quickstart — programmatic API
------------------------------
::

    import matplotlib.pyplot as plt
    from mpl_help import HelpManager, HelpSection, KeyBinding

    fig, ax = plt.subplots()
    help_mgr = HelpManager(fig, title="My App", theme="dark")
    help_mgr.add_section(HelpSection(
        title="Navigation",
        accent="blue",
        bindings=[
            KeyBinding("h",          "Show this help window"),
            KeyBinding("q / Escape", "Close figure"),
        ],
    ))
    help_mgr.attach()
    plt.show()

Quickstart — config file API
-----------------------------
::

    from mpl_help import load_manager

    help_mgr = load_manager(fig, "my_app_help.yaml", theme="light")
    help_mgr.attach()
    plt.show()

Theme and palette
-----------------
Two built-in themes are available: ``"dark"`` (default) and ``"light"``.
Individual palette colours can be overridden per-instance::

    from mpl_help import HelpManager, DEFAULT_PALETTE

    help_mgr = HelpManager(
        fig,
        theme="light",
        palette={
            "blue": ("#1a5fb4", "#6ab0f5"),   # (light_hex, dark_hex)
            "bg":   ("#fafafa", "#0a0d12"),
        },
    )

See :data:`DEFAULT_PALETTE` for all available keys.
Valid accent colour names are listed in :data:`ACCENT_NAMES`.
"""

from mpl_help._figure import (
    HelpManager,
    HelpSection,
    KeyBinding,
    DEFAULT_PALETTE,
    ACCENT_NAMES,
)
from mpl_help._config import load_manager, loads_manager, manager_from_dict

__version__ = "0.1.0rc3"
__author__  = "Your Name"
__email__   = "you@example.com"

__all__ = [
    # Core data classes
    "HelpSection",
    "KeyBinding",
    # Manager
    "HelpManager",
    # Config loaders
    "load_manager",
    "loads_manager",
    "manager_from_dict",
    # Palette introspection
    "DEFAULT_PALETTE",
    "ACCENT_NAMES",
]
