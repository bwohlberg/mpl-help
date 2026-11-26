"""
tests/test_mpl_help.py
======================
Unit tests for mpl-help.  Run with:  pytest
"""

import gc
import json

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backend_bases import CloseEvent, KeyEvent

from mpl_help import (
    ACCENT_NAMES,
    DEFAULT_PALETTE,
    HelpManager,
    HelpSection,
    KeyBinding,
    load_manager,
    loads_manager,
    manager_from_dict,
)
from mpl_help._figure import (
    _build_help_figure,
    _closing_all_figures,
    _make_colour_map,
    _resolve_accent,
    _section_height,
    _total_rows,
)


def _close_window(fig):
    """Close *fig* the way an interactive backend closes a window.

    The Agg backend used by these tests has no window, so it never emits
    the ``close_event`` that every GUI backend emits from its window
    destruction handler; synthesise it here, then destroy the figure.
    """
    CloseEvent("close_event", fig.canvas)._process()
    plt.close(fig)


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def close_all_figures():
    yield
    plt.close("all")


@pytest.fixture
def fig():
    f = plt.figure()
    f.add_subplot(111)
    return f


@pytest.fixture
def simple_section():
    return HelpSection(
        title="Navigation",
        bindings=[KeyBinding("h", "Help"), KeyBinding("q / Escape", "Quit")],
        note="A note.",
        accent="blue",
    )


@pytest.fixture
def simple_manager(fig, simple_section):
    mgr = HelpManager(fig, title="Test Help", footer="test footer")
    mgr.add_section(simple_section)
    return mgr


# ── palette ───────────────────────────────────────────────────────────────────


class TestPalette:
    def test_default_palette_has_both_themes(self):
        for name, pair in DEFAULT_PALETTE.items():
            assert (
                isinstance(pair, tuple) and len(pair) == 2
            ), f"{name!r} should be a (light, dark) tuple"
            assert pair[0].startswith("#") and pair[1].startswith(
                "#"
            ), f"{name!r} values should be hex strings"

    def test_accent_names_are_subset_of_palette(self):
        for name in ACCENT_NAMES:
            assert (
                name in DEFAULT_PALETTE
            ), f"accent name {name!r} not in DEFAULT_PALETTE"

    def test_make_colour_map_dark(self):
        C = _make_colour_map("dark")
        assert C["bg"] == DEFAULT_PALETTE["bg"][1]
        assert C["blue"] == DEFAULT_PALETTE["blue"][1]

    def test_make_colour_map_light(self):
        C = _make_colour_map("light")
        assert C["bg"] == DEFAULT_PALETTE["bg"][0]
        assert C["blue"] == DEFAULT_PALETTE["blue"][0]

    def test_make_colour_map_invalid_theme(self):
        with pytest.raises(ValueError, match="Unknown"):
            _make_colour_map("solarized")

    def test_palette_overrides_applied(self):
        overrides = {"blue": ("#aaaaaa", "#bbbbbb")}
        C_light = _make_colour_map("light", overrides)
        C_dark = _make_colour_map("dark", overrides)
        assert C_light["blue"] == "#aaaaaa"
        assert C_dark["blue"] == "#bbbbbb"

    def test_unknown_override_keys_ignored(self):
        # Should not raise
        C = _make_colour_map("dark", {"nonexistent": ("#111111", "#222222")})
        assert "nonexistent" not in C

    def test_resolve_accent_none_returns_purple(self):
        C = _make_colour_map("dark")
        assert _resolve_accent(None, C) == C["purple"]

    def test_resolve_accent_named(self):
        C = _make_colour_map("dark")
        assert _resolve_accent("blue", C) == C["blue"]
        assert _resolve_accent("green", C) == C["green"]

    def test_resolve_accent_hex_passthrough(self):
        C = _make_colour_map("dark")
        assert _resolve_accent("#abcdef", C) == "#abcdef"

    def test_dark_and_light_differ_structurally(self):
        C_dark = _make_colour_map("dark")
        C_light = _make_colour_map("light")
        assert C_dark["bg"] != C_light["bg"]
        assert C_dark["text"] != C_light["text"]

    def test_dark_and_light_accents_differ(self):
        # Accent colours should be different between themes (darker on light bg)
        C_dark = _make_colour_map("dark")
        C_light = _make_colour_map("light")
        assert C_dark["blue"] != C_light["blue"]


