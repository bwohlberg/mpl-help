"""
tests/test_mpl_help.py
======================
Unit tests for mpl-help.  Run with:  pytest
"""

import gc
import sys
import pytest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.backend_bases import KeyEvent

from mpl_help import (
    HelpManager, HelpSection, KeyBinding,
    load_manager, loads_manager, manager_from_dict,
)
from mpl_help._config import resolve_colour, NAMED_COLOURS
from mpl_help._figure import _build_help_figure, _section_height, _total_rows


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def close_all_figures():
    """Ensure no figures leak between tests."""
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
        accent="#58a6ff",
    )


@pytest.fixture
def simple_manager(fig, simple_section):
    mgr = HelpManager(fig, title="Test Help", footer="test footer")
    mgr.add_section(simple_section)
    return mgr


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

    def test_helpsection_with_accent(self):
        s = HelpSection("Nav", [], accent="#ff0000")
        assert s.accent == "#ff0000"


# ── layout arithmetic ─────────────────────────────────────────────────────────

class TestLayout:
    def test_section_height_no_note(self):
        from mpl_help._figure import _SECTION_HDR, _BINDING_ROW
        s = HelpSection("Nav", [KeyBinding("h", "Help"), KeyBinding("q", "Quit")])
        expected = _SECTION_HDR + 2 * _BINDING_ROW
        assert _section_height(s) == pytest.approx(expected)

    def test_section_height_with_note(self, simple_section):
        from mpl_help._figure import _SECTION_HDR, _BINDING_ROW, _NOTE_ROW
        expected = _SECTION_HDR + 2 * _BINDING_ROW + _NOTE_ROW
        assert _section_height(simple_section) == pytest.approx(expected)

    def test_total_rows_padding(self):
        from mpl_help._figure import _PAD_TOP, _PAD_BOT
        rows = _total_rows([])
        assert rows == pytest.approx(_PAD_TOP + _PAD_BOT)


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

    def test_accent_colour_used(self):
        section = HelpSection("S", [KeyBinding("h", "Help")], accent="#ff0000")
        fig = _build_help_figure([section], "T", "F")
        # At least one patch should use the accent colour
        colours = [p.get_facecolor() for p in fig.axes[0].patches]
        import matplotlib.colors as mcolors
        target = mcolors.to_rgba("#ff0000")
        assert any(
            all(abs(a - b) < 1e-3 for a, b in zip(c, target))
            for c in colours
        )


# ── HelpManager ───────────────────────────────────────────────────────────────

class TestHelpManager:
    def test_add_section_chainable(self, fig):
        mgr = HelpManager(fig)
        result = mgr.add_section(HelpSection("Nav", []))
        assert result is mgr

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
        mgr.detach()   # should not raise

    def test_help_not_open_initially(self, simple_manager):
        assert not simple_manager._help_is_open()

    def test_show_opens_figure(self, simple_manager):
        simple_manager.show()
        assert simple_manager._help_is_open()

    def test_keypress_opens_figure(self, simple_manager, fig):
        simple_manager.attach()
        event = KeyEvent("key_press_event", fig.canvas, "h")
        fig.canvas.callbacks.process("key_press_event", event)
        assert simple_manager._help_is_open()

    def test_second_keypress_closes_figure(self, simple_manager, fig):
        simple_manager.attach()
        event = KeyEvent("key_press_event", fig.canvas, "h")
        fig.canvas.callbacks.process("key_press_event", event)
        assert simple_manager._help_is_open()
        fig.canvas.callbacks.process("key_press_event", event)
        assert not simple_manager._help_is_open()

    def test_wrong_key_does_nothing(self, simple_manager, fig):
        simple_manager.attach()
        event = KeyEvent("key_press_event", fig.canvas, "z")
        fig.canvas.callbacks.process("key_press_event", event)
        assert not simple_manager._help_is_open()

    def test_custom_trigger_key(self, fig):
        mgr = HelpManager(fig, trigger_key="?")
        mgr.add_section(HelpSection("Nav", [KeyBinding("?", "Help")]))
        mgr.attach()
        event = KeyEvent("key_press_event", fig.canvas, "?")
        fig.canvas.callbacks.process("key_press_event", event)
        assert mgr._help_is_open()

    def test_weak_ref_survives_while_in_scope(self, fig):
        """Callback fires while manager is alive."""
        mgr = HelpManager(fig)
        mgr.add_section(HelpSection("Nav", [KeyBinding("h", "Help")]))
        mgr.attach()
        event = KeyEvent("key_press_event", fig.canvas, "h")
        fig.canvas.callbacks.process("key_press_event", event)
        assert mgr._help_is_open()

    def test_weak_ref_dies_after_del(self, fig):
        """Callback silently stops firing after manager is garbage-collected."""
        mgr = HelpManager(fig)
        mgr.add_section(HelpSection("Nav", [KeyBinding("h", "Help")]))
        mgr.attach()
        del mgr
        gc.collect()
        # Fire key — should not raise, but nothing should happen
        event = KeyEvent("key_press_event", fig.canvas, "h")
        fig.canvas.callbacks.process("key_press_event", event)
        # No assertion on open state — manager is gone; just confirm no crash.


