# Changelog

All notable changes to mpl-help are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Changed
- Minimum supported Python raised to 3.11

### Removed
- `toml` extra and the `tomli` fallback it provided: TOML config files are
  now always parsed with the standard library `tomllib` module

### Fixed
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