# ── data classes ──────────────────────────────────────────────────────────────


class TestDataClasses:
    def test_keybinding_fields(self):
        kb = KeyBinding("h", "Open help")
        assert kb.key == "h"
        assert kb.description == "Open help"

    def test_helpsection_defaults(self):
        s = HelpSection("Nav", [])
        assert s.note is None
        assert s.accent is None

    def test_helpsection_with_named_accent(self):
        s = HelpSection("Nav", [], accent="blue")
        assert s.accent == "blue"

    def test_helpsection_with_hex_accent(self):
        s = HelpSection("Nav", [], accent="#ff0000")
        assert s.accent == "#ff0000"


# ── layout arithmetic ─────────────────────────────────────────────────────────


class TestLayout:
    def test_section_height_no_note(self):
        from mpl_help._figure import _BINDING_ROW, _SECTION_HDR

        s = HelpSection("Nav", [KeyBinding("h", "Help"), KeyBinding("q", "Quit")])
        assert _section_height(s) == pytest.approx(_SECTION_HDR + 2 * _BINDING_ROW)

    def test_section_height_with_note(self, simple_section):
        from mpl_help._figure import _BINDING_ROW, _NOTE_ROW, _SECTION_HDR

        assert _section_height(simple_section) == pytest.approx(
            _SECTION_HDR + 2 * _BINDING_ROW + _NOTE_ROW
        )

    def test_long_description_wraps_and_grows_row(self):
        from mpl_help._figure import _BINDING_ROW, _SECTION_HDR, _description_lines

        long_desc = (
            "toggle the overlay, reset the current view to its initial limits, "
            "and print a summary of the current selection to standard output"
        )
        assert len(_description_lines(long_desc, 0.24)) > 1
        s = HelpSection("Nav", [KeyBinding("x", long_desc)])
        assert _section_height(s) > _SECTION_HDR + _BINDING_ROW

    def test_long_note_wraps_and_grows_section(self):
        from mpl_help._figure import _note_lines

        long_note = (
            "This note is deliberately long indeed: it describes in detail what "
            "each of the bindings above does, why it exists, and which of the "
            "alternative key choices were considered first."
        )
        assert len(_note_lines(long_note)) > 1
        short = HelpSection("Nav", [KeyBinding("x", "y")], note="A note.")
        long = HelpSection("Nav", [KeyBinding("x", "y")], note=long_note)
        assert _section_height(long) > _section_height(short)

    def test_wrapped_text_stays_within_panel(self):
        from mpl_help._figure import _PANEL_RIGHT, _build_help_figure

        long_note = (
            "This note is deliberately long indeed: it describes in detail what "
            "each of the bindings above does, why it exists, and which of the "
            "alternative key choices were considered first."
        )
        section = HelpSection("Nav", [KeyBinding("x", "y")], note=long_note)
        fig = _build_help_figure([section], "T", "F")
        fig.canvas.draw()
        axes = fig.axes[0]
        inverse = axes.transData.inverted()
        renderer = fig.canvas.get_renderer()
        for text in axes.texts:
            bbox = text.get_window_extent(renderer)
            right = inverse.transform([(bbox.x1, bbox.y1)])[0][0]
            assert right <= _PANEL_RIGHT + 0.01, text.get_text()

    def test_section_panel_matches_wrapped_content(self):
        import matplotlib.colors as mcolors

        from mpl_help._figure import DEFAULT_PALETTE, _build_help_figure

        long_desc = (
            "toggle the overlay, reset the view to its initial limits, and "
            "print a summary of the current selection to standard output"
        )
        section = HelpSection(
            "Nav", [KeyBinding("x", long_desc), KeyBinding("y", "brief")]
        )
        surface = mcolors.to_hex(DEFAULT_PALETTE["surface"][1])
        for key_column in (0.24, 0.45):
            fig = _build_help_figure(
                [section], "T", "F", theme="dark", key_column=key_column
            )
            panel = next(
                p
                for p in fig.axes[0].patches
                if mcolors.to_hex(p.get_facecolor()) == surface
            )
            assert panel.get_height() == pytest.approx(
                _section_height(section, key_column)
            )

    def test_total_rows_padding(self):
        from mpl_help._figure import _PAD_BOT, _PAD_TOP

        assert _total_rows([]) == pytest.approx(_PAD_TOP + _PAD_BOT)


