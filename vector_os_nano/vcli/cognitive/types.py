# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""VGG cognitive layer — frozen dataclasses.

All types are immutable (frozen=True) to ensure safe sharing across
async executor threads without defensive copying.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
