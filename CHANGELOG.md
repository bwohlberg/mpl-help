# Changelog

All notable changes to mpl-help are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Changed
- Minimum supported Python raised to 3.11
- Default `trigger_key` is now `?` rather than `h`, which matplotlib binds to
  `keymap.home` and therefore also reset the view of the monitored figure
- Minimum supported matplotlib raised to 3.6, the first release supporting
  Python 3.11
- Long notes and binding descriptions are wrapped, and their rows grow to fit,
  instead of overflowing the panel
- Invalid `theme`, `key_column`, `palette` and section `accent` values are now
  rejected when constructed, rather than when the help window first opens
- Each `HelpManager` now has its own help window, so that managers attached to
  different figures no longer resize, overwrite and close one another's
- The help window no longer responds to matplotlib's default key bindings,
  which could apply log scaling or a grid to the help text
- Darkened the dark theme alternating row colour, which matched the key badge
  background exactly

### Removed
- `toml` extra and the `tomli` fallback it provided: TOML config files are
  now always parsed with the standard library `tomllib` module

### Fixed
- The help window header and title claimed `h` closes the window even when
  another trigger key was configured
- Package metadata declared the MIT license, while the package is in fact
  BSD 3-Clause licensed
- Suppression of the help window toolbar no longer leaks into the rest of
  the session when figure creation fails
- `AttributeError` when reopening the help window under a backend whose
  figure manager has no window object, such as Agg or a non-Qt GUI backend

## [0.1.0] — 2026-05-15

### Added
- `HelpManager`, `HelpSection`, `KeyBinding` — programmatic API
- Figure-based help window rendered entirely in matplotlib (no external GUI toolkit)
- Per-section accent colours — named palette (`blue`, `green`, `orange`, …) or hex
- `load_manager()` — load config from a YAML / TOML / JSON file
- `loads_manager()` — parse a config string
- `manager_from_dict()` — build from a Python dict
- Toolbar suppressed on the help figure window
- Annotated example configs (`example_help.yaml`, `example_help.toml`)