# ── figure builder ────────────────────────────────────────────────────────────


class TestKeyColumnFit:
    """The key badge column is fitted to the keys it has to display."""

    # A key of the length that a plotting package generates when it names a
    # mouse action rather than a key, which is wider than the default column
    WIDE_KEY = "Mouse wheel in lower half of colorbar"

    def _badge_bounds(self, fig):
        """Left and right edge of each key badge, in axes coordinates."""
        fig.canvas.draw()
        axes = fig.axes[0]
        inverse = axes.transData.inverted()
        renderer = fig.canvas.get_renderer()
        bounds = []
        for text in axes.texts:
            if text.get_ha() != "right" or text.get_bbox_patch() is None:
                continue
            bbox = text.get_bbox_patch().get_window_extent(renderer)
            (left, _), (right, _) = inverse.transform(
                [(bbox.x0, bbox.y0), (bbox.x1, bbox.y1)]
            )
            bounds.append((left, right, text))
        return bounds

    def test_requested_column_kept_when_keys_fit(self):
        from mpl_help._figure import _fit_key_column

        section = HelpSection("Nav", [KeyBinding("x", "y"), KeyBinding("q", "quit")])
        for key_column in (0.24, 0.45):
            assert _fit_key_column([section], key_column) == pytest.approx(key_column)

    def test_column_widened_for_a_wide_key(self):
        from mpl_help._figure import _fit_key_column

        section = HelpSection("Nav", [KeyBinding(self.WIDE_KEY, "d")])
        assert _fit_key_column([section], 0.24) > 0.24

    def test_wide_key_badge_stays_within_panel(self):
        """A badge wider than the requested column must not be truncated.

        The badges are right-aligned on the key column, so one too wide
        for it used to extend beyond the left edge of the figure.
        """
        from mpl_help._figure import _PANEL_LEFT, _build_help_figure

        section = HelpSection(
            "Range",
            [KeyBinding(self.WIDE_KEY, "Increase or decrease the colormap vmin")],
        )
        fig = _build_help_figure([section], "T", "F", key_column=0.24)
        for left, _, text in self._badge_bounds(fig):
            assert left >= _PANEL_LEFT, text.get_text()

    def test_fitted_column_does_not_wrap_the_key_fitted_to(self):
        """A column widened to fit a key displays it on one line."""
        from mpl_help._figure import _build_help_figure

        section = HelpSection("Range", [KeyBinding(self.WIDE_KEY, "d")])
        fig = _build_help_figure([section], "T", "F", key_column=0.24)
        badges = [text for _, _, text in self._badge_bounds(fig)]
        assert [t.get_text() for t in badges] == [self.WIDE_KEY]

    def test_wide_key_does_not_change_the_height(self):
        """Fitting the column costs description width, not height.

        The description column is narrowed by the fit, so a description
        wraps into more lines only if the narrowing takes it past a word
        boundary, and a short one never does.
        """
        from mpl_help._figure import _build_help_figure

        sections = [HelpSection("Range", [KeyBinding(self.WIDE_KEY, "brief")])]
        fitted = _build_help_figure(sections, "T", "F", key_column=0.24)
        narrow = _build_help_figure(
            [HelpSection("Range", [KeyBinding("x", "brief")])], "T", "F"
        )
        assert fitted.get_size_inches()[1] == pytest.approx(narrow.get_size_inches()[1])

    def test_fit_is_bounded_and_key_wrapped_beyond_the_bound(self):
        """A key too wide for the widest column is wrapped to fit it."""
        from mpl_help._figure import (
            _KEY_COL_MAX,
            _PANEL_LEFT,
            _build_help_figure,
            _fit_key_column,
            _key_lines,
        )

        key = " ".join(["verbose"] * 30)
        sections = [HelpSection("Nav", [KeyBinding(key, "d")])]
        assert _fit_key_column(sections, 0.24) == pytest.approx(_KEY_COL_MAX)
        assert len(_key_lines(key, _KEY_COL_MAX)) > 1
        fig = _build_help_figure(sections, "T", "F")
        for left, _, text in self._badge_bounds(fig):
            assert left >= _PANEL_LEFT, text.get_text()

    def test_wrapped_key_grows_its_row(self):
        from mpl_help._figure import _BINDING_ROW, _binding_height

        key = " ".join(["verbose"] * 30)
        assert _binding_height(KeyBinding(key, "d"), 0.24) > _BINDING_ROW

    def test_fit_of_no_sections(self):
        from mpl_help._figure import _fit_key_column

        assert _fit_key_column([], 0.24) == pytest.approx(0.24)
        assert _fit_key_column([HelpSection("Empty", [])], 0.24) == pytest.approx(0.24)


