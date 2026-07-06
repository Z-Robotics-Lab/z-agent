# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""VGG cognitive layer — types, verifier, decomposer, strategy selector, executor, stats, sandbox, experience, and object memory.

Public surface::

    from zeno.vcli.cognitive import (
        SubGoal,
        GoalTree,
        StepRecord,
        ExecutionTrace,
        GoalVerifier,
        GoalDecomposer,
        GoalExecutor,
        StrategySelector,
        StrategyResult,
        StrategyStats,
        StrategyRecord,
        CodeExecutor,
        CodeResult,
        SubGoalTemplate,
        GoalTemplate,
        ExperienceCompiler,
        TemplateLibrary,
        ObjectMemory,
        TrackedObject,
    )
"""
from __future__ import annotations

from zeno.vcli.cognitive.code_executor import CodeExecutor, CodeResult
from zeno.vcli.cognitive.experience_compiler import (
    ExperienceCompiler,
    GoalTemplate,
    SubGoalTemplate,
)
from zeno.vcli.cognitive.goal_decomposer import GoalDecomposer
from zeno.vcli.cognitive.goal_executor import GoalExecutor
from zeno.vcli.cognitive.goal_verifier import GoalVerifier
from zeno.vcli.cognitive.observation import (
    goal_tree_view,
    render_run_snapshot,
    render_step_view,
    run_snapshot,
    step_view,
)
from zeno.vcli.cognitive.strategy_selector import StrategyResult, StrategySelector
from zeno.vcli.cognitive.strategy_stats import StrategyRecord, StrategyStats
from zeno.vcli.cognitive.template_library import TemplateLibrary
from zeno.vcli.cognitive.tool_dispatcher import ToolDispatcher
from zeno.vcli.cognitive.trace_store import (
    classify_step_evidence,
    evidence_passed,
    load_trace,
    replay,
    save_trace,
    step_evidence_ok,
    verify_oracle_names,
)
from zeno.vcli.cognitive.vgg_harness import VGGHarness, HarnessConfig, FailureRecord
from zeno.vcli.cognitive.object_memory import ObjectMemory, TrackedObject
from zeno.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)

__all__ = [
    "CodeExecutor",
    "CodeResult",
    "ExperienceCompiler",
    "ExecutionTrace",
    "GoalDecomposer",
    "GoalExecutor",
    "GoalTemplate",
    "GoalTree",
    "GoalVerifier",
    "ObjectMemory",
    "StepRecord",
    "StrategyRecord",
    "StrategyResult",
    "StrategySelector",
    "StrategyStats",
    "SubGoal",
    "SubGoalTemplate",
    "TemplateLibrary",
    "ToolDispatcher",
    "TrackedObject",
    "VGGHarness",
    "HarnessConfig",
    "FailureRecord",
    "save_trace",
    "load_trace",
    "replay",
    "evidence_passed",
    "step_evidence_ok",
    "classify_step_evidence",
    "verify_oracle_names",
    "step_view",
    "run_snapshot",
    "goal_tree_view",
    "render_step_view",
    "render_run_snapshot",
]
