"""
mpl-help
========
Backend-independent help windows for matplotlib figures.

Pressing a configurable trigger key (default ``h``) inside a matplotlib
figure opens a styled help window that lists keyboard shortcuts, grouped
into sections with optional per-section accent colours and notes.

Quickstart — programmatic API
------------------------------
::

    import matplotlib.pyplot as plt
    from mpl_help import HelpManager, HelpSection, KeyBinding

    fig, ax = plt.subplots()

    help_mgr = HelpManager(fig, title="My App — Help")
    help_mgr.add_section(HelpSection(
        title="Navigation",
        bindings=[
            KeyBinding("h",          "Show this help window"),
            KeyBinding("q / Escape", "Close figure"),
            KeyBinding("← → ↑ ↓",   "Pan the active axes"),
        ],
        note="Click a subplot first to make it active.",
    ))
    help_mgr.attach()
    plt.show()

Quickstart — config file API
-----------------------------
::

    from mpl_help import load_manager

    help_mgr = load_manager(fig, "my_app_help.yaml")
    help_mgr.attach()
    plt.show()

See ``examples/example_help.yaml`` for a fully annotated config template.
"""

from mpl_help._figure import HelpManager, HelpSection, KeyBinding
from mpl_help._config import load_manager, loads_manager, manager_from_dict

__version__ = "0.1.0"
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
]