class TestBuildHelpFigure:
    def test_returns_figure(self, simple_section):
        fig = _build_help_figure([simple_section], "Title", "Footer")
        assert isinstance(fig, mpl.figure.Figure)

    def test_axes_xlim(self, simple_section):
        fig = _build_help_figure([simple_section], "Title", "Footer")
        assert fig.axes[0].get_xlim() == (0.0, 1.0)

    def test_toolbar_suppressed(self, simple_section):
        fig = _build_help_figure([simple_section], "Title", "Footer")
        assert fig.canvas.toolbar is None

    def test_rcparam_restored_after_build(self, simple_section):
        original = mpl.rcParams["toolbar"]
        _build_help_figure([simple_section], "Title", "Footer")
        assert mpl.rcParams["toolbar"] == original

    def test_dark_theme_bg(self, simple_section):
        fig = _build_help_figure([simple_section], "T", "F", theme="dark")
        assert fig.get_facecolor() == pytest.approx(
            mpl.colors.to_rgba(DEFAULT_PALETTE["bg"][1]), abs=1e-3
        )

    def test_light_theme_bg(self, simple_section):
        fig = _build_help_figure([simple_section], "T", "F", theme="light")
        assert fig.get_facecolor() == pytest.approx(
            mpl.colors.to_rgba(DEFAULT_PALETTE["bg"][0]), abs=1e-3
        )

    def test_palette_override_applied(self):
        custom_bg = ("#fafafa", "#010101")
        section = HelpSection("S", [KeyBinding("h", "Help")])
        fig = _build_help_figure(
            [section],
            "T",
            "F",
            theme="dark",
            palette_overrides={"bg": custom_bg},
        )
        assert fig.get_facecolor() == pytest.approx(
            mpl.colors.to_rgba(custom_bg[1]), abs=1e-3
        )

    def test_named_accent_resolved(self):
        section = HelpSection("S", [KeyBinding("h", "Help")], accent="green")
        fig = _build_help_figure([section], "T", "F", theme="dark")
        expected = mpl.colors.to_rgba(DEFAULT_PALETTE["green"][1])
        colours = [p.get_facecolor() for p in fig.axes[0].patches]
        assert any(all(abs(a - b) < 1e-3 for a, b in zip(c, expected)) for c in colours)

    def test_hex_accent_passthrough(self):
        section = HelpSection("S", [KeyBinding("h", "Help")], accent="#ff0000")
        fig = _build_help_figure([section], "T", "F", theme="dark")
        expected = mpl.colors.to_rgba("#ff0000")
        colours = [p.get_facecolor() for p in fig.axes[0].patches]
        assert any(all(abs(a - b) < 1e-3 for a, b in zip(c, expected)) for c in colours)


