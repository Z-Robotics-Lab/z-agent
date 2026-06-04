# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""trace_store — persist, reload, and replay VGG execution traces.

Turns a run's ``ExecutionTrace`` into a replayable, self-grading eval signal:

- ``save_trace`` / ``load_trace`` round-trip a trace to JSON under
  ``~/.vector/traces/`` (frozen dataclasses -> dicts and back; tuples survive).
- ``replay`` re-evaluates each sub-goal's *deterministic* verify predicate with
  a fresh ``GoalVerifier``. Visual overrides are NOT reproduced — only
  deterministic evidence counts, which is the point of replay.
- ``evidence_passed`` gates a "verified done": in the dev world a step backs the
  outcome with evidence only when its verify is a real predicate (not the
  sentinels ``""`` / ``"True"``) AND that predicate verified. Robot worlds bypass
  the gate so async motor skills that legitimately use ``verify="True"`` do not
  regress.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from vector_os_nano.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)

# Verify strings that carry no deterministic evidence (empty, or the trivial
# fallback the decomposer/robot motor steps use).
_NO_EVIDENCE: frozenset[str] = frozenset({"", "True"})

_DEFAULT_TRACES_DIR = Path.home() / ".vector" / "traces"

# Bump when the on-disk shape changes; load_trace tolerates older/unknown keys.
_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# (De)serialization
# ---------------------------------------------------------------------------


def _trace_to_dict(trace: ExecutionTrace) -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "goal_tree": {
            "goal": trace.goal_tree.goal,
            "sub_goals": [
                {
                    "name": sg.name,
                    "description": sg.description,
                    "verify": sg.verify,
                    "timeout_sec": sg.timeout_sec,
                    "depends_on": list(sg.depends_on),
                    "strategy": sg.strategy,
                    "strategy_params": sg.strategy_params,
                    "fail_action": sg.fail_action,
                }
                for sg in trace.goal_tree.sub_goals
            ],
            "context_snapshot": trace.goal_tree.context_snapshot,
        },
        "steps": [
            {
                "sub_goal_name": s.sub_goal_name,
                "strategy": s.strategy,
                "success": s.success,
                "verify_result": s.verify_result,
                "duration_sec": s.duration_sec,
                "error": s.error,
                "fallback_used": s.fallback_used,
            }
            for s in trace.steps
        ],
        "success": trace.success,
        "total_duration_sec": trace.total_duration_sec,
    }


def _dict_to_trace(data: dict[str, Any]) -> ExecutionTrace:
    gt = data.get("goal_tree", {}) or {}
    sub_goals = tuple(
        SubGoal(
            name=str(sg.get("name", "")),
            description=str(sg.get("description", "")),
            verify=str(sg.get("verify", "")),
            timeout_sec=float(sg.get("timeout_sec", 30.0)),
            depends_on=tuple(sg.get("depends_on", []) or ()),
            strategy=str(sg.get("strategy", "")),
            strategy_params=dict(sg.get("strategy_params", {}) or {}),
            fail_action=str(sg.get("fail_action", "")),
        )
        for sg in gt.get("sub_goals", []) or []
    )
    goal_tree = GoalTree(
        goal=str(gt.get("goal", "")),
        sub_goals=sub_goals,
        context_snapshot=str(gt.get("context_snapshot", "")),
    )
    steps = tuple(
        StepRecord(
            sub_goal_name=str(s.get("sub_goal_name", "")),
            strategy=str(s.get("strategy", "")),
            success=bool(s.get("success", False)),
            verify_result=bool(s.get("verify_result", False)),
            duration_sec=float(s.get("duration_sec", 0.0)),
            error=str(s.get("error", "")),
            fallback_used=bool(s.get("fallback_used", False)),
        )
        for s in data.get("steps", []) or []
    )
    return ExecutionTrace(
        goal_tree=goal_tree,
        steps=steps,
        success=bool(data.get("success", False)),
        total_duration_sec=float(data.get("total_duration_sec", 0.0)),
    )


def save_trace(trace: ExecutionTrace, path: str | Path | None = None) -> Path:
    """Serialise *trace* to JSON; return the written path.

    With no *path*, writes a uuid-named file under ``~/.vector/traces/``.
    Written atomically (temp file + ``os.replace``) so a concurrent reader never
    sees a half-written file.
    """
    import os

    if path is None:
        _DEFAULT_TRACES_DIR.mkdir(parents=True, exist_ok=True)
        path = _DEFAULT_TRACES_DIR / f"trace-{uuid.uuid4().hex}.json"
    else:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(_trace_to_dict(trace), ensure_ascii=False, indent=2)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(payload)
    os.replace(tmp, path)
    return path


def load_trace(path: str | Path) -> ExecutionTrace:
    """Reconstruct an ExecutionTrace from a JSON file written by ``save_trace``."""
    data = json.loads(Path(path).read_text())
    return _dict_to_trace(data)


# ---------------------------------------------------------------------------
# Replay + evidence
# ---------------------------------------------------------------------------


def replay(trace: ExecutionTrace, verifier: Any) -> bool:
    """Re-evaluate every sub-goal's deterministic verify predicate.

    Returns True iff every non-sentinel verify expression evaluates truthy under
    *verifier* (a ``GoalVerifier``). Sentinel verifies (``""`` / ``"True"``) are
    skipped — they carry no evidence — and a trace with *no* deterministic
    predicate to replay returns False (nothing was actually checked).
    """
    checked = 0
    for sg in trace.goal_tree.sub_goals:
        expr = (sg.verify or "").strip()
        if expr in _NO_EVIDENCE:
            continue
        checked += 1
        if not verifier.verify(sg.verify):
            return False
    return checked > 0


def evidence_passed(trace: ExecutionTrace, is_robot: bool = False) -> bool:
    """True when the trace's success is backed by deterministic evidence.

    Dev world (strict): every executed step must map to a sub-goal whose verify
    is a real predicate (not ``""`` / ``"True"``) and whose ``verify_result`` is
    True. Robot world: always True — do not regress async motor skills that use
    ``verify="True"`` because no symbolic post-condition exists.
    """
    if is_robot:
        return True
    sg_by_name = {sg.name: sg for sg in trace.goal_tree.sub_goals}
    checked = [s for s in trace.steps if s.sub_goal_name in sg_by_name]
    if not checked:
        return False
    return all(
        (sg_by_name[s.sub_goal_name].verify or "").strip() not in _NO_EVIDENCE
        and s.verify_result
        for s in checked
    )
