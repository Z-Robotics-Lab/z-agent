# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""trace_store — persist, reload, and replay VGG execution traces.

Turns a run's ``ExecutionTrace`` into a replayable, self-grading eval signal:

- ``save_trace`` / ``load_trace`` round-trip a trace to JSON under
  ``~/.vector/traces/`` (frozen dataclasses -> dicts and back; tuples survive).
- ``replay`` re-evaluates each sub-goal's *deterministic* verify predicate with
  a fresh ``GoalVerifier``. Visual overrides are NOT reproduced — only
  deterministic evidence counts, which is the point of replay.
- ``evidence_passed`` gates a "verified done" in EVERY world (dev and robot
  alike — the old ``if is_robot: return True`` bypass is gone): a step backs the
  outcome with evidence only when its verify actually consumes a world oracle
  (single-sourced via ``classify_step_evidence`` -> ``classify_verify_expr``).
  A sentinel ``""`` / ``"True"`` verify, an absent oracle, or a tautology
  classify RAN and do NOT pass the gate.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Literal

from vector_os_nano.vcli.cognitive.actor_causation import ActorCaused, from_name
from vector_os_nano.vcli.cognitive.evidence_classifier import classify_verify_expr
from vector_os_nano.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)

logger = logging.getLogger(__name__)

StepEvidence = Literal["GROUNDED", "RAN", "FAILED"]

# Verify strings that carry no deterministic evidence (empty, or the trivial
# fallback the decomposer/robot motor steps use).
_NO_EVIDENCE: frozenset[str] = frozenset({"", "True"})

_DEFAULT_TRACES_DIR = Path.home() / ".vector" / "traces"

# Bump when the on-disk shape changes; load_trace tolerates older/unknown keys.
# v2 adds StepRecord.visual_override; v3 adds SubGoal.answer_only (S5.2);
# v4 adds StepRecord.actor_caused (R2b actor-causation grade).
_SCHEMA_VERSION = 4

# The ONLY side-effect-free dispatch route (``GoalExecutor._execute_answer`` does
# no I/O and no model call). The evidence-gate exemption for a no-robot-evidence
# step is bound to it, never to the LLM-controlled ``answer_only`` flag alone.
_ANSWER_STRATEGY = "answer"


def _is_answer_only(sub_goal: SubGoal) -> bool:
    """True iff *sub_goal* is a legitimately-exempt answer-only step.

    The evidence-gate relaxation (skip the real-predicate requirement) applies
    ONLY to a step that is BOTH flagged ``answer_only`` AND routed through the
    side-effect-free ``answer`` strategy. Tying the exemption to the zero-I/O
    executor — not to the LLM-controlled ``answer_only`` bit alone — keeps the
    moat (rule 5) intact: an LLM that sets ``answer_only: true`` on a
    side-effecting strategy (``tool_call`` / a skill) does NOT get waived, because
    that step still runs a real executor and so must carry deterministic evidence.
    The decomposer additionally refuses the flag on non-``answer`` strategies, so
    this gate and the decomposer agree; this check is the belt to that suspenders.
    """
    return bool(getattr(sub_goal, "answer_only", False)) and sub_goal.strategy == _ANSWER_STRATEGY


# ---------------------------------------------------------------------------
# Oracle names — single-sourced from the LIVE verify namespace
# ---------------------------------------------------------------------------


def verify_oracle_names(agent: Any, engine: Any = None) -> frozenset[str]:
    """The callable names in the LIVE verify namespace GoalVerifier uses.

    Single source (rule 3): the names are the keys of the SAME dict
    ``engine._build_verifier_namespace(agent)`` builds for ``GoalVerifier`` (which
    already merges ``World.build_verify_namespace(agent)`` on top — so a connected
    sim arm's ``arm_at_home`` / ``holding_object`` overlay is visible here, and the
    engine's empty perception stubs at engine.py:906 are correctly shadowed). NEVER
    a hand-authored second allowlist.

    *engine* is required to build the namespace; when it is None (or namespace
    construction raises) this FAILS CLOSED to ``frozenset()`` — with no oracle
    names every predicate classifies RAN, never a spurious GROUNDED. This keeps the
    moat strict (rule 5): an absent namespace can only make verification stricter.
    """
    if engine is None:
        return frozenset()
    builder = getattr(engine, "_build_verifier_namespace", None)
    if builder is None:
        return frozenset()
    try:
        ns = builder(agent)
    except Exception as exc:  # noqa: BLE001
        logger.debug("verify_oracle_names: namespace build failed: %s", exc)
        return frozenset()
    return frozenset(ns.keys())


