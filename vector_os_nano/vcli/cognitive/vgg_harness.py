# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""VGG Harness — feedback loop wrapper around the VGG pipeline.

Three layers of retry/recovery:

Layer 1 (step-level): Strategy A fails → try alternative strategies
Layer 2 (tree-level): Step fails → re-decompose remaining goals with failure context
Layer 3 (pipeline-level): Whole tree fails → full re-plan with history

This prevents single-point failures from killing the entire task.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from vector_os_nano.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HarnessConfig:
    """Configuration for VGG retry behavior."""
    max_step_retries: int = 2       # per-step strategy retries (Layer 1)
    max_redecompose: int = 1        # re-decompose attempts on step failure (Layer 2)
    max_pipeline_retries: int = 1   # full re-plan attempts (Layer 3)
    # Stage 4 (S4-4) — observation-driven mid-tree replan. The maximum number of
    # times the harness may re-decompose a SUCCEEDING run because a step's
    # result_data showed a live observation that diverged from the plan's
    # assumptions (e.g. detect found a different object set). Bounded so a
    # detector that always reports divergence cannot loop forever. Only consulted
    # when an ``observation_divergence`` detector is wired into the harness; with
    # no detector the run path is byte-identical. Additive + LAST + defaulted so
    # existing HarnessConfig(...) constructions are unaffected.
    max_obs_replan: int = 1


@dataclass(frozen=True)
class FailureRecord:
    """Records a failure for feedback to the decomposer."""
    sub_goal_name: str
    strategy_tried: str
    error: str
    step_index: int


