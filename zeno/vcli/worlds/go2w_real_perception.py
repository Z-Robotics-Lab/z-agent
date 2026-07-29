# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real perception skills — find_object / scene_query via RynnBrain.

The real dog's eyes: a local RynnBrain embodied VLM (GPU workstation service,
JSON POST /infer — see :mod:`zeno.perception.rynnbrain`). Both skills are
READ-ONLY perception: their output is DECISION INPUT for the model, never
verification evidence (Inv-1 — a VLM self-report is not ground truth; arrival
is still proven by at()/moved()/turned() odometry oracles).

* ``find_object``: one live frame (``get_camera_image()`` — the None-honest
  accessor; the black-frame fallback must NEVER reach the VLM) -> RynnBrain
  grounding -> box centre -> image side (左/中/右) + horizontal bearing in
  degrees (positive = turn left; D435i color HFOV ≈ 69°). The message teaches
  the follow-up: turn toward the bearing, approach, verify with odometry.
* ``scene_query``: free-form QA in thinking mode (slower, better answers).

Wording rule: effects/description must avoid the 7 MOTOR_KEYWORDS
(skill_wrapper._detect_motor scans them) — these skills must wrap read-only +
concurrency-safe. Names avoid the native-loop special cases (navigate/detect).

Split file per the repo rule (files < 400 lines); registered at the skills
extension marker in ``go2w_real.py``; strategies ``find_object_skill`` /
``scene_query_skill``. Client rides the standard two-path seam
(services['rynn'] + base.rynn_client).
"""

from __future__ import annotations

import time
from typing import Any

from zeno.core.skill import skill
from zeno.core.types import SkillResult
from zeno.vcli.worlds.go2w_real_diag import oplog
from zeno.vcli.worlds.go2w_real_skills import _base_of

# D435i color stream horizontal FOV (~69°): bearing = (500-cx)/500 * HFOV/2.
_HFOV_DEG = 69.0
_STALE_WARN_S = 2.0

_default_client = None  # module-level last-resort client (lazy)


def _client_of(context: Any) -> Any:
    """RynnBrain client from a SkillContext (two-path seam, then default).

    The embodiment publishes it as the 'rynn' service; VGG GoalExecutor
    contexts carry no world services, so it also rides the driver
    (base.rynn_client). A bare context falls back to a module-level default
    (zero-config: localhost/ZENO_RYNNBRAIN_URL).
    """
    services = getattr(context, "services", None) or {}
    client = services.get("rynn")
    if client is not None:
        return client
    client = getattr(getattr(context, "base", None), "rynn_client", None)
    if client is not None:
        return client
    global _default_client
    if _default_client is None:
        from zeno.perception.rynnbrain import RynnBrainClient

        _default_client = RynnBrainClient()
    return _default_client


def _live_frame(base: Any):
    """(frame, age_s) — the None-honest accessor + best-effort staleness."""
    frame = base.get_camera_image()
    if frame is None:
        return None, None
    age = None
    ts = getattr(getattr(base, "_camera", None), "_last_ts", None)
    if isinstance(ts, (int, float)):
        age = max(0.0, time.monotonic() - float(ts))
    return frame, age


def _side_label(cx: float) -> str:
    if cx < 400:
        return "左"
    if cx > 600:
        return "右"
    return "中"


def _bearing_deg(cx: float) -> float:
    """[0,1000] box-centre x -> horizontal bearing (deg, positive = left)."""
    return (500.0 - cx) / 500.0 * (_HFOV_DEG / 2.0)


@skill(aliases=["find_object", "find object", "找物体", "视觉定位"], direct=True)
class RealFindObjectSkill:
    """Visually locate ONE object via the RynnBrain VLM (decision input)."""

    name = "find_object"
    description = (
        "Locate ONE object in the head-camera view via the local RynnBrain "
        "VLM. Returns the image side (左/中/右), a horizontal bearing in "
        "degrees (positive = turn left), and the [0,1000] box. Phrase the "
        "target by its REAL appearance (color/material). Perception is "
        "DECISION INPUT only: after turning toward the bearing and "
        "approaching, prove arrival with at()/turned() odometry — never with "
        "this skill. 找物体(视觉定位)。")
    parameters = {
        "description": {"type": "string", "required": True,
                        "description": ("what to locate, phrased by real "
                                        "appearance, e.g. 'metal bowl', "
                                        "'red charger'")},
    }
    preconditions: list = []
    effects = {"perception": "queried"}

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        if base is None:
            return SkillResult(success=False, diagnosis_code="no_base",
                               error_message="No Go2W hardware base")
        desc = str((params or {}).get("description")
                   or kw.get("description") or "").strip()
        if not desc:
            return SkillResult(success=False, diagnosis_code="bad_params",
                               error_message=("find_object needs a "
                                              "description of the target"))
        frame, age = _live_frame(base)
        if frame is None:
            return SkillResult(
                success=False, diagnosis_code="camera_failed",
                error_message=("no camera frame received yet — the camera "
                               "stream is not flowing; check the D435i "
                               "service before perception"))
        client = _client_of(context)
        try:
            reply = client.locate(frame, desc)
        except Exception as exc:  # noqa: BLE001 — service boundary, honest failure
            oplog("skill", "find_object", f"no_vlm: {exc}")
            return SkillResult(success=False, diagnosis_code="no_vlm",
                               error_message=f"RynnBrain unreachable: {exc}")
        from zeno.perception.rynnbrain import (is_degenerate_box, parse_boxes,
                                               sent_size)

        boxes = parse_boxes(reply)
        if not boxes:
            oplog("skill", "find_object", f"not found: {desc!r}")
            return SkillResult(
                success=False, diagnosis_code="object_not_found",
                error_message=(f"RynnBrain could not locate '{desc}' "
                               f"(reply: {reply[:120]}). Re-phrase by real "
                               f"appearance (颜色/材质), or scene_query first"))
        image_wh = sent_size(int(frame.shape[1]), int(frame.shape[0]))
        boxes = [b for b in boxes if not is_degenerate_box(b, image_wh)]
        if not boxes:
            oplog("skill", "find_object", f"degenerate box: {desc!r}")
            return SkillResult(
                success=False, diagnosis_code="object_not_found",
                error_message=(
                    f"RynnBrain 对 '{desc}' 只返回全幅退化框 — 2B 模型对不在场"
                    f"物体的典型应答, 按未找到处理(不给假方位)。场景里很可能没有"
                    f"该物体: 先用 scene_query 确认在场物体, 再按真实外观"
                    f"(颜色/材质)重新描述"))
        (x1, y1), (x2, y2) = boxes[0]
        cx = (x1 + x2) / 2.0
        side = _side_label(cx)
        bearing = _bearing_deg(cx)
        turn_dir = "left" if bearing > 0 else "right"
        message = (
            f"{desc}: 画面{side}侧, 水平偏角约 {bearing:+.1f}°（左正右负）, "
            f"框[0,1000]=({x1},{y1})-({x2},{y2})。这是决策输入: 可先 "
            f"turn_skill(direction={turn_dir}, degrees≈{abs(bearing):.0f}) 对准, "
            f"靠近后用 at(x, y) / turned() 里程计验收")
        if len(boxes) > 1:
            message += f"; 另有 {len(boxes) - 1} 个候选框被忽略"
        if age is not None and age > _STALE_WARN_S:
            message += f"; ⚠ 相机帧已 {age:.1f}s 未更新, 结果可能过时"
        oplog("skill", "find_object",
              f"{desc!r} -> side={side} bearing={bearing:+.1f}")
        return SkillResult(success=True, result_data={
            "side": side,
            "bearing_deg": round(bearing, 2),
            "box": [[x1, y1], [x2, y2]],
            "message": message,
        })


@skill(aliases=["scene_query", "场景问答", "看到什么", "你看到了什么"], direct=True)
class RealSceneQuerySkill:
    """Free-form QA about the camera view via RynnBrain (thinking mode)."""

    name = "scene_query"
    description = (
        "Answer a free question about the current head-camera view via the "
        "local RynnBrain VLM in thinking mode (slower, better answers). Use "
        "for scene understanding (桌上有什么/前面是什么); the answer is "
        "DECISION INPUT, not verification evidence. 场景问答。")
    parameters = {
        "question": {"type": "string", "required": True,
                     "description": "the question to ask about the view"},
    }
    preconditions: list = []
    effects = {"perception": "queried"}

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        if base is None:
            return SkillResult(success=False, diagnosis_code="no_base",
                               error_message="No Go2W hardware base")
        question = str((params or {}).get("question")
                       or kw.get("question")
                       or getattr(context, "instruction", "") or "").strip()
        if not question:
            return SkillResult(success=False, diagnosis_code="bad_params",
                               error_message="scene_query needs a question")
        frame, age = _live_frame(base)
        if frame is None:
            return SkillResult(
                success=False, diagnosis_code="camera_failed",
                error_message=("no camera frame received yet — the camera "
                               "stream is not flowing; check the D435i "
                               "service before perception"))
        client = _client_of(context)
        try:
            reply = client.ask(frame, question, think=True)
        except Exception as exc:  # noqa: BLE001 — service boundary, honest failure
            oplog("skill", "scene_query", f"no_vlm: {exc}")
            return SkillResult(success=False, diagnosis_code="no_vlm",
                               error_message=f"RynnBrain unreachable: {exc}")
        message = reply
        if age is not None and age > _STALE_WARN_S:
            message += f"\n⚠ 相机帧已 {age:.1f}s 未更新, 回答可能过时"
        oplog("skill", "scene_query", f"{question!r} -> {reply[:80]!r}")
        return SkillResult(success=True, result_data={
            "question": question,
            "message": message,
        })
