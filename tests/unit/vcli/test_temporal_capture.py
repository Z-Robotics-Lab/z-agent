# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: temporal strip capture is env-gated + inert, and the temporal judge fails closed
(ADR-002 Stage 3). No sim is launched — the real strip is proven on a real walk in the demo.
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np

from vector_os_nano.acceptance import capture
from vector_os_nano.acceptance import vision_judge as vj


class _NoBase:
    _base = None


def test_strip_off_without_strip_env(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.delenv("VECTOR_SNAPSHOT_STRIP", raising=False)
    assert capture.capture_strip_frame(_NoBase(), 0) is None  # strip disabled -> no-op


def test_strip_enabled_no_base_is_noop(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setenv("VECTOR_SNAPSHOT_STRIP", "1")
    assert capture.capture_strip_frame(_NoBase(), 0) is None
    assert not (tmp_path / "strip.jsonl").exists()


def test_capture_strip_never_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setenv("VECTOR_SNAPSHOT_STRIP", "1")
    for bad in (None, object(), 123, "x"):
        assert capture.capture_strip_frame(bad, 0) is None


def test_strip_frame_cap_skips_high_idx(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setenv("VECTOR_SNAPSHOT_STRIP", "1")
    calls = []
    monkeypatch.setattr(capture, "_render_agent_frame", lambda *a, **k: calls.append(1) or (0.0, 0.0, 0.0))
    capture.capture_strip_frame(object(), 0)                          # under the cap -> renders
    capture.capture_strip_frame(object(), capture._STRIP_MAX_FRAMES)  # at the cap -> skipped
    assert calls == [1]


def test_load_strip_empty(tmp_path):
    assert capture.load_strip(str(tmp_path)) == []


def test_load_strip_orders_by_idx(tmp_path):
    recs = [{"idx": 2, "x": 2, "y": 0}, {"idx": 0, "x": 0, "y": 0}, {"idx": 1, "x": 1, "y": 0}]
    (tmp_path / "strip.jsonl").write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    assert [r["idx"] for r in capture.load_strip(str(tmp_path))] == [0, 1, 2]


def test_montage_tiles_frames(tmp_path):
    paths = []
    for i in range(3):
        p = str(tmp_path / f"f{i}.png")
        cv2.imwrite(p, np.full((20, 30, 3), 50 + i * 40, np.uint8))
        paths.append(p)
    out = capture.montage(paths, str(tmp_path / "m.png"), cols=2)
    assert out and os.path.exists(out)
    assert cv2.imread(out) is not None


def test_montage_empty_is_none(tmp_path):
    assert capture.montage([], str(tmp_path / "m.png")) is None


def test_sample_evenly_keeps_first_and_last():
    s = capture._sample_evenly(list(range(100)), 5)
    assert s[0] == 0 and s[-1] == 99 and len(s) <= 5


def test_montage_caps_frame_count(tmp_path):
    paths = []
    for i in range(30):
        p = str(tmp_path / f"f{i:03d}.png")
        cv2.imwrite(p, np.full((10, 10, 3), (i * 5) % 255, np.uint8))
        paths.append(p)
    out = capture.montage(paths, str(tmp_path / "m.png"), cols=4, max_frames=12)
    assert out is not None
    img = cv2.imread(out)
    assert img is not None and img.shape[0] <= 10 * 3  # <=12 frames at cols=4 -> at most 3 rows


def test_judge_temporal_fail_closed_on_unreadable():
    v = vj.judge_temporal("/nonexistent/montage.png", call=lambda *a, **k: "{}")
    assert v.witness == vj.ABSTAIN


def test_judge_temporal_canned_pass(tmp_path):
    items = vj.load_temporal_rubric()

    def fake(b64, prompt, *, model, api_key):
        return '{"items": {%s}}' % ",".join(
            f'"{it["key"]}": {{"answer": "yes", "why": "ok"}}' for it in items
        )

    p = str(tmp_path / "m.png")
    cv2.imwrite(p, np.full((8, 8, 3), 120, np.uint8))
    assert vj.judge_temporal(p, call=fake).witness == vj.PASS


def test_temporal_rubric_loads_motion_items():
    keys = {it["key"] for it in vj.load_temporal_rubric()}
    assert {"locomotion_plausible", "no_teleport", "upright_throughout"} <= keys
