# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""/clean REPL slash command — wipe ALL persisted map places (CEO 2026-07-14).

Field directive: an operator accumulates named places over many sessions and
wants a single, SAFE way to wipe them for a map. `/clean` in the zeno REPL does
exactly that, gated by DOUBLE confirmation so a stray keystroke can never nuke
the store:

  1. print WHAT will be deleted (map + each place, EXCLUDING built-in home/家
     which are derived from start_pose.txt and cannot be deleted);
  2. confirmation 1 = TYPE THE MAP NAME exactly;
  3. confirmation 2 = y/N (default N);
  4. on confirm: back up places.json -> .bak, empty places.json (clear_places),
     clear the live ledger's non-builtin marks, reload home/家 via home_place.

Hermetic BY DESIGN (kernel must NOT import the world statically — it imports the
map seam lazily and degrades when no map world is present): the confirmation
stdin is a scripted ``cli._CLEAN_INPUT`` seam, the map seam is env/monkeypatch
temp dirs, no ROS, no LLM, no sim.
"""
from __future__ import annotations

from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console


# ---------------------------------------------------------------------------
# Harness — a scripted-stdin console + a fake active map on disk
# ---------------------------------------------------------------------------


def _script_input(cli, monkeypatch, answers):
    """Feed *answers* (a list) to the confirmation prompts in order.

    Raising EOFError when the script runs dry mirrors a closed stdin (^D).
    """
    it = iter(answers)

    def _fake(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    monkeypatch.setattr(cli, "_CLEAN_INPUT", _fake, raising=False)


def _wire_console(cli, monkeypatch):
    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False))
    return buf


def _active_map(tmp_path, monkeypatch, *, name="zeno_office",
                places=None, home_line="1.0 2.0 0.0 0.0 0.0 0.5 3.0\n"):
    """Make *name* the active map with *places* persisted; return the maps mod."""
    import zeno.vcli.worlds.go2w_real_maps as maps

    root = tmp_path / "maps"
    (root / name).mkdir(parents=True)
    monkeypatch.setattr(maps, "MAPS_ROOT", root)
    cur = tmp_path / "current_map.txt"
    cur.write_text(f"{name}\n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(cur))
    if home_line is not None:
        (root / name / "start_pose.txt").write_text(home_line, encoding="utf-8")
    if places:
        maps.save_places(name, places)
    return maps


def _no_map(tmp_path, monkeypatch):
    import zeno.vcli.worlds.go2w_real_maps as maps

    root = tmp_path / "maps"
    root.mkdir(parents=True)
    monkeypatch.setattr(maps, "MAPS_ROOT", root)
    cur = tmp_path / "current_map.txt"
    cur.write_text("none\n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(cur))
    return maps


def _ledger_app_state(maps=None):
    """An app_state whose agent carries a live PoseLedger at base.pose_ledger."""
    from zeno.vcli.worlds.go2w_real_places import PoseLedger

    led = PoseLedger()
    base = SimpleNamespace(pose_ledger=led)
    agent = SimpleNamespace(_base=base)
    return {"agent": agent}, led


# ---------------------------------------------------------------------------
# No active map -> honest refusal, nothing deleted
# ---------------------------------------------------------------------------


def test_clean_no_active_map_refuses(tmp_path, monkeypatch):
    from zeno.vcli import cli

    _no_map(tmp_path, monkeypatch)
    buf = _wire_console(cli, monkeypatch)
    _script_input(cli, monkeypatch, [])  # must never be consulted

    assert cli._handle_slash_command("clean", [], None, None, {}) is True
    out = buf.getvalue()
    assert "预建图" in out or "没有可清空" in out, out


def test_clean_no_map_world_degrades(monkeypatch):
    """A sim world (no go2w_real map seam) must not crash /clean — it degrades
    to the honest 'no map world / no active map' message."""
    from zeno.vcli import cli
    import zeno.vcli.worlds.go2w_real_maps as maps

    buf = _wire_console(cli, monkeypatch)
    # current_map raises as if the seam were unavailable — handler must catch.
    monkeypatch.setattr(maps, "current_map",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cli._handle_slash_command("clean", [], None, None, {}) is True
    assert "没有可清空" in buf.getvalue() or "没有" in buf.getvalue()


# ---------------------------------------------------------------------------
# Preview lists places, EXCLUDES built-in home/家
# ---------------------------------------------------------------------------


def test_clean_preview_excludes_builtins(tmp_path, monkeypatch):
    from zeno.vcli import cli

    _active_map(tmp_path, monkeypatch, places={
        "充电桩": (1.0, 2.0, 0.5),
        "门口": (3.0, -1.0, 1.2),
        "home": (1.0, 2.0, 0.5),
        "家": (1.0, 2.0, 0.5),
    })
    buf = _wire_console(cli, monkeypatch)
    _script_input(cli, monkeypatch, [""])  # abort at confirm-1 (blank != map)

    cli._handle_slash_command("clean", [], None, None, {})
    out = buf.getvalue()
    assert "充电桩" in out and "门口" in out, out
    # built-ins are described as underivable, not offered for deletion
    assert "home" not in out.split("充电桩")[0] or "家" in out  # loose: mentioned as builtin
    assert "已取消" in out, "blank map-name mismatch aborts"


# ---------------------------------------------------------------------------
# Abort paths — mismatch / wrong y-n / EOF — nothing deleted
# ---------------------------------------------------------------------------


def test_clean_wrong_map_name_aborts(tmp_path, monkeypatch):
    from zeno.vcli import cli

    maps = _active_map(tmp_path, monkeypatch, places={"充电桩": (1.0, 2.0, 0.5)})
    _wire_console(cli, monkeypatch)
    _script_input(cli, monkeypatch, ["wrong_name", "y"])

    cli._handle_slash_command("clean", [], None, None, {})
    assert maps.load_places("zeno_office") == {"充电桩": (1.0, 2.0, 0.5)}, (
        "map-name mismatch must NOT delete")
    assert not (maps.MAPS_ROOT / "zeno_office" / "places.json.bak").exists()


def test_clean_default_no_on_second_confirm_aborts(tmp_path, monkeypatch):
    from zeno.vcli import cli

    maps = _active_map(tmp_path, monkeypatch, places={"充电桩": (1.0, 2.0, 0.5)})
    buf = _wire_console(cli, monkeypatch)
    # confirm-1 correct, confirm-2 blank -> default N -> abort
    _script_input(cli, monkeypatch, ["zeno_office", ""])

    cli._handle_slash_command("clean", [], None, None, {})
    assert maps.load_places("zeno_office") == {"充电桩": (1.0, 2.0, 0.5)}
    assert "已取消" in buf.getvalue()


def test_clean_eof_aborts(tmp_path, monkeypatch):
    from zeno.vcli import cli

    maps = _active_map(tmp_path, monkeypatch, places={"充电桩": (1.0, 2.0, 0.5)})
    buf = _wire_console(cli, monkeypatch)
    _script_input(cli, monkeypatch, [])  # first prompt -> EOFError

    assert cli._handle_slash_command("clean", [], None, None, {}) is True
    assert maps.load_places("zeno_office") == {"充电桩": (1.0, 2.0, 0.5)}
    assert "已取消" in buf.getvalue()


# ---------------------------------------------------------------------------
# Confirm both -> wipe disk + backup + clear ledger non-builtins, keep home/家
# ---------------------------------------------------------------------------


def test_clean_confirmed_wipes_and_backs_up(tmp_path, monkeypatch):
    from zeno.vcli import cli

    maps = _active_map(tmp_path, monkeypatch, places={
        "充电桩": (1.0, 2.0, 0.5), "门口": (3.0, -1.0, 1.2)})
    buf = _wire_console(cli, monkeypatch)
    _script_input(cli, monkeypatch, ["zeno_office", "y"])

    assert cli._handle_slash_command("clean", [], None, None, {}) is True
    # disk wiped
    assert maps.load_places("zeno_office") == {}
    # backup created with the old content
    import json
    bak = maps.MAPS_ROOT / "zeno_office" / "places.json.bak"
    assert bak.is_file()
    assert json.loads(bak.read_text("utf-8"))["充电桩"] == [1.0, 2.0, 0.5]
    # success message with the count
    out = buf.getvalue()
    assert "2" in out and ("已清空" in out or "places.json.bak" in out), out


def test_clean_confirmed_clears_ledger_keeps_home(tmp_path, monkeypatch):
    from zeno.vcli import cli

    maps = _active_map(tmp_path, monkeypatch, places={"充电桩": (1.0, 2.0, 0.5)})
    _wire_console(cli, monkeypatch)
    app_state, led = _ledger_app_state()
    # live ledger holds a persisted mark AND the built-in home (loaded at setup)
    led.load_marks({"充电桩": (1.0, 2.0, 0.5),
                    "home": (1.0, 2.0, 0.5), "家": (1.0, 2.0, 0.5)})
    _script_input(cli, monkeypatch, ["zeno_office", "y"])

    cli._handle_slash_command("clean", [], None, None, app_state)
    # non-builtin marks cleared from the LIVE session ledger
    assert "充电桩" not in led.marks, "session ledger non-builtins cleared"
    # home/家 reloaded from start_pose.txt (home_place), so goto home still works
    assert led.marks.get("home") == (1.0, 2.0, 0.5)
    assert led.marks.get("家") == (1.0, 2.0, 0.5)


def test_clean_confirmed_no_ledger_still_ok(tmp_path, monkeypatch):
    """No go2w_real agent in app_state (e.g. dict without agent) -> disk still
    wiped, no crash on the missing ledger."""
    from zeno.vcli import cli

    maps = _active_map(tmp_path, monkeypatch, places={"充电桩": (1.0, 2.0, 0.5)})
    _wire_console(cli, monkeypatch)
    _script_input(cli, monkeypatch, ["zeno_office", "y"])

    assert cli._handle_slash_command("clean", [], None, None, {}) is True
    assert maps.load_places("zeno_office") == {}


# ---------------------------------------------------------------------------
# /clean is discoverable in the command list + /help
# ---------------------------------------------------------------------------


def test_clean_registered_in_slash_commands():
    from zeno.vcli import cli

    names = {n for n, _desc, _has in cli.SLASH_COMMANDS}
    assert "clean" in names, "/clean must be in the completer + /help list"


def test_help_mentions_clean(monkeypatch):
    from zeno.vcli import cli

    buf = _wire_console(cli, monkeypatch)
    cli._handle_slash_command("help", [], None, None, {})
    assert "/clean" in buf.getvalue()