class VGGHarness:
    """Wraps GoalDecomposer + GoalExecutor with feedback loops.

    Usage:
        harness = VGGHarness(decomposer, executor, selector, verifier)
        trace = harness.run("去厨房看看有没有杯子", world_context)
    """

    def __init__(
        self,
        decomposer: Any,
        executor: Any,
        selector: Any = None,
        config: HarnessConfig | None = None,
        on_step: Callable[[StepRecord], None] | None = None,
        on_replan: Callable[[str], None] | None = None,
        observation_divergence: Callable[[ExecutionTrace], str | None] | None = None,
    ) -> None:
        """Construct the harness.

        Args:
            observation_divergence: Optional detector for observation-driven
                mid-tree replan (Stage 4, S4-4). Given the just-completed
                ExecutionTrace, it returns a non-empty reason string when a step's
                live observation (its ``result_data``) diverged from what the plan
                assumed — e.g. a detect step found a different object set, or a
                post-pick re-detect changed the remaining set. Returning ``None`` /
                "" means no divergence. When this is ``None`` (the default) the
                observation-replan loop is entirely skipped and ``run()`` is
                byte-identical to before. The detector is a PURE read over the
                trace/result_data — it never executes model output.
        """
        self._decomposer = decomposer
        self._executor = executor
        self._selector = selector
        self._config = config or HarnessConfig()
        self._on_step = on_step
        self._on_replan = on_replan
        self._obs_divergence = observation_divergence

    def run(
        self,
        task: str,
        world_context: str,
        goal_tree: GoalTree | None = None,
        context_provider: Callable[[], str] | None = None,
    ) -> ExecutionTrace:
        """Run task with full feedback loop.

        Args:
            task: Natural language task description.
            world_context: Current world model summary (static fallback).
            goal_tree: Pre-decomposed GoalTree (skip decomposition if provided).
            context_provider: Optional callable that (re)builds the world context
                on demand (Stage 1b). When given, it is called to produce a FRESH
                world context for the initial decompose and before every
                re-decompose, so replans see current state. When ``None`` the
                static *world_context* arg is used (current behavior).

        Returns:
            Best ExecutionTrace achieved across all retry attempts.
        """
        cfg = self._config
        failures: list[FailureRecord] = []
        best_trace: ExecutionTrace | None = None
        tree: GoalTree | None = None
        obs_replans_used = 0  # S4-4: bounded observation-driven re-decomposes

        # Data binding (Stage 1b): one fresh Blackboard scoped to this run. The
        # executor captures each successful step's output here and resolves later
        # steps' ``${step.key}`` params against it. Fail-soft: if the executor
        # has no blackboard attribute (e.g. a bare mock) capture is simply off.
        self._attach_blackboard()

        for pipeline_attempt in range(cfg.max_pipeline_retries + 1):
            # --- Abort check ---
            try:
                from vector_os_nano.vcli.cognitive.abort import is_abort_requested
                if is_abort_requested():
                    break
            except ImportError:
                pass

            # --- Decompose (or use provided tree) ---
            if goal_tree is not None and pipeline_attempt == 0:
                tree = goal_tree
            else:
                fresh_context = self._current_context(world_context, context_provider)
                # Validator feedback (Stage 2b): carry the PRIOR attempt's dropped/
                # invalid-strategy notes into this decompose so the next plan stops
                # repeating the hallucination. ``tree`` still holds the previous
                # attempt's GoalTree here (None on the very first attempt).
                prior_notes = tuple(getattr(tree, "validation_notes", ()) or ())
                tree = self._decompose_with_context(
                    task, fresh_context, failures, prior_notes
                )
                if tree is None:
                    logger.warning("VGGHarness: decomposition failed on attempt %d", pipeline_attempt)
                    break

            # --- Execute with step-level retry ---
            trace = self._execute_with_retry(tree, failures)

            # Track best result
            if best_trace is None or trace.success:
                best_trace = trace

            if trace.success:
                # --- S4-4: observation-driven mid-tree replan ---
                # Even a fully-verified run may have observed live state that the
                # plan did not assume (e.g. detect found a different object set, or
                # a post-pick re-detect changed the remaining set). When a divergence
                # detector is wired AND replan budget remains, re-decompose against
                # the CURRENT world_context/Blackboard (not the stale T=0 context)
                # and re-execute. This is its OWN bounded loop, independent of the
                # pipeline-retry counter (max_obs_replan), so a detector that always
                # reports divergence cannot loop forever.
                while True:
                    reason = self._obs_divergence_reason(trace, obs_replans_used, cfg)
                    if not reason:
                        break
                    obs_replans_used += 1
                    new_tree = self._obs_replan_decompose(
                        task, world_context, context_provider, failures, tree, reason
                    )
                    if new_tree is None:
                        return trace  # re-decompose failed — keep the verified run
                    tree = new_tree
                    trace = self._execute_with_retry(tree, failures)
                    if trace.success:
                        best_trace = trace
                    else:
                        # The post-divergence plan did not verify; fall back to
                        # Layer 3 pipeline retry with the accumulated failures.
                        break
                if trace.success:
                    return trace

            # --- Layer 3: Pipeline retry — full re-plan with failure history ---
            if pipeline_attempt < cfg.max_pipeline_retries:
                if self._on_replan:
                    self._on_replan(
                        f"Re-planning (attempt {pipeline_attempt + 2}): "
                        f"{len(failures)} previous failures"
                    )
                goal_tree = None  # force re-decompose
                logger.info(
                    "VGGHarness: pipeline retry %d/%d with %d failure records",
                    pipeline_attempt + 1, cfg.max_pipeline_retries, len(failures),
                )

        return best_trace or ExecutionTrace(
            goal_tree=tree or GoalTree(goal=task, sub_goals=()),
            steps=(),
            success=False,
            total_duration_sec=0.0,
        )

    def _attach_blackboard(self) -> None:
        """Attach a fresh run-scoped Blackboard to the executor (Stage 1b).

        Fail-soft: a missing import or an executor that does not accept a
        ``blackboard`` (e.g. a bare test double) leaves capture disabled and
        never aborts the run.
        """
        try:
            from vector_os_nano.vcli.cognitive.blackboard import Blackboard
            self._executor.blackboard = Blackboard()
        except Exception as exc:  # noqa: BLE001
            logger.debug("VGGHarness: could not attach blackboard: %s", exc)

    @staticmethod
    def _current_context(
        world_context: str,
        context_provider: Callable[[], str] | None,
    ) -> str:
        """Return a fresh world context (Stage 1b).

        Calls *context_provider* when supplied so each (re)decompose sees current
        state; on any failure or when no provider is given, falls back to the
        static *world_context* (current behavior).
        """
        if context_provider is None:
            return world_context
        try:
            fresh = context_provider()
        except Exception as exc:  # noqa: BLE001
            logger.warning("VGGHarness: context_provider raised: %s", exc)
            return world_context
        return fresh if isinstance(fresh, str) else world_context

    def _obs_divergence_reason(
        self,
        trace: ExecutionTrace,
        obs_replans_used: int,
        cfg: HarnessConfig,
    ) -> str | None:
        """Return the divergence reason for a verified run, or ``None`` (S4-4).

        Consulted ONCE per replan decision (the reason is then threaded into the
        re-decompose so the detector is never invoked twice for one decision).
        Returns a non-empty reason only when a divergence detector is wired, the
        per-run observation-replan budget (``cfg.max_obs_replan``) is not yet
        spent, and the detector reports a non-empty reason for *trace*. With no
        detector this is always ``None``, so the run path is unchanged. The
        detector is consulted defensively — any exception is treated as
        "no divergence" so a misbehaving detector can never abort a verified run.
        """
        if self._obs_divergence is None:
            return None
        if obs_replans_used >= max(0, cfg.max_obs_replan):
            return None
        try:
            reason = self._obs_divergence(trace)
        except Exception as exc:  # noqa: BLE001
            logger.warning("VGGHarness: observation_divergence raised: %s", exc)
            return None
        return reason if reason else None

    def _obs_replan_decompose(
        self,
        task: str,
        world_context: str,
        context_provider: Callable[[], str] | None,
        failures: list[FailureRecord],
        prior_tree: GoalTree | None,
        reason: str,
    ) -> GoalTree | None:
        """Re-decompose after an observed divergence on a verified run (S4-4).

        Builds a FRESH world context via *context_provider* (so the new plan sees
        CURRENT state, not the stale T=0 context), threads the detector's *reason*
        + the prior plan's validation notes into the decompose context, fires the
        ``on_replan`` callback, and returns the new GoalTree (or ``None`` on
        decompose failure). The run-scoped Blackboard is intentionally NOT reset:
        the prior run's captured observations (e.g. the latest detect set) remain
        addressable so a foreach in the new plan iterates the CURRENT set.
        """
        if self._on_replan:
            try:
                self._on_replan(
                    "Re-planning on observed divergence: "
                    f"{reason or 'live observation changed'}"
                )
            except Exception:  # noqa: BLE001
                pass

        fresh_context = self._current_context(world_context, context_provider)
        if reason:
            fresh_context += (
                "\n\nObservation diverged from the previous plan (re-plan around the "
                f"CURRENT observed state):\n  - {reason}"
            )
        prior_notes = tuple(getattr(prior_tree, "validation_notes", ()) or ())
        logger.info(
            "VGGHarness: observation-driven replan (reason=%r)", reason or "(none)"
        )
        return self._decompose_with_context(task, fresh_context, failures, prior_notes)

    def _decompose_with_context(
        self,
        task: str,
        world_context: str,
        failures: list[FailureRecord],
        prior_validation_notes: tuple[str, ...] = (),
    ) -> GoalTree | None:
        """Decompose with failure history + prior validator feedback in context.

        *prior_validation_notes* are the previous attempt's
        ``GoalTree.validation_notes`` (Stage 2b) — dropped/invalid-strategy
        messages. Injecting them tells the next decompose which strategies were
        invalid so it stops hallucinating them.
        """
        enriched_context = world_context
        if failures:
            failure_summary = "\n".join(
                f"  - {f.sub_goal_name}: {f.strategy_tried} failed ({f.error})"
                for f in failures[-5:]  # last 5 failures
            )
            enriched_context += (
                f"\n\nPrevious failures (avoid these strategies):\n{failure_summary}"
            )

        if prior_validation_notes:
            invalid = self._invalid_strategies_from_notes(prior_validation_notes)
            notes_block = "\n".join(f"  - {n}" for n in prior_validation_notes)
            enriched_context += (
                "\n\nValidator rejected part of the previous plan:\n"
                f"{notes_block}"
            )
            if invalid:
                enriched_context += (
                    "\nDo NOT use these invalid strategies again: "
                    f"{', '.join(invalid)}; valid strategies are listed in "
                    "KNOWN_STRATEGIES above."
                )

        try:
            return self._decomposer.decompose(task, enriched_context)
        except Exception as exc:
            logger.warning("VGGHarness: decompose raised: %s", exc)
            return None

    @staticmethod
    def _invalid_strategies_from_notes(notes: tuple[str, ...]) -> list[str]:
        """Extract the invalid strategy names quoted in validator notes.

        Notes have the shape ``strategy 'look_skill' is not valid; ...``. The
        first single-quoted token of such a note is the offending strategy.
        Best-effort and side-effect-free; returns a de-duplicated, ordered list.
        """
        import re

        found: list[str] = []
        for note in notes:
            if "is not valid" not in note:
                continue
            m = re.search(r"'([^']+)'", note)
            if m and m.group(1) not in found:
                found.append(m.group(1))
        return found

    def _execute_with_retry(
        self,
        tree: GoalTree,
        failures: list[FailureRecord],
    ) -> ExecutionTrace:
        """Execute GoalTree with step-level retry (Layer 1 + Layer 2).

        On step failure:
        1. Try alternative strategies for the failed step (Layer 1)
        2. If all strategies exhausted, record failure and continue to next step
           (don't abort the whole tree — some later steps may still succeed)
        """
        cfg = self._config
        trace_start = time.monotonic()
        steps: list[StepRecord] = []
        overall_success = True

        ordered = self._executor._topological_sort(tree)

        for i, sub_goal in enumerate(ordered):
            # --- Abort check ---
            try:
                from vector_os_nano.vcli.cognitive.abort import is_abort_requested
                if is_abort_requested():
                    overall_success = False
                    break
            except ImportError:
                pass

            # Stage 4 (S4-2): a foreach node expands at runtime into N children.
            # Delegate the whole expansion to the executor (it reads the producing
            # step's list off the run blackboard and binds the iteration var per
            # item). Layer-1 strategy retry does not apply to the loop node itself;
            # each expanded child still carries its own verify.
            if getattr(sub_goal, "foreach", None) is not None:
                expanded = self._executor._execute_foreach(sub_goal, self._on_step)
                steps.extend(expanded)
                for child in expanded:
                    if self._executor._stats is not None:
                        try:
                            self._executor._stats.record(
                                strategy_name=child.strategy,
                                sub_goal_name=child.sub_goal_name,
                                success=child.success,
                                duration_sec=child.duration_sec,
                            )
                        except Exception:
                            pass
                    if not child.success:
                        failures.append(FailureRecord(
                            sub_goal_name=child.sub_goal_name,
                            strategy_tried=child.strategy,
                            error=child.error,
                            step_index=i,
                        ))
                        overall_success = False
                continue

            step = self._execute_step_with_retry(sub_goal, i, cfg.max_step_retries)
            steps.append(step)

            if self._on_step:
                try:
                    self._on_step(step)
                except Exception:
                    pass

            # Record stats
            if self._executor._stats is not None:
                try:
                    self._executor._stats.record(
                        strategy_name=step.strategy,
                        sub_goal_name=step.sub_goal_name,
                        success=step.success,
                        duration_sec=step.duration_sec,
                    )
                except Exception:
                    pass

            if not step.success:
                failures.append(FailureRecord(
                    sub_goal_name=step.sub_goal_name,
                    strategy_tried=step.strategy,
                    error=step.error,
                    step_index=i,
                ))
                overall_success = False
                # Don't break — try remaining steps that don't depend on this one
                # (steps with depends_on referencing the failed step will skip)

        total_duration = time.monotonic() - trace_start
        return ExecutionTrace(
            goal_tree=tree,
            steps=tuple(steps),
            success=overall_success,
            total_duration_sec=total_duration,
        )

    def _execute_step_with_retry(
        self,
        sub_goal: SubGoal,
        step_index: int,
        max_retries: int,
    ) -> StepRecord:
        """Execute a single step with strategy retry (Layer 1).

        Tries primary strategy, then fail_action, then asks selector for
        alternatives.
        """
        tried_strategies: set[str] = set()

        for attempt in range(max_retries + 1):
            # Select strategy (first attempt uses sub_goal.strategy, later uses selector)
            if attempt == 0:
                step = self._executor._execute_sub_goal(sub_goal)
            else:
                # Clear strategy to let selector pick an alternative
                retry_goal = SubGoal(
                    name=sub_goal.name,
                    description=sub_goal.description,
                    verify=sub_goal.verify,
                    timeout_sec=sub_goal.timeout_sec,
                    depends_on=sub_goal.depends_on,
                    strategy="",  # force selector to pick fresh
                    strategy_params=sub_goal.strategy_params,
                    fail_action="",
                )
                step = self._executor._execute_sub_goal(retry_goal)

            if step.success:
                return step

            tried_strategies.add(step.strategy)
            if attempt < max_retries:
                logger.info(
                    "VGGHarness: step %s attempt %d/%d failed (%s) — retrying",
                    sub_goal.name, attempt + 1, max_retries + 1, step.error,
                )

        return step  # return last failed attempt
