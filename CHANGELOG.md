# Changelog

All notable changes to mpl-help are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).


## [Unreleased]

### Fixed

- A key wider than the key badge column is no longer truncated by the left
  edge of the help window.  Since the badges are right-aligned on the
  column, a badge that did not fit it extended to the left of the section
  panel, and beyond the edge of the figure if it was wider still, as the
  keys naming mouse actions rather than keystrokes tend to be.  The
  `key_column` value is now a minimum: the column is widened to fit the
  widest badge, which costs width for the descriptions rather than height,
  as they wrap only where the narrowing passes a word boundary.  The column
  is not widened beyond 0.6 of the figure width, and a key too wide for
  that column is wrapped onto as many lines as it needs, so that no key can
  be truncated.


## [0.1.0] — 2026-11-25

### Initial release.