# ── HelpManager ───────────────────────────────────────────────────────────────


class TestHelpManager:
    def test_add_section_chainable(self, fig):
        mgr = HelpManager(fig)
        assert mgr.add_section(HelpSection("Nav", [])) is mgr

    def test_default_theme_is_dark(self, fig):
        assert HelpManager(fig)._theme == "dark"

    def test_theme_stored(self, fig):
        assert HelpManager(fig, theme="light")._theme == "light"

    def test_palette_stored(self, fig):
        overrides = {"blue": ("#111", "#222")}
        assert HelpManager(fig, palette=overrides)._palette is overrides

    def test_key_column_stored(self, fig):
        mgr = HelpManager(fig, key_column=0.45)
        assert mgr._key_column == 0.45

    def test_key_column_default(self, fig):
        from mpl_help._figure import _DEFAULT_KEY_COL

        assert HelpManager(fig)._key_column == _DEFAULT_KEY_COL

    def test_invalid_theme_raises_on_init(self, fig):
        with pytest.raises(ValueError, match="solarized"):
            HelpManager(fig, theme="solarized")

    def test_default_trigger_key_avoids_matplotlib_bindings(self, fig):
        trigger = HelpManager(fig)._trigger_key
        bound = {
            key
            for param, value in mpl.rcParams.items()
            if param.startswith("keymap.")
            for key in value
        }
        assert trigger not in bound

    def test_invalid_key_column_raises_on_init(self, fig):
        with pytest.raises(ValueError, match="key_column"):
            HelpManager(fig, key_column=1.5)

    def test_invalid_palette_colour_raises_on_init(self, fig):
        with pytest.raises(ValueError, match="not-a-colour"):
            HelpManager(fig, palette={"bg": ("not-a-colour", "#000000")})

    def test_malformed_palette_entry_raises_on_init(self, fig):
        with pytest.raises(ValueError, match="light_hex"):
            HelpManager(fig, palette={"bg": "#000000"})

    def test_invalid_accent_raises(self):
        with pytest.raises(ValueError, match="nosuchcolour"):
            HelpSection("Nav", [KeyBinding("?", "Help")], accent="nosuchcolour")

    def test_managers_do_not_share_a_help_figure(self, simple_section):
        f1, f2 = plt.figure(), plt.figure()
        m1, m2 = HelpManager(f1), HelpManager(f2)
        m1.add_section(simple_section)
        m2.add_section(simple_section)
        m1.show()
        m2.show()
        assert m1._help_fig is not m2._help_fig
        m2._close_help()
        assert m1._help_is_open()

    def test_help_figure_ignores_matplotlib_keymap(self, simple_manager):
        simple_manager.show()
        help_fig = simple_manager._help_fig
        axes = help_fig.axes[0]
        help_fig.canvas.draw()
        width, height = help_fig.canvas.get_width_height()
        KeyEvent(
            "key_press_event", help_fig.canvas, "l", x=width // 2, y=height // 2
        )._process()
        assert axes.get_yscale() == "linear"

    def test_attach_sets_cid(self, fig):
        mgr = HelpManager(fig)
        assert mgr._cid is None
        mgr.attach()
        assert mgr._cid is not None

    def test_attach_idempotent(self, fig):
        mgr = HelpManager(fig)
        mgr.attach()
        cid = mgr._cid
        mgr.attach()
        assert mgr._cid == cid

    def test_detach_clears_cid(self, fig):
        mgr = HelpManager(fig)
        mgr.attach()
        mgr.detach()
        assert mgr._cid is None

    def test_detach_idempotent(self, fig):
        mgr = HelpManager(fig)
        mgr.attach()
        mgr.detach()
        mgr.detach()

    def test_closing_main_figure_closes_help(self, simple_manager, fig):
        simple_manager.attach()
        simple_manager.show()
        assert simple_manager._help_is_open()
        help_fig = simple_manager._help_fig
        _close_window(fig)
        assert not plt.fignum_exists(help_fig.number)
        assert simple_manager._help_fig is None

    def test_closing_main_figure_closes_help_without_attach(self, simple_manager, fig):
        # show() alone, with no attach(), must still arm the close hook.
        simple_manager.show()
        help_fig = simple_manager._help_fig
        _close_window(fig)
        assert not plt.fignum_exists(help_fig.number)

    def test_close_with_figure_disabled_leaves_help_open(self, fig, simple_section):
        mgr = HelpManager(fig, close_with_figure=False)
        mgr.add_section(simple_section)
        mgr.attach()
        mgr.show()
        assert mgr._close_cid is None
        help_fig = mgr._help_fig
        _close_window(fig)
        assert plt.fignum_exists(help_fig.number)
        assert mgr._help_is_open()

    def test_detach_clears_close_cid(self, fig):
        mgr = HelpManager(fig)
        mgr.attach()
        assert mgr._close_cid is not None
        mgr.detach()
        assert mgr._close_cid is None

    def test_close_hook_connected_once(self, simple_manager):
        simple_manager.attach()
        cid = simple_manager._close_cid
        simple_manager.attach()
        simple_manager.show()
        assert simple_manager._close_cid == cid

    def test_closing_main_figure_is_safe_with_no_help_open(self, simple_manager, fig):
        simple_manager.attach()
        _close_window(fig)
        assert simple_manager._help_fig is None

    def test_bulk_close_does_not_double_destroy_help(self, simple_manager, fig):
        """``plt.close("all")`` must not close the help figure itself.

        It destroys the managers in a snapshot of pyplot's registry, so a
        help figure closed from a ``close_event`` raised inside that loop
        is destroyed twice, which the Tk backend raises on.
        """
        from matplotlib._pylab_helpers import Gcf

        simple_manager.attach()
        simple_manager.show()
        help_fig = simple_manager._help_fig
        recorded = []

        class _Probe:
            # Agg emits no close_event, so Gcf.destroy_all on its own cannot
            # reproduce the re-entrant close that GUI backends produce.
            num = "__mpl_help_probe__"
            canvas = fig.canvas
            _cidgcf = fig.canvas.mpl_connect("button_press_event", lambda e: None)

            def destroy(self):
                recorded.append(_closing_all_figures())
                CloseEvent("close_event", fig.canvas)._process()

        Gcf.figs[_Probe.num] = _Probe()
        try:
            plt.close("all")
        finally:
            Gcf.figs.pop(_Probe.num, None)

        assert recorded == [True]
        assert simple_manager._help_fig is help_fig

    def test_closing_all_figures_false_in_normal_flow(self):
        assert _closing_all_figures() is False

    def test_show_opens_figure(self, simple_manager):
        simple_manager.show()
        assert simple_manager._help_is_open()

    def test_keypress_opens_figure(self, simple_manager, fig):
        simple_manager.attach()
        fig.canvas.callbacks.process(
            "key_press_event",
            KeyEvent("key_press_event", fig.canvas, simple_manager._trigger_key),
        )
        assert simple_manager._help_is_open()

    def test_second_keypress_closes_figure(self, simple_manager, fig):
        simple_manager.attach()
        event = KeyEvent("key_press_event", fig.canvas, simple_manager._trigger_key)
        fig.canvas.callbacks.process("key_press_event", event)
        fig.canvas.callbacks.process("key_press_event", event)
        assert not simple_manager._help_is_open()

    def test_wrong_key_does_nothing(self, simple_manager, fig):
        simple_manager.attach()
        fig.canvas.callbacks.process(
            "key_press_event", KeyEvent("key_press_event", fig.canvas, "z")
        )
        assert not simple_manager._help_is_open()

    def test_custom_trigger_key(self, fig):
        mgr = HelpManager(fig, trigger_key="?")
        mgr.add_section(HelpSection("Nav", [KeyBinding("?", "Help")]))
        mgr.attach()
        fig.canvas.callbacks.process(
            "key_press_event", KeyEvent("key_press_event", fig.canvas, "?")
        )
        assert mgr._help_is_open()

    def test_weak_ref_survives_while_in_scope(self, fig):
        mgr = HelpManager(fig)
        mgr.add_section(HelpSection("Nav", [KeyBinding("?", "Help")]))
        mgr.attach()
        fig.canvas.callbacks.process(
            "key_press_event",
            KeyEvent("key_press_event", fig.canvas, mgr._trigger_key),
        )
        assert mgr._help_is_open()

    def test_weak_ref_dies_after_del(self, fig):
        mgr = HelpManager(fig)
        mgr.add_section(HelpSection("Nav", [KeyBinding("h", "Help")]))
        mgr.attach()
        del mgr
        gc.collect()
        # Should not raise
        fig.canvas.callbacks.process(
            "key_press_event", KeyEvent("key_press_event", fig.canvas, "h")
        )


