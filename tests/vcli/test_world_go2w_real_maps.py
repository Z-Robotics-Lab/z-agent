# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real pre-built map integration — bringup map param, current-map
handshake, persistent named places, and the 3D view seam (RED first).

CONTEXT (CEO 2026-07-14): pre-built-map relocalization is LIVE.
``~/maps/zeno_office/`` holds the nav/viz PCDs + ``start_pose.txt`` (line 1 =
home pose). ``nav.sh start <map>`` -> arise_slam localization. This suite pins
the z-agent WORLD half:

TASK 1 — DEFAULT-MAP BRINGUP: RealBringupSkill + Go2WRealBringupTool action=
  start gain an optional ``map`` param. Resolution: explicit name wins; explicit
  从零/none/'' = plain start; DEFAULT (unspecified) = env GO2W_DEFAULT_MAP, else
  'zeno_office' IF its PCD exists, else plain. argv = ['bash', nav.sh, 'start',
  <map>] in map mode; ['bash', nav.sh, 'start'] plain.
TASK 2 — CURRENT-MAP HANDSHAKE: the current_map helper reads the active map name
  from ``current_map.txt`` (env GO2W_CURRENT_MAP_FILE override); 'none'/missing
  = None. (nav.sh writes the file; that is the go2w-nuc repo's own commit.)
TASK 3 — PERSISTENT PLACES: PoseLedger.save_marks/load_marks <-> ~/maps/<map>/
  places.json (atomic tmp+rename; schema {name: [x, y, yaw]}). mark_place saves
  when a map is active; setup() loads marks + injects 'home'/'家' from
  start_pose.txt.
TASK 4 — 3D VIEW SEAM: open_viz view=3d launches view3d.sh through the same
  OverlayLauncher machinery.

Hermetic: fake driver, env-pointed temp files, no ROS env, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# TASK 2 — current-map helper (also the seam Tasks 1/3 lean on)
# ---------------------------------------------------------------------------


def _maps():
    import zeno.vcli.worlds.go2w_real_maps as m

    return m


def test_current_map_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(tmp_path / "gone.txt"))
    assert _maps().current_map() is None


