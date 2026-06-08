# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""VGG cognitive layer — frozen dataclasses.

All types are immutable (frozen=True) to ensure safe sharing across
async executor threads without defensive copying.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ForEachSpec:
    """Control-flow FOREACH spec attached to a SubGoal (Stage 4, S4-1).

    Declares that a sub-goal's *body* is instantiated once per item of a list
    produced by an EARLIER step. The list is reached through the SAME pure
    ``${step.path}`` Blackboard convention every other step reference uses — e.g.
    ``detect_all.objects`` resolves to the detect step's ``result_data["objects"]``
    list. Each iteration binds the item to ``var`` (default ``"item"``); body
    sub-goal templates reference the item's fields with that var name (e.g.
    ``${obj.name}`` in strategy_params / verify), which the per-item binder
    resolves by PURE dict/list traversal — never string eval/format.

    S4-1 only models + parses + validates this spec; expansion at execution time
    is deferred to S4-2. All fields are frozen so the spec is safe to share.
    """

    # Producing step name (the step whose result_data holds the iterable).
    source_step: str
    # Dotted path INTO that step's result_data reaching the list to iterate, e.g.
    # ``"objects"`` or ``"objects.detections"``. Resolved by the Blackboard's pure
    # dict/list traversal; never evaluated.
    source_path: str
    # Iteration variable name bound to each item (referenced as ``${<var>.<field>}``
    # inside body templates). Defaults to ``"item"``.
    var: str = "item"
    # Body templates instantiated once per item. Empty tuple is a no-op loop.
    body: tuple["SubGoal", ...] = ()


@dataclass(frozen=True)
class SubGoal:
    """A single verifiable step in a goal decomposition tree."""

    name: str
    description: str
    verify: str  # Python expression evaluated by GoalVerifier
    timeout_sec: float = 30.0
    depends_on: tuple[str, ...] = ()
    strategy: str = ""
    strategy_params: dict = field(default_factory=dict)
    fail_action: str = ""
    # Stage 4 (S4-1) control flow: an optional FOREACH spec. When present, this
    # sub-goal is a loop node whose ``body`` is instantiated once per item of the
    # list produced by ``foreach.source_step``. None (the default) means a plain
    # leaf step — preserving every existing positional/keyword constructor and
    # keeping no-foreach plans byte-unaffected. Expansion is S4-2; S4-1 only
    # models + parses + validates the spec. Field is LAST + defaulted (frozen-safe).
    foreach: "ForEachSpec | None" = None
    # Stage 5 (S5.2) answer-only marker. True when this step is a pure-conversation
    # "answer" step that produces text and CARRIES NO ROBOT EVIDENCE BY DESIGN —
    # NOT an action step whose evidence is merely missing. This flag (not a
    # verify-string trick) is what lets the evidence gate DISTINGUISH a legitimate
    # answer-only step from an action step that produced no evidence, so the moat
    # (rule 5) is never weakened: an action step with a sentinel verify still fails
    # the gate; only an explicitly-flagged answer step is exempt. Additive + LAST +
    # defaulted False so every existing constructor and non-answer plan is
    # byte-unaffected.
    answer_only: bool = False


@dataclass(frozen=True)
class GoalTree:
    """Full decomposition of a high-level task into ordered SubGoals."""

    goal: str
    sub_goals: tuple[SubGoal, ...]
    context_snapshot: str = ""
    # Validator feedback (Stage 2b): human-readable notes about strategies or
    # sub_goals the decomposer DROPPED during validation (e.g. an unknown
    # strategy cleared to ""). The harness threads these into the next replan's
    # decompose context so the LLM stops repeating the hallucination. Additive +
    # keyword-default so existing positional constructors are unaffected.
    validation_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepRecord:
    """Execution record for a single SubGoal attempt."""

    sub_goal_name: str
    strategy: str
    success: bool
    verify_result: bool
    duration_sec: float
    error: str = ""
    fallback_used: bool = False
    # True when verify_result was set by a VLM visual-verification override
    # rather than the deterministic predicate — NOT deterministic evidence
    # (see trace_store.evidence_passed).
    visual_override: bool = False
    # Captured structured output of the step (Stage 1a). Typically
    # {"output": <strategy output dict>, "verify_value": <raw verify value>}.
    # Additive + keyword-default so existing positional constructors are unaffected.
    result_data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionTrace:
    """Complete record of a goal execution run."""

    goal_tree: GoalTree
    steps: tuple[StepRecord, ...]
    success: bool
    total_duration_sec: float
