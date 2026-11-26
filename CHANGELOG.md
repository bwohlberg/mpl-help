# Changelog

All notable changes to mpl-help are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).


## [Unreleased]


## [0.1.1] — 2026-11-26

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
- Text is measured with the renderer that draws it, rather than from the
  font metrics alone, which underestimated the width drawn by a margin
  that depends on the version of matplotlib: 0.9% of a key under 3.10 but
  4.65% under 3.11, which is more than the margin that the wrapping of
  text allows for.  The layout therefore no longer leaves text wider than
  the space allowed for it, and a help window is built more quickly, since
  measuring with the renderer does not build the glyph paths that
  measuring from the metrics did.
- The box around a section note no longer extends beyond the section panel
  on each side.  Its margins came from the padding of its boxstyle, which
  is applied in data coordinates: these span the figure width in x but the
  rows of the layout in y, so a padding large enough to be seen in y took
  the box to the edges of the figure in x.  The margins are now part of the
  geometry of the box, which is aligned with the section panel that it
  belongs to.


## [0.1.0] — 2026-11-25

### Initial release.
