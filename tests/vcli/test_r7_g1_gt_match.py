# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R7 — the HONEST GROUNDED for g1: GT-backed perception match (NOT a self-read).

These tests lock in the honesty CONTRACT of ``detection_matches_gt`` at unit level
(no real model / no GL render) with a stubbed segmentation GT + a stubbed detector:

  - CORRECT localization (box center on the seg centroid)         -> True  (GROUNDED-eligible)
  - WRONG box (box on a wall, far from the seg centroid)          -> False (RAN)   [REFUTATION]
  - object OUT OF VIEW (no matching-colour geom in segmentation)  -> False (RAN)   [REFUTATION]
  - the detector input is RGB ONLY — the segmentation GT is never handed to it (firewall)

and that the spine grades ``detection_matches_gt('red') == True`` GROUNDED while a
bare call / a short-circuit stays RAN (the spine is byte-unchanged; this just pins it).
"""

from __future__ import annotations

import numpy as np

import vector_os_nano.vcli.worlds.g1_perception_oracle as oracle_mod
from vector_os_nano.vcli.worlds.g1_perception_oracle import make_detection_matches_gt

# The independent GT: the red object's segmentation centroid in the rendered frame.
_SEG_CENTROID = (321.0, 260.0, 919)  # (u, v, px) — matches the real spawn-view stool


class _Box:
    def __init__(self, x1, y1, x2, y2):
        self.bbox = (x1, y1, x2, y2)
        self.label = "red"
        self.confidence = 0.5


class _StubDetector:
    """Boxes the test chooses; RECORDS what it was handed — must be ONLY RGB (firewall)."""

    def __init__(self, boxes):
        self._boxes = boxes
        self.seen_rgb_shapes: list = []
        self.seen_extra_args: list = []

    def detect(self, rgb, query, *extra):
        assert isinstance(rgb, np.ndarray), "detector must receive an RGB array"
        self.seen_rgb_shapes.append(rgb.shape)
        self.seen_extra_args.append(extra)  # must be empty — no GT/seg leaked
        return list(self._boxes)


class _FakeBase:
    """Minimal g1-shape sim base: a live model/data + an RGB frame source."""

    def __init__(self):
        self._model = object()
        self._data = object()

    def get_camera_frame(self, w=640, h=480):
        return np.zeros((h, w, 3), dtype=np.uint8)


class _FakeAgent:
    def __init__(self, base):
        self._base = base
        self._arm = None
        self._perception = None


def _run(monkeypatch, boxes, seg=_SEG_CENTROID):
    """Wire a stub detector + stub segmentation GT + fake g1 agent."""
    stub = _StubDetector(boxes)
    monkeypatch.setattr(
        "vector_os_nano.perception.grounding_dino.get_shared_detector",
        lambda: stub,
    )
    # Stub the renderer-native segmentation GT (no GL in unit tests).
    monkeypatch.setattr(oracle_mod, "_red_geom_seg_centroid", lambda base, token: seg)
    agent = _FakeAgent(_FakeBase())
    return make_detection_matches_gt(agent), stub


def test_correct_box_on_seg_centroid_matches(monkeypatch):
    """A box centered on the segmentation centroid -> True (the EARNED GROUNDED)."""
    gu, gv, _ = _SEG_CENTROID
    boxes = [_Box(gu - 20, gv - 30, gu + 20, gv + 30)]  # center == (gu, gv)
    oracle, stub = _run(monkeypatch, boxes)
    assert oracle("red", tol=60.0) is True
    # FIREWALL: the detector only ever saw an RGB array, never the seg/GT.
    assert all(extra == () for extra in stub.seen_extra_args)
    assert all(len(shape) == 3 for shape in stub.seen_rgb_shapes)


def test_wrong_box_far_from_seg_is_refuted(monkeypatch):
    """REFUTATION: a box on a wall (far from the seg centroid) -> False -> RAN."""
    boxes = [_Box(5.0, 5.0, 25.0, 25.0)]  # center (15,15), hundreds of px from GT
    oracle, _ = _run(monkeypatch, boxes)
    assert oracle("red", tol=60.0) is False


def test_object_out_of_view_is_refuted(monkeypatch):
    """REFUTATION: no matching-colour geom in the segmentation (g1 faces away) -> False."""
    boxes = [_Box(300, 230, 340, 290)]  # even a centered box can't match an absent GT
    oracle, _ = _run(monkeypatch, boxes, seg=None)  # seg GT returns None = not in view
    assert oracle("red", tol=60.0) is False


def test_no_detection_is_refuted(monkeypatch):
    """No box at all -> False (detector found nothing to match)."""
    oracle, _ = _run(monkeypatch, boxes=[])
    assert oracle("red", tol=60.0) is False


def test_no_colour_token_fails_safe(monkeypatch):
    """A target with no colour word -> False (the oracle judges ONE coloured object)."""
    oracle, _ = _run(monkeypatch, boxes=[_Box(300, 230, 340, 290)])
    assert oracle("the thing over there", tol=60.0) is False


def test_missing_base_fails_safe():
    """No live sim base -> False (never raises into the verifier sandbox)."""
    class _Bare:
        _base = None
        _arm = None
    oracle = make_detection_matches_gt(_Bare())
    assert oracle("red") is False


def test_chinese_colour_word_resolves(monkeypatch):
    """'红色' maps to the red token so the NL command path grounds the same way."""
    gu, gv, _ = _SEG_CENTROID
    oracle, _ = _run(monkeypatch, [_Box(gu - 15, gv - 15, gu + 15, gv + 15)])
    assert oracle("找前面的红色的东西", tol=60.0) is True


def test_spine_grades_match_grounded_bare_ran():
    """The frozen spine grades '== True' GROUNDED and a bare call RAN (unchanged)."""
    from vector_os_nano.vcli.cognitive.evidence_classifier import classify_verify_expr

    names = frozenset({"detection_matches_gt"})
    assert classify_verify_expr("detection_matches_gt('red') == True", names) == "GROUNDED"
    assert classify_verify_expr("detection_matches_gt('red')", names) == "RAN"
    assert classify_verify_expr("detection_matches_gt('red') or True", names) == "RAN"