# ── config loaders ────────────────────────────────────────────────────────────

MINIMAL_YAML = """
title: YAML Test
sections:
  - title: General
    accent: green
    bindings:
      - key: h
        desc: Help
"""

MINIMAL_JSON = """{
  "title": "JSON Test",
  "sections": [
    {"title": "General", "bindings": [{"key": "h", "desc": "Help"}]}
  ]
}"""

MINIMAL_DICT = {
    "title": "Dict Test",
    "sections": [
        {"title": "General", "bindings": [{"key": "h", "desc": "Help"}]},
    ],
}


class TestConfigLoaders:
    def test_manager_from_dict_title(self, fig):
        mgr = manager_from_dict(fig, MINIMAL_DICT)
        assert mgr._title == "Dict Test"

    def test_manager_from_dict_theme(self, fig):
        mgr = manager_from_dict(fig, MINIMAL_DICT, theme="light")
        assert mgr._theme == "light"

    def test_manager_from_dict_palette(self, fig):
        overrides = {"blue": ("#111", "#222")}
        mgr = manager_from_dict(fig, MINIMAL_DICT, palette=overrides)
        assert mgr._palette is overrides

    def test_manager_from_dict_sections(self, fig):
        mgr = manager_from_dict(fig, MINIMAL_DICT)
        assert len(mgr._sections) == 1
        assert mgr._sections[0].title == "General"

    def test_accent_stored_as_name(self, fig):
        cfg = {
            "title": "T",
            "sections": [
                {
                    "title": "S",
                    "accent": "blue",
                    "bindings": [{"key": "h", "desc": "Help"}],
                },
            ],
        }
        mgr = manager_from_dict(fig, cfg)
        assert mgr._sections[0].accent == "blue"  # stored as name, not hex

    def test_loads_manager_json(self, fig):
        mgr = loads_manager(fig, MINIMAL_JSON, fmt="json")
        assert mgr._title == "JSON Test"

    @pytest.mark.skipif(
        pytest.importorskip("yaml", reason="pyyaml not installed") is None,
        reason="pyyaml not installed",
    )
    def test_loads_manager_yaml(self, fig):
        pytest.importorskip("yaml")
        mgr = loads_manager(fig, MINIMAL_YAML, fmt="yaml")
        assert mgr._title == "YAML Test"
        assert mgr._sections[0].accent == "green"  # stored as name

    def test_loads_manager_toml(self, fig):
        toml_text = (
            'title = "TOML Test"\n'
            '[[sections]]\ntitle = "General"\n'
            '[[sections.bindings]]\nkey = "h"\ndesc = "Help"\n'
        )
        mgr = loads_manager(fig, toml_text, fmt="toml")
        assert mgr._title == "TOML Test"

    def test_loads_manager_theme_passed(self, fig):
        mgr = loads_manager(fig, MINIMAL_JSON, fmt="json", theme="light")
        assert mgr._theme == "light"

    def test_loads_manager_palette_passed(self, fig):
        overrides = {"bg": ("#fff", "#000")}
        mgr = loads_manager(fig, MINIMAL_JSON, fmt="json", palette=overrides)
        assert mgr._palette is overrides

    def test_unknown_format_raises(self, fig):
        with pytest.raises(ValueError, match="xml"):
            loads_manager(fig, "<help/>", fmt="xml")

    def test_load_manager_from_file(self, fig, tmp_path):
        cfg = tmp_path / "help.json"
        cfg.write_text(MINIMAL_JSON)
        mgr = load_manager(fig, cfg)
        assert mgr._title == "JSON Test"

    def test_load_manager_theme_passed(self, fig, tmp_path):
        cfg = tmp_path / "help.json"
        cfg.write_text(MINIMAL_JSON)
        mgr = load_manager(fig, cfg, theme="light")
        assert mgr._theme == "light"

    def test_load_manager_unknown_extension(self, fig, tmp_path):
        cfg = tmp_path / "help.ini"
        cfg.write_text("[section]")
        with pytest.raises(ValueError, match=".ini"):
            load_manager(fig, cfg)

    def test_key_column_from_config(self, fig):
        cfg = dict(MINIMAL_DICT, key_column=0.45)
        mgr = manager_from_dict(fig, cfg)
        assert mgr._key_column == pytest.approx(0.45)

    def test_key_column_programmatic_overrides_config(self, fig):
        cfg = dict(MINIMAL_DICT, key_column=0.45)
        mgr = manager_from_dict(fig, cfg, key_column=0.35)
        assert mgr._key_column == pytest.approx(0.35)

    def test_key_column_default_when_absent(self, fig):
        from mpl_help._figure import _DEFAULT_KEY_COL

        mgr = manager_from_dict(fig, MINIMAL_DICT)
        assert mgr._key_column == pytest.approx(_DEFAULT_KEY_COL)

        cfg = {
            "title": "T",
            "sections": [
                {"title": "S", "bindings": [{"key": "h", "description": "Help"}]},
            ],
        }
        mgr = manager_from_dict(fig, cfg)
        assert mgr._sections[0].bindings[0].description == "Help"

    def test_trigger_key_respected(self, fig):
        mgr = manager_from_dict(fig, dict(MINIMAL_DICT, trigger_key="x"))
        assert mgr._trigger_key == "x"

    def test_trigger_key_default_matches_package_default(self, fig):
        from mpl_help._figure import _DEFAULT_TRIGGER_KEY

        mgr = manager_from_dict(fig, MINIMAL_DICT)
        assert mgr._trigger_key == _DEFAULT_TRIGGER_KEY

    def test_close_with_figure_default(self, fig):
        mgr = manager_from_dict(fig, MINIMAL_DICT)
        assert mgr._close_with_figure is True

    def test_close_with_figure_from_config(self, fig):
        mgr = manager_from_dict(fig, dict(MINIMAL_DICT, close_with_figure=False))
        assert mgr._close_with_figure is False

    def test_close_with_figure_programmatic_overrides_config(self, fig):
        cfg = dict(MINIMAL_DICT, close_with_figure=False)
        mgr = manager_from_dict(fig, cfg, close_with_figure=True)
        assert mgr._close_with_figure is True

    def test_close_with_figure_through_loads_manager(self, fig):
        mgr = loads_manager(fig, MINIMAL_JSON, fmt="json", close_with_figure=False)
        assert mgr._close_with_figure is False

    def test_close_with_figure_through_load_manager(self, fig, tmp_path):
        path = tmp_path / "help.json"
        path.write_text(json.dumps(dict(MINIMAL_DICT, close_with_figure=False)))
        mgr = load_manager(fig, path)
        assert mgr._close_with_figure is False

    def test_footer_respected(self, fig):
        mgr = manager_from_dict(fig, dict(MINIMAL_DICT, footer="my footer"))
        assert mgr._footer == "my footer"
