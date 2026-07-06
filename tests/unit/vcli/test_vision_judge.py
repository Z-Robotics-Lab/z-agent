# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the VisionJudge folds FAIL-CLOSED and never PASSes on uncertainty/error (ADR-002).

The real VLM call is injected (``call=``) so these stay network-free; the live judge is proven on
a real captured frame in the Stage-2 demo.
"""
from __future__ import annotations

import numpy as np

from zeno.acceptance import vision_judge as vj

_ITEMS = [
    {"key": "scene_rendered", "question": "rendered?"},
    {"key": "robot_present_upright", "question": "upright?"},
    {"key": "body_intact", "question": "intact?"},
    {"key": "workspace_in_frame", "question": "table?"},
]


def _all(ans: str) -> tuple:
    return tuple((it["key"], ans, "x") for it in _ITEMS)


def test_fold_all_yes_is_pass():
    assert vj._fold(_all("yes")) == vj.PASS


def test_fold_any_no_is_fail():
    per = list(_all("yes"))
    per[1] = ("robot_present_upright", "no", "floating")
    assert vj._fold(tuple(per)) == vj.FAIL


def test_fold_any_abstain_is_abstain_not_pass():
    per = list(_all("yes"))
    per[0] = ("scene_rendered", "abstain", "unclear")
    assert vj._fold(tuple(per)) == vj.ABSTAIN


def test_fold_empty_is_abstain():
    assert vj._fold(()) == vj.ABSTAIN


def test_parse_tolerates_prose_and_missing_keys():
    raw = 'sure!\n{"items": {"scene_rendered": {"answer": "YES", "why": "room"}}}\nthanks'
    per = vj._parse(raw, _ITEMS)
    d = dict((k, a) for k, a, _ in per)
    assert d["scene_rendered"] == "yes"          # case-normalised
    assert d["robot_present_upright"] == "abstain"  # missing -> fail-closed


def test_parse_bad_answer_value_becomes_abstain():
    raw = '{"items": {"scene_rendered": {"answer": "probably", "why": ""}}}'
    per = dict((k, a) for k, a, _ in vj._parse(raw, _ITEMS))
    assert per["scene_rendered"] == "abstain"


def test_judge_with_canned_pass(monkeypatch):
    def fake_call(b64, prompt, *, model, api_key):
        return '{"items": {%s}}' % ",".join(f'"{it["key"]}": {{"answer": "yes", "why": "ok"}}' for it in _ITEMS)

    # encode is real but cheap on a tiny synthetic frame
    import cv2
    import tempfile, os
    p = os.path.join(tempfile.mkdtemp(), "f.png")
    cv2.imwrite(p, np.full((8, 8, 3), 120, dtype=np.uint8))
    v = vj.judge(p, items=_ITEMS, call=fake_call)
    assert v.witness == vj.PASS


def test_judge_api_error_is_abstain_not_pass(monkeypatch):
    def boom(b64, prompt, *, model, api_key):
        raise RuntimeError("network down")

    import cv2
    import tempfile, os
    p = os.path.join(tempfile.mkdtemp(), "f.png")
    cv2.imwrite(p, np.full((8, 8, 3), 120, dtype=np.uint8))
    v = vj.judge(p, items=_ITEMS, call=boom)
    assert v.witness == vj.ABSTAIN  # fail-closed, never PASS on error


def test_judge_unreadable_image_is_abstain():
    v = vj.judge("/nonexistent/frame.png", items=_ITEMS, call=lambda *a, **k: "{}")
    assert v.witness == vj.ABSTAIN


def test_rubric_loads_four_orthogonal_items():
    items = vj.load_rubric()
    keys = {it["key"] for it in items}
    assert {"scene_rendered", "robot_present_upright", "body_intact", "workspace_in_frame"} <= keys