# ── colour resolver ───────────────────────────────────────────────────────────

class TestResolveColour:
    def test_named_colours(self):
        for name, expected in NAMED_COLOURS.items():
            assert resolve_colour(name) == expected

    def test_hex_passthrough(self):
        assert resolve_colour("#aabbcc") == "#aabbcc"

    def test_none_passthrough(self):
        assert resolve_colour(None) is None

    def test_unknown_name_passthrough(self):
        assert resolve_colour("notacolour") == "notacolour"


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
    {
      "title": "General",
      "bindings": [{"key": "h", "desc": "Help"}]
    }
  ]
}"""

MINIMAL_DICT = {
    "title": "Dict Test",
    "sections": [
        {"title": "General", "bindings": [{"key": "h", "desc": "Help"}]},
    ],
}


class TestConfigLoaders:
    def test_manager_from_dict(self, fig):
        mgr = manager_from_dict(fig, MINIMAL_DICT)
        assert mgr._title == "Dict Test"
        assert len(mgr._sections) == 1
        assert mgr._sections[0].title == "General"

    def test_loads_manager_json(self, fig):
        mgr = loads_manager(fig, MINIMAL_JSON, fmt="json")
        assert mgr._title == "JSON Test"
        assert len(mgr._sections) == 1

    @pytest.mark.skipif(
        pytest.importorskip("yaml", reason="pyyaml not installed") is None,
        reason="pyyaml not installed",
    )
    def test_loads_manager_yaml(self, fig):
        pytest.importorskip("yaml")
        mgr = loads_manager(fig, MINIMAL_YAML, fmt="yaml")
        assert mgr._title == "YAML Test"
        assert mgr._sections[0].accent == NAMED_COLOURS["green"]

    @pytest.mark.skipif(
        sys.version_info < (3, 11), reason="tomllib stdlib requires Python 3.11+"
    )
    def test_loads_manager_toml(self, fig):
        toml_text = (
            'title = "TOML Test"\n'
            '[[sections]]\n'
            'title = "General"\n'
            '[[sections.bindings]]\n'
            'key = "h"\ndesc = "Help"\n'
        )
        mgr = loads_manager(fig, toml_text, fmt="toml")
        assert mgr._title == "TOML Test"

    def test_unknown_format_raises(self, fig):
        with pytest.raises(ValueError, match="xml"):
            loads_manager(fig, "<help/>", fmt="xml")

    def test_load_manager_from_file(self, fig, tmp_path):
        cfg = tmp_path / "help.json"
        cfg.write_text(MINIMAL_JSON)
        mgr = load_manager(fig, cfg)
        assert mgr._title == "JSON Test"

    def test_load_manager_unknown_extension(self, fig, tmp_path):
        cfg = tmp_path / "help.ini"
        cfg.write_text("[section]")
        with pytest.raises(ValueError, match=".ini"):
            load_manager(fig, cfg)

    def test_desc_alias(self, fig):
        """'description' is accepted as an alias for 'desc'."""
        cfg = {
            "title": "T",
            "sections": [
                {"title": "S", "bindings": [{"key": "h", "description": "Help"}]},
            ],
        }
        mgr = manager_from_dict(fig, cfg)
        assert mgr._sections[0].bindings[0].description == "Help"

    def test_trigger_key_respected(self, fig):
        cfg = dict(MINIMAL_DICT, trigger_key="?")
        mgr = manager_from_dict(fig, cfg)
        assert mgr._trigger_key == "?"

    def test_footer_respected(self, fig):
        cfg = dict(MINIMAL_DICT, footer="my footer")
        mgr = manager_from_dict(fig, cfg)
        assert mgr._footer == "my footer"
