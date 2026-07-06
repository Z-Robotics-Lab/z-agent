# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Level 65 — Phase B.2.1: persistent strategy stats.

Acceptance criteria (docs/agent-kernel-phase-b-plan.md, B-3):
- record -> save -> reload round-trips across instances.
- a corrupt file degrades gracefully (resets, no exception).
- save is atomic (temp file + os.replace; no .tmp left behind).
- persistence is opt-in: engine.init_vgg WITHOUT persist_dir stays in memory
  (the experience tier is off, so tests never write to ~/.vector).

Pure kernel logic — no robot, no network, no mujoco fixtures.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from zeno.vcli.cognitive.strategy_stats import _DEFAULT_PATH, StrategyStats


def test_default_path_under_dot_zeno() -> None:
    """Post-rename: the informational default location is under ~/.zeno."""
    assert _DEFAULT_PATH.endswith("/.zeno/strategy_stats.json")


def test_record_save_reload_round_trip(tmp_path: Path) -> None:
    path = str(tmp_path / "stats.json")
    s = StrategyStats(persist_path=path)
    s.record("tool_call", "write_config", success=True, duration_sec=0.5)
    s.record("tool_call", "write_config", success=False, duration_sec=0.2)
    s.record("navigate_skill", "reach_kitchen", success=True, duration_sec=3.0)
    s.save()

    reloaded = StrategyStats(persist_path=path)
    rec = reloaded.get_stats("tool_call", "write_*")
    assert rec is not None
    assert rec.total_attempts == 2
    assert rec.successes == 1
    assert rec.success_rate == 0.5
    assert reloaded.get_stats("navigate_skill", "reach_*").successes == 1


def test_save_is_atomic_no_tmp_left(tmp_path: Path) -> None:
    path = str(tmp_path / "stats.json")
    s = StrategyStats(persist_path=path)
    s.record("tool_call", "write_x", success=True, duration_sec=0.1)
    s.save()
    s.save()  # repeated saves must not accumulate temp files
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []
    assert Path(path).exists()


def test_corrupt_file_degrades_gracefully(tmp_path: Path) -> None:
    path = tmp_path / "stats.json"
    path.write_text("{ this is not valid json")
    s = StrategyStats(persist_path=str(path))  # load() must not raise
    assert s.get_stats("anything", "x_*") is None
    # still usable after a corrupt load
    s.record("tool_call", "write_x", success=True, duration_sec=0.1)
    assert s.get_stats("tool_call", "write_*").successes == 1


def test_in_memory_mode_writes_nothing(tmp_path: Path) -> None:
    s = StrategyStats()  # no path -> in-memory
    s.record("tool_call", "write_x", success=True, duration_sec=0.1)
    s.save()  # no-op
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Engine wiring: persistence is opt-in via persist_dir
# ---------------------------------------------------------------------------


def _engine_with_mock_backend():
    from zeno.vcli.engine import VectorEngine

    backend = MagicMock()
    return VectorEngine(backend=backend, intent_router=MagicMock())


def test_engine_persist_dir_enables_experience_tier(tmp_path: Path) -> None:
    from zeno.vcli.worlds import DevWorld

    eng = _engine_with_mock_backend()
    eng.init_vgg(agent=None, skill_registry=None, world=DevWorld(), persist_dir=tmp_path)
    assert eng._vgg_enabled is True
    assert eng._template_library is not None
    assert eng._experience_compiler is not None


def test_engine_without_persist_dir_stays_in_memory() -> None:
    from zeno.vcli.worlds import DevWorld

    eng = _engine_with_mock_backend()
    eng.init_vgg(agent=None, skill_registry=None, world=DevWorld())
    assert eng._vgg_enabled is True
    # No persist_dir -> no experience tier, no home-dir writes.
    assert eng._template_library is None
    assert eng._experience_compiler is None
