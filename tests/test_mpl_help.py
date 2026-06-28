"""
tests/test_mpl_help.py
======================
Unit tests for mpl-help.  Run with:  pytest
"""

import gc
import sys

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backend_bases import KeyEvent

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
    _make_colour_map,
    _resolve_accent,
    _section_height,
    _total_rows,
)

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

    def test_total_rows_padding(self):
        from mpl_help._figure import _PAD_BOT, _PAD_TOP

        assert _total_rows([]) == pytest.approx(_PAD_TOP + _PAD_BOT)


# ── figure builder ────────────────────────────────────────────────────────────


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

    def test_invalid_theme_raises_on_show(self, fig):
        mgr = HelpManager(fig, theme="solarized")
        mgr.add_section(HelpSection("Nav", [KeyBinding("h", "Help")]))
        with pytest.raises(ValueError, match="solarized"):
            mgr.show()

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

    def test_show_opens_figure(self, simple_manager):
        simple_manager.show()
        assert simple_manager._help_is_open()

    def test_keypress_opens_figure(self, simple_manager, fig):
        simple_manager.attach()
        fig.canvas.callbacks.process(
            "key_press_event", KeyEvent("key_press_event", fig.canvas, "h")
        )
        assert simple_manager._help_is_open()

    def test_second_keypress_closes_figure(self, simple_manager, fig):
        simple_manager.attach()
        event = KeyEvent("key_press_event", fig.canvas, "h")
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
        mgr.add_section(HelpSection("Nav", [KeyBinding("h", "Help")]))
        mgr.attach()
        fig.canvas.callbacks.process(
            "key_press_event", KeyEvent("key_press_event", fig.canvas, "h")
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

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="tomllib stdlib requires Python 3.11+"
    )
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
        mgr = manager_from_dict(fig, dict(MINIMAL_DICT, trigger_key="?"))
        assert mgr._trigger_key == "?"

    def test_footer_respected(self, fig):
        mgr = manager_from_dict(fig, dict(MINIMAL_DICT, footer="my footer"))
        assert mgr._footer == "my footer"
