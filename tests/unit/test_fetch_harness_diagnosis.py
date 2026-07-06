# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit tests for verify_fetch_cli._build_rec diagnosis surfacing.

TDD contract:
  RED  — _build_rec does not exist yet (ImportError / AttributeError).
  GREEN — after extracting _build_rec pure helper into verify_fetch_cli.py,
          all assertions pass without spinning up any simulator.

The helper is pure (no sim, no PTY, no subprocess): it maps
(trial_index, verdict_dict, exit_code) -> rec dict, which is exactly the
per-run record the harness appends to its results list. A fake verdict dict
with per_step entries that carry result_data['diagnosis'] is enough to
exercise it — no real zeno / MuJoCo / LLM needed.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers — shared fake-verdict builders
# ---------------------------------------------------------------------------

def _verdict(per_step=None, evidence="FAILED", verified=False, error=""):
    return {
        "evidence": evidence,
        "verified": verified,
        "error": error,
        "per_step": per_step if per_step is not None else [],
    }


def _step(strategy, success=False, diagnosis=None):
    rd = {}
    if diagnosis is not None:
        rd["diagnosis"] = diagnosis
    return {"strategy": strategy, "success": success, "result_data": rd}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildRec:
    """_build_rec is a pure helper: no sim, no PTY, no network."""

    def _import(self):
        from tools.verify_fetch_cli import _build_rec  # noqa: PLC0415
        return _build_rec

    def test_surfaces_nav_failed_from_last_per_step(self):
        """Single failed nav step -> diagnosis='nav_failed' in rec."""
        _build_rec = self._import()
        v = _verdict(per_step=[_step("navigate_to_object", diagnosis="nav_failed")])
        rec = _build_rec(0, v, 1)
        assert rec["diagnosis"] == "nav_failed"

    def test_surfaces_no_detections_from_last_step(self):
        """Perception failure -> diagnosis='no_detections' in rec."""
        _build_rec = self._import()
        v = _verdict(per_step=[_step("perception_grasp", diagnosis="no_detections")])
        rec = _build_rec(0, v, 2)
        assert rec["diagnosis"] == "no_detections"

    def test_uses_last_step_not_first(self):
        """When multiple steps exist, the LAST step's diagnosis is surfaced."""
        _build_rec = self._import()
        v = _verdict(per_step=[
            _step("look", success=True, diagnosis="ok"),
            _step("navigate_to_object", success=True, diagnosis="ok"),
            _step("perception_grasp", success=False, diagnosis="dock_not_converged"),
        ])
        rec = _build_rec(0, v, 2)
        assert rec["diagnosis"] == "dock_not_converged"

    def test_falls_back_to_verdict_error_when_no_result_data_diagnosis(self):
        """No result_data on last step -> falls back to verdict['error']."""
        _build_rec = self._import()
        # Step has result_data but no 'diagnosis' key.
        v = _verdict(
            per_step=[{"strategy": "mobile_pick", "success": False, "result_data": {}}],
            error="timeout_exceeded",
        )
        rec = _build_rec(0, v, 1)
        assert rec["diagnosis"] == "timeout_exceeded"

    def test_falls_back_to_verdict_error_when_step_has_no_result_data_key(self):
        """Step dict has no 'result_data' key at all -> falls back to verdict error."""
        _build_rec = self._import()
        v = _verdict(
            per_step=[{"strategy": "mobile_pick", "success": False}],
            error="nav_failed",
        )
        rec = _build_rec(0, v, 1)
        assert rec["diagnosis"] == "nav_failed"

    def test_diagnosis_is_none_when_empty_per_step_and_no_error(self):
        """Empty per_step, no error -> diagnosis is None (not a crash)."""
        _build_rec = self._import()
        v = _verdict(per_step=[], evidence="NO_TRACE")
        rec = _build_rec(0, v, 1)
        assert rec["diagnosis"] is None

    def test_rec_contains_all_expected_fields(self):
        """_build_rec always returns i, evidence, verified, strategies, exit, diagnosis."""
        _build_rec = self._import()
        v = _verdict(
            per_step=[_step("perception_grasp", success=False, diagnosis="low_z")],
            evidence="FAILED",
            verified=False,
        )
        rec = _build_rec(7, v, 2)
        assert rec["i"] == 7
        assert rec["evidence"] == "FAILED"
        assert rec["verified"] is False
        assert rec["strategies"] == ["perception_grasp"]
        assert rec["exit"] == 2
        assert rec["diagnosis"] == "low_z"

    def test_success_path_preserves_ok_diagnosis(self):
        """A successful run with diagnosis='ok' from PickTopDown is preserved."""
        _build_rec = self._import()
        v = _verdict(
            per_step=[_step("perception_grasp", success=True, diagnosis="ok")],
            evidence="GROUNDED",
            verified=True,
        )
        rec = _build_rec(0, v, 0)
        assert rec["verified"] is True
        assert rec["diagnosis"] == "ok"
