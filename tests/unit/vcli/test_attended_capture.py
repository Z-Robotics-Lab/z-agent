# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: attended real-screen capture is best-effort (never raises) and the launcher-truth judge
folds FAIL when no simulator window is on screen (ADR-002 Stage 4). No real screen is sent to the VLM
here — the end-to-end (real :0 -> VLM) is an owner-watched demo; these pin the logic.
"""
from __future__ import annotations

import cv2
import numpy as np

from zeno.acceptance import capture
from zeno.acceptance import vision_judge as vj


def test_attended_snapshot_bad_display_is_none(tmp_path):
    # an unreachable display -> import fails -> None, never raises
    assert capture.attended_snapshot(str(tmp_path / "s.png"), display=":99", timeout=6) is None


def test_attended_record_bad_display_is_none(tmp_path):
    assert capture.attended_record(str(tmp_path / "r.mp4"), 1, display=":99", timeout=10) is None


def test_attended_rubric_loads_launcher_truth_items():
    keys = {it["key"] for it in vj.load_attended_rubric()}
    assert "simulator_window_present" in keys and "robot_visible_on_screen" in keys


def test_judge_attended_fail_closed_on_error():
    v = vj.judge_attended("/nonexistent/screen.png", call=lambda *a, **k: "{}")
    assert v.witness == vj.ABSTAIN


def test_judge_attended_no_sim_window_is_fail(tmp_path):
    """A bypassed launcher (desktop only, no sim window) -> FAIL — the launcher-truth catch."""
    def fake(b64, prompt, *, model, api_key):
        return (
            '{"items": {"simulator_window_present": {"answer": "no", "why": "desktop only"}, '
            '"robot_visible_on_screen": {"answer": "no", "why": "no sim window"}}}'
        )

    p = str(tmp_path / "x.png")
    cv2.imwrite(p, np.full((8, 8, 3), 120, np.uint8))
    assert vj.judge_attended(p, call=fake).witness == vj.FAIL


def test_judge_attended_sim_window_present_is_pass(tmp_path):
    def fake(b64, prompt, *, model, api_key):
        return (
            '{"items": {"simulator_window_present": {"answer": "yes", "why": "mujoco viewer open"}, '
            '"robot_visible_on_screen": {"answer": "yes", "why": "a quadruped in the scene"}}}'
        )

    p = str(tmp_path / "x.png")
    cv2.imwrite(p, np.full((8, 8, 3), 120, np.uint8))
    assert vj.judge_attended(p, call=fake).witness == vj.PASS


def test_launcher_truth_requires_consent_before_vlm_send(monkeypatch, tmp_path):
    """PRIVACY: the owner's screen is sent to the external VLM ONLY with explicit consent — never
    silently from an automated path (security.md: confirm before outward-facing actions)."""
    from tools.acceptance import attended

    monkeypatch.setattr(attended.capture, "attended_snapshot", lambda *a, **k: str(tmp_path / "screen.png"))
    sent = []
    monkeypatch.setattr(
        attended.vj, "judge_attended",
        lambda *a, **k: sent.append("SENT") or attended.vj.VisionVerdict("PASS", (), "", "x"),
    )
    monkeypatch.delenv("VECTOR_ATTENDED_CONSENT", raising=False)

    r = attended.launcher_truth(str(tmp_path))  # no consent -> grab locally, DO NOT send
    assert sent == [] and r["witness"] is None and "consent" in r["reason"].lower()

    r2 = attended.launcher_truth(str(tmp_path), consent=True)  # explicit consent -> sends
    assert sent == ["SENT"] and r2["witness"] == "PASS"