# ---------------------------------------------------------------------------
# Per-step evidence classification (single source for BOTH gates — rule 3)
# ---------------------------------------------------------------------------


def _actor_uncaused(step: StepRecord) -> bool:
    """True iff the executor graded this step's actor-causation as UNCAUSED (R2b).

    Reads ``step.actor_caused`` defensively (``getattr``) so a legacy StepRecord
    built before the field existed reads as ``NOT_GRADED`` -> not uncaused -> no
    downgrade. Only the explicit ``UNCAUSED`` value downgrades a GROUNDED step.
    """
    return getattr(step, "actor_caused", ActorCaused.NOT_GRADED) == ActorCaused.UNCAUSED


def classify_step_evidence(
    step: StepRecord, sub_goal: SubGoal, oracle_names: frozenset[str],
    goal_text: str | None = None,
) -> StepEvidence:
    """Classify a single executed step's evidence: GROUNDED / RAN / FAILED.

    The ONE source of truth for both the done-gate (``evidence_passed``) and the
    per-step reward gate (``step_evidence_ok``) — rule 3 (no split-brain). It
    replaces the old ``if is_robot: return True`` short-circuit with the honest
    classifier: a robot step that merely RAN (``verify="True"``) is no longer
    auto-passed; only a step whose verify actually consumes a world oracle in a
    non-tautological way reaches GROUNDED.

    - FAILED — the step did not succeed (``not step.success``).
    - GROUNDED — the step succeeded AND either:
        * it is a legitimately-exempt answer-only step (zero-I/O ``answer``
          strategy) whose ``verify_result`` is True and not a visual override; OR
        * ``classify_verify_expr(sub_goal.verify, oracle_names) == "GROUNDED"``
          AND ``step.verify_result`` AND not a visual override.
      A VLM visual override is not deterministic (not replayable) evidence, so it
      can never reach GROUNDED — keeping this gate in agreement with ``replay``.
    - RAN — the step succeeded but its verify carries no real, non-tautological
      world evidence (a sentinel ``""``/``"True"``, an absent oracle, or a
      tautology), or it succeeded with a visual override.

    R2b ACTOR-CAUSATION downgrade (single-sourced HERE so it flows to BOTH gates
    and the VECTOR_VERDICT report): a step that would otherwise classify GROUNDED is
    DOWNGRADED to RAN when ``step.actor_caused == ActorCaused.UNCAUSED`` — i.e. the
    R1 predicate is GROUNDED but the executor graded that the ACTOR did NOT cause the
    state change (a satisfied-at-baseline NO-OP, or a teleport with no commanded
    motion). The downgrade fires ONLY on the explicit ``UNCAUSED`` value; the default
    ``NOT_GRADED`` (legacy / hand-built / non-robot-predicate steps the executor never
    graded) classifies EXACTLY as before R2b — zero regression. ``CAUSED`` is a no-op
    here (the step keeps its GROUNDED classification).

    STEP-13 GOAL-AUTHENTICITY downgrade (also subtractive, fail-OPEN): when *goal_text*
    is provided (the turn's NL goal, single-sourced from ``trace.goal_tree.goal``) and
    BOTH it parses to a coordinate AND the verify is a literal ``at_position(x, y)``
    whose constant differs from the goal by more than the oracle tolerance, the
    otherwise-GROUNDED step DOWNGRADES to RAN — the model verified its OWN landing, not
    the commanded target. Non-coordinate goals/verifies fail OPEN (unchanged);
    ``goal_text=None`` (the per-step reward gate) is a no-op. Stricter-only (rule 5).
    """
    if not step.success:
        return "FAILED"
    visual_override = bool(getattr(step, "visual_override", False))
    if _is_answer_only(sub_goal):
        return "GROUNDED" if (step.verify_result and not visual_override) else "RAN"
    grounded = (
        classify_verify_expr(sub_goal.verify, oracle_names) == "GROUNDED"
        and step.verify_result
        and not visual_override
    )
    if grounded and _actor_uncaused(step):
        # R2b: GROUNDED predicate but the actor did not cause it -> downgrade to RAN.
        return "RAN"
    if grounded and goal_text is not None:
        # STEP-13 goal-authenticity: an actor-CAUSED at_position verify whose constant
        # does NOT match the user's parsed COORDINATE goal means the model verified its
        # OWN landing, not the commanded target -> downgrade to RAN. Fail-OPEN whenever
        # the goal or the verify is not a parseable coordinate. Stricter-only.
        from vector_os_nano.vcli.cognitive.coord_goal import coord_goal_mismatch

        if coord_goal_mismatch(goal_text, sub_goal.verify):
            return "RAN"
    return "GROUNDED" if grounded else "RAN"


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
                    "answer_only": getattr(sg, "answer_only", False),
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
                "visual_override": getattr(s, "visual_override", False),
                # R2b: serialize the actor-causation grade as its enum ``.value``.
                "actor_caused": getattr(
                    s, "actor_caused", ActorCaused.NOT_GRADED
                ).value,
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
            answer_only=bool(sg.get("answer_only", False)),
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
            visual_override=bool(s.get("visual_override", False)),
            # R2b: deserialize the actor-causation grade; absent/unknown (older
            # traces) maps to NOT_GRADED -> legacy-equivalent (no downgrade).
            actor_caused=from_name(s.get("actor_caused")),
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

    Stage 5 (S5.2): an explicitly ``answer_only`` step carries no robot evidence
    BY DESIGN — it is skipped exactly like a sentinel and never counts toward
    ``checked``. This does NOT loosen the gate: the exemption is tied to the
    side-effect-free ``answer`` strategy (``answer_only`` alone is fully
    LLM-controlled, so it is NOT trusted to waive evidence for a step that runs a
    side-effecting executor). An action step with a sentinel verify is still
    non-evidence and a pure-answer trace still returns False (nothing deterministic
    was checked).
    """
    checked = 0
    for sg in trace.goal_tree.sub_goals:
        if _is_answer_only(sg):
            continue
        expr = (sg.verify or "").strip()
        if expr in _NO_EVIDENCE:
            continue
        checked += 1
        if not verifier.verify(sg.verify):
            return False
    return checked > 0


def evidence_passed(trace: ExecutionTrace, oracle_names: frozenset[str]) -> bool:
    """True when the trace's success is backed by deterministic evidence.

    Single-sourced through ``classify_step_evidence`` (rule 3) and applied to BOTH
    dev and robot worlds (the dishonest ``if is_robot: return True`` bypass is
    GONE): every executed step that maps to a sub-goal must classify GROUNDED, and
    there must be at least one such checked step (an empty trace fails). A step
    classifies GROUNDED only when its verify actually consumes a world oracle in
    *oracle_names* in a non-tautological way (or it is a legitimately-exempt
    answer-only step); a sentinel ``""`` / ``"True"`` verify (the robot motor
    default), an absent oracle, a tautology, or a VLM visual override classify RAN
    and so do NOT pass the gate.

    *oracle_names* MUST be the live verify-namespace callable names from
    ``verify_oracle_names(agent, engine)`` — single-sourced from the SAME namespace
    ``GoalVerifier`` uses; never a hand-authored copy. An empty set fails closed
    (everything classifies RAN), so the moat only ever gets stricter (rule 5).

    Stage 5 (S5.2): a step whose sub-goal is explicitly ``answer_only`` (and routed
    through the zero-I/O ``answer`` strategy) is a pure-conversation step that
    carries no robot evidence BY DESIGN; ``classify_step_evidence`` exempts it from
    the real-predicate requirement but still requires ``verify_result`` True and no
    visual override. The exemption is keyed on the side-effect-free ``answer``
    strategy, NOT the LLM-controlled ``answer_only`` flag alone, so an LLM cannot
    launder a side-effecting step past the gate.
    """
    sg_by_name = {sg.name: sg for sg in trace.goal_tree.sub_goals}
    checked = [s for s in trace.steps if s.sub_goal_name in sg_by_name]
    if not checked:
        return False
    goal_text = trace.goal_tree.goal
    return all(
        classify_step_evidence(s, sg_by_name[s.sub_goal_name], oracle_names, goal_text) == "GROUNDED"
        for s in checked
    )


def step_evidence_ok(
    step: StepRecord, sub_goal: SubGoal, oracle_names: frozenset[str]
) -> bool:
    """True when a SINGLE step's pass is backed by deterministic evidence.

    The per-step analogue of ``evidence_passed``, single-sourced through the SAME
    ``classify_step_evidence`` (rule 3): True iff this step classifies GROUNDED.
    The robot bypass is GONE — a robot motor step with ``verify="True"`` now
    classifies RAN, not GROUNDED, so it no longer trains the bandit on unverified
    "success". Reward parity with the done-gate is intentional (W1.1 → R1):
    learning is rewarded only for steps that actually proved their post-condition.

    *oracle_names* MUST come from ``verify_oracle_names(agent, engine)`` (live
    namespace, single source). An empty set fails closed (classifies RAN).
    """
    return classify_step_evidence(step, sub_goal, oracle_names) == "GROUNDED"