def test_current_map_reads_active_map_name(tmp_path, monkeypatch):
    f = tmp_path / "current_map.txt"
    f.write_text("zeno_office\n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(f))
    assert _maps().current_map() == "zeno_office"


def test_current_map_none_literal_means_no_map(tmp_path, monkeypatch):
    f = tmp_path / "current_map.txt"
    f.write_text("none\n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(f))
    assert _maps().current_map() is None


def test_current_map_blank_file_is_none(tmp_path, monkeypatch):
    f = tmp_path / "current_map.txt"
    f.write_text("   \n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(f))
    assert _maps().current_map() is None


# ---------------------------------------------------------------------------
# TASK 1 — bringup map resolution
# ---------------------------------------------------------------------------


def _fake_maps_root(tmp_path: Path, *names: str) -> Path:
    """Create ~/maps/<name>/<name>.pcd stubs; return the maps root."""
    root = tmp_path / "maps"
    for n in names:
        d = root / n
        d.mkdir(parents=True)
        (d / f"{n}.pcd").write_text("stub", encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_resolve_bringup_map_explicit_name_wins(tmp_path, monkeypatch):
    root = _fake_maps_root(tmp_path, "zeno_office", "warehouse")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    monkeypatch.delenv("GO2W_DEFAULT_MAP", raising=False)
    assert _maps().resolve_bringup_map("warehouse") == "warehouse"


def test_resolve_bringup_map_from_zero_is_plain(tmp_path, monkeypatch):
    root = _fake_maps_root(tmp_path, "zeno_office")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    for word in ("从零", "none", ""):
        assert _maps().resolve_bringup_map(word) is None, word


def test_resolve_bringup_map_default_is_zeno_office_when_pcd_exists(
        tmp_path, monkeypatch):
    root = _fake_maps_root(tmp_path, "zeno_office")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    monkeypatch.delenv("GO2W_DEFAULT_MAP", raising=False)
    # unspecified -> the built-in default map (its PCD exists)
    assert _maps().resolve_bringup_map(None) == "zeno_office"


def test_resolve_bringup_map_default_env_overrides(tmp_path, monkeypatch):
    root = _fake_maps_root(tmp_path, "zeno_office", "warehouse")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    monkeypatch.setenv("GO2W_DEFAULT_MAP", "warehouse")
    assert _maps().resolve_bringup_map(None) == "warehouse"


def test_resolve_bringup_map_default_plain_when_no_pcd(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    root.mkdir()
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    monkeypatch.delenv("GO2W_DEFAULT_MAP", raising=False)
    # no zeno_office.pcd -> fall back to plain fresh mapping
    assert _maps().resolve_bringup_map(None) is None


def test_resolve_bringup_map_env_none_is_plain(tmp_path, monkeypatch):
    root = _fake_maps_root(tmp_path, "zeno_office")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    monkeypatch.setenv("GO2W_DEFAULT_MAP", "none")
    assert _maps().resolve_bringup_map(None) is None


# ---------------------------------------------------------------------------
# TASK 1 — bringup SKILL passes the resolved map into nav.sh argv
# ---------------------------------------------------------------------------


class _FakeHW:
    def __init__(self):
        self.explore_manager = None
        self.route_manager = None


def _ctx(base=None, services=None, instruction=""):
    return SimpleNamespace(base=base, services=services or {},
                           instruction=instruction)


def _bringup(runner_rc=0, ready=True, already=False):
    from zeno.vcli.worlds.go2w_real_lifecycle import RealBringupSkill
    calls: list[list[str]] = []

    def runner(argv, timeout):  # noqa: ARG001
        calls.append(list(argv))
        return SimpleNamespace(returncode=runner_rc, stdout="", stderr="")

    skill = RealBringupSkill(runner=runner, ready_poller=lambda hw, t: ready,
                             ready_probe=lambda hw: already)
    return skill, calls


def test_bringup_skill_explicit_map_reaches_nav_sh(tmp_path, monkeypatch):
    root = _fake_maps_root(tmp_path, "zeno_office")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    skill, calls = _bringup(already=False)
    result = skill.execute({"action": "start", "map": "zeno_office"},
                           _ctx(base=_FakeHW()))
    assert result.success, result.error_message
    assert calls[0][0] == "bash"
    assert calls[0][1].endswith("nav.sh")
    assert calls[0][2] == "start"
    assert calls[0][3] == "zeno_office"
    assert "zeno_office" in str(result.result_data or {})
    assert "重定位" in str(result.result_data or {})


def test_bringup_skill_from_zero_is_plain_start(tmp_path, monkeypatch):
    root = _fake_maps_root(tmp_path, "zeno_office")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    skill, calls = _bringup(already=False)
    result = skill.execute({"action": "start", "map": "从零"},
                           _ctx(base=_FakeHW()))
    assert result.success
    assert calls[0][-1] == "start", "从零 = plain nav.sh start, no map arg"
    assert "从零建图" in str(result.result_data or {})


def test_bringup_skill_default_uses_zeno_office(tmp_path, monkeypatch):
    root = _fake_maps_root(tmp_path, "zeno_office")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    monkeypatch.delenv("GO2W_DEFAULT_MAP", raising=False)
    skill, calls = _bringup(already=False)
    result = skill.execute({"action": "start"}, _ctx(base=_FakeHW()))
    assert result.success
    assert calls[0][-1] == "zeno_office", "unspecified default -> zeno_office"


def test_bringup_skill_default_plain_when_no_map(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    root.mkdir()
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    monkeypatch.delenv("GO2W_DEFAULT_MAP", raising=False)
    skill, calls = _bringup(already=False)
    result = skill.execute({"action": "start"}, _ctx(base=_FakeHW()))
    assert result.success
    assert calls[0][-1] == "start", "no default map available -> plain start"


# ---------------------------------------------------------------------------
# TASK 1 — bringup TOOL gains the map param
# ---------------------------------------------------------------------------


def test_bringup_tool_schema_has_map_param():
    from zeno.vcli.worlds.go2w_real_tools import Go2WRealBringupTool
    schema = Go2WRealBringupTool.input_schema
    assert "map" in schema["properties"], "bringup tool must accept map"


# ---------------------------------------------------------------------------
# TASK 3 — persistent named places (places.json)
# ---------------------------------------------------------------------------


def test_places_json_roundtrip_named_marks(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    (root / "zeno_office").mkdir(parents=True)
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    from zeno.vcli.worlds.go2w_real_places import PoseLedger

    led = PoseLedger()
    led.mark("充电桩", (1.0, 2.0, 0.5))
    led.mark("门口", (3.0, -1.0, 1.2))
    _maps().save_places("zeno_office", led.marks)

    path = root / "zeno_office" / "places.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["充电桩"] == [1.0, 2.0, 0.5]

    led2 = PoseLedger()
    loaded = _maps().load_places("zeno_office")
    led2.load_marks(loaded)
    assert led2.marks["充电桩"] == (1.0, 2.0, 0.5)
    assert led2.marks["门口"] == (3.0, -1.0, 1.2)


def test_save_places_is_atomic_tmp_rename(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    (root / "zeno_office").mkdir(parents=True)
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    _maps().save_places("zeno_office", {"a": (1.0, 2.0, 0.0)})
    # no leftover tmp files beside the final places.json
    leftovers = [p.name for p in (root / "zeno_office").iterdir()
                 if p.name != "places.json"]
    assert leftovers == [], f"atomic write left temp files: {leftovers}"


def test_load_places_missing_file_is_empty(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    (root / "zeno_office").mkdir(parents=True)
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    assert _maps().load_places("zeno_office") == {}


def test_load_places_corrupt_file_is_empty(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    (root / "zeno_office").mkdir(parents=True)
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    (root / "zeno_office" / "places.json").write_text("{bad json",
                                                      encoding="utf-8")
    assert _maps().load_places("zeno_office") == {}, "corrupt -> empty, no raise"


def test_load_marks_does_not_clobber_breadcrumbs():
    from zeno.vcli.worlds.go2w_real_places import PoseLedger

    led = PoseLedger()
    led.push_breadcrumb((9.0, 9.0, 0.0))
    led.load_marks({"充电桩": (1.0, 2.0, 0.5)})
    assert led.marks["充电桩"] == (1.0, 2.0, 0.5)
    assert led.breadcrumbs, "loading marks must not touch session breadcrumbs"


# ---------------------------------------------------------------------------
# TASK 3 — mark_place persists when a map is active
# ---------------------------------------------------------------------------


class _PlacesFakeHW:
    def __init__(self, x=0.0, y=0.0, yaw=0.0, age=0.4):
        from zeno.vcli.worlds.go2w_real_course import CourseTracker
        from zeno.vcli.worlds.go2w_real_places import PoseLedger

        self.estop_latched = False
        self._pos = [float(x), float(y), 0.0]
        self._yaw = float(yaw)
        self._age = age
        self.pose_ledger = PoseLedger()
        self.course_tracker = CourseTracker()

    def get_position(self):
        return list(self._pos)

    def get_heading(self):
        return self._yaw

    def odom_age_s(self):
        return self._age


def test_mark_place_persists_when_map_active(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    (root / "zeno_office").mkdir(parents=True)
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    cur = tmp_path / "current_map.txt"
    cur.write_text("zeno_office\n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(cur))

    from zeno.vcli.worlds.go2w_real_places import RealMarkPlaceSkill

    hw = _PlacesFakeHW(x=1.5, y=-2.0, yaw=0.7)
    result = RealMarkPlaceSkill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert result.success
    data = json.loads((root / "zeno_office" / "places.json").read_text("utf-8"))
    assert data["充电桩"] == pytest.approx([1.5, -2.0, 0.7])


def test_mark_place_session_only_when_no_map(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    (root / "zeno_office").mkdir(parents=True)
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    cur = tmp_path / "current_map.txt"
    cur.write_text("none\n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(cur))

    from zeno.vcli.worlds.go2w_real_places import RealMarkPlaceSkill

    hw = _PlacesFakeHW(x=1.0, y=1.0)
    result = RealMarkPlaceSkill().execute({"name": "临时点"}, _ctx(base=hw))
    assert result.success
    assert not (root / "zeno_office" / "places.json").exists(), (
        "fresh-mapping mode = session-only, nothing written to disk")


# ---------------------------------------------------------------------------
# TASK 3 — home place from start_pose.txt
# ---------------------------------------------------------------------------


def test_home_place_reads_start_pose_line1(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    d = root / "zeno_office"
    d.mkdir(parents=True)
    # x y z roll pitch yaw dur
    (d / "start_pose.txt").write_text(
        "-0.059 0.015 -0.013 -0.0021 -0.0099 -0.0059 0\n", encoding="utf-8")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    home = _maps().home_place("zeno_office")
    assert home is not None
    x, y, yaw = home
    assert x == pytest.approx(-0.059)
    assert y == pytest.approx(0.015)
    assert yaw == pytest.approx(-0.0059)


def test_home_place_missing_file_is_none(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    (root / "zeno_office").mkdir(parents=True)
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    assert _maps().home_place("zeno_office") is None


# ---------------------------------------------------------------------------
# TASK 3 — setup() loads persisted marks + injects home when a map is active
# ---------------------------------------------------------------------------


def test_setup_loads_marks_and_injects_home_when_map_active(
        tmp_path, monkeypatch):
    root = tmp_path / "maps"
    d = root / "zeno_office"
    d.mkdir(parents=True)
    (d / "places.json").write_text(
        json.dumps({"充电桩": [1.0, 2.0, 0.5]}), encoding="utf-8")
    (d / "start_pose.txt").write_text(
        "-0.059 0.015 -0.013 0 0 -0.0059 0\n", encoding="utf-8")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    cur = tmp_path / "current_map.txt"
    cur.write_text("zeno_office\n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(cur))

    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    world = Go2WRealWorld()
    emb = world.build_embodiment()
    # A base that never connects to ROS (connect is a no-op) — setup must still
    # load places without a live driver.
    emb._base.connect = lambda: None  # noqa: SLF001
    agent = SimpleNamespace(_base=emb._base)
    world.setup(agent)

    marks = emb._base.pose_ledger.marks
    assert marks.get("充电桩") == (1.0, 2.0, 0.5), "persisted mark loaded"
    assert "home" in marks or "家" in marks, "built-in home place injected"
    home = marks.get("home") or marks.get("家")
    assert home[0] == pytest.approx(-0.059)


def test_setup_no_map_leaves_ledger_empty(tmp_path, monkeypatch):
    root = tmp_path / "maps"
    (root / "zeno_office").mkdir(parents=True)
    (root / "zeno_office" / "places.json").write_text(
        json.dumps({"充电桩": [1.0, 2.0, 0.5]}), encoding="utf-8")
    monkeypatch.setattr(_maps(), "MAPS_ROOT", root)
    cur = tmp_path / "current_map.txt"
    cur.write_text("none\n", encoding="utf-8")
    monkeypatch.setenv("GO2W_CURRENT_MAP_FILE", str(cur))

    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    world = Go2WRealWorld()
    emb = world.build_embodiment()
    emb._base.connect = lambda: None  # noqa: SLF001
    world.setup(SimpleNamespace(_base=emb._base))
    assert emb._base.pose_ledger.marks == {}, (
        "no active map -> no persisted places loaded (fresh-mapping session)")


# ---------------------------------------------------------------------------
# TASK 4 — open_viz view=3d launches view3d.sh
# ---------------------------------------------------------------------------


from tests.unit.hardware.test_go2w_hw_overlay import (  # noqa: E402
    FakePopenFactory,
    FakeProc,
)


def _nav_sh(tmp_path: Path) -> str:
    p = tmp_path / "nav.sh"
    p.write_text("#!/usr/bin/env bash\n")
    return str(p)


def _session(tmp_path: Path, factory: FakePopenFactory | None = None):
    from zeno.vcli.worlds.go2w_real_viz_tools import VizOverlaySession

    return VizOverlaySession(
        popen_factory=factory or FakePopenFactory(),
        nav_sh=_nav_sh(tmp_path))


def test_viz_3d_view_launches_view3d_script(tmp_path):
    factory = FakePopenFactory()
    session = _session(tmp_path, factory)
    status, _detail = session.open("3d")
    assert status == "opened", status
    (argv, _kwargs), = factory.calls
    assert argv[0] == "bash"
    assert argv[1].endswith("view3d.sh"), argv
    # view3d.sh takes no nav.sh subcommand — the script IS the whole command
    assert "rviz" not in argv


def test_viz_3d_dedupes_and_close_all_still_works(tmp_path):
    factory = FakePopenFactory(FakeProc(exits_on_sigint=1))
    session = _session(tmp_path, factory)
    assert session.open("3d")[0] == "opened"
    assert session.open("3d")[0] == "already_open", "3d view must dedupe"
    assert len(factory.calls) == 1
    closed, stuck = session.close_all()
    assert "3d" in closed and stuck == []


def test_viz_3d_skill_view_param(tmp_path):
    from zeno.vcli.worlds.go2w_real_ops_skills import RealVizSkill

    factory = FakePopenFactory()
    session = _session(tmp_path, factory)
    result = RealVizSkill().execute(
        {"view": "3d"}, _ctx(services={"viz": session}))
    assert result.success, result.error_message
    assert factory.calls[0][0][1].endswith("view3d.sh")


def test_viz_tool_schema_allows_3d():
    from zeno.vcli.worlds.go2w_real_viz_tools import Go2WRealVizTool

    view_enum = Go2WRealVizTool.input_schema["properties"]["view"]["enum"]
    assert "3d" in view_enum


# ---------------------------------------------------------------------------
# card + vocab honesty updates
# ---------------------------------------------------------------------------


def _capability_md() -> str:
    import zeno.vcli.worlds.go2w_real as w

    return Path(w.__file__).with_name("go2w_real_capabilities.md").read_text(
        encoding="utf-8")


def test_card_documents_persistent_places_on_prebuilt_map():
    text = _capability_md()
    assert "预建图模式下地点跨重启有效" in text, (
        "card must say places PERSIST on a pre-built map")


def test_card_documents_3d_view():
    text = _capability_md()
    assert "3D" in text and "Foxglove" in text
