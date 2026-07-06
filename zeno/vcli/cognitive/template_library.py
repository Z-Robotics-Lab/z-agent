# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""TemplateLibrary — store, persist, and retrieve GoalTemplates.

Phase 2 matching strategy: simple keyword matching (no LLM required).
Phase 3 can extend with LLM-based semantic matching.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from zeno.vcli.cognitive.types import GoalTree, SubGoal
from zeno.vcli.cognitive.experience_compiler import GoalTemplate, SubGoalTemplate

logger = logging.getLogger(__name__)

# Informational default location (the live path is derived from the persist_dir the
# engine passes — ~/.zeno via cli.py). ~/.zeno is the product home post-rename.
_DEFAULT_PATH = os.path.expanduser("~/.zeno/goal_templates.json")

# On-disk shape v2 carries SubGoalTemplate.strategy_params so tool_call /
# code-as-policy payloads survive compile -> reuse. The loader is tolerant:
# v1 files (no strategy_params key) load with an empty payload, and unknown
# keys are ignored — no migration needed.

# ---------------------------------------------------------------------------
# Known keyword sets for simple parameter extraction
# ---------------------------------------------------------------------------

_KNOWN_ROOMS = {
    "kitchen", "bedroom", "hallway", "bathroom", "livingroom", "living_room",
    "garage", "office", "garden", "dining", "corridor", "lobby", "lab",
    "storage", "library", "entrance", "room",
}

_KNOWN_OBJECTS = {
    "cup", "book", "key", "phone", "laptop", "bag", "bottle", "pen", "pencil",
    "plate", "glass", "chair", "table", "box", "ball", "toy", "remote",
    "tablet", "charger", "wallet", "hat", "shoes", "jacket",
}

# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------

def _sub_goal_template_to_dict(sgt: SubGoalTemplate) -> dict:
    return {
        "name_pattern": sgt.name_pattern,
        "description_pattern": sgt.description_pattern,
        "verify_pattern": sgt.verify_pattern,
        "strategy": sgt.strategy,
        "timeout_sec": sgt.timeout_sec,
        "depends_on": list(sgt.depends_on),
        "fail_action": sgt.fail_action,
        "strategy_params": dict(getattr(sgt, "strategy_params", {}) or {}),
    }


def _sub_goal_template_from_dict(d: dict) -> SubGoalTemplate:
    sp = d.get("strategy_params", {})
    return SubGoalTemplate(
        name_pattern=d["name_pattern"],
        description_pattern=d["description_pattern"],
        verify_pattern=d["verify_pattern"],
        strategy=d.get("strategy", ""),
        timeout_sec=float(d.get("timeout_sec", 30.0)),
        depends_on=tuple(d.get("depends_on", [])),
        fail_action=d.get("fail_action", ""),
        strategy_params=dict(sp) if isinstance(sp, dict) else {},
    )


def _goal_template_to_dict(t: GoalTemplate) -> dict:
    return {
        "name": t.name,
        "description": t.description,
        "parameters": list(t.parameters),
        "sub_goal_templates": [_sub_goal_template_to_dict(s) for s in t.sub_goal_templates],
        "success_count": t.success_count,
        "fail_count": t.fail_count,
    }


def _goal_template_from_dict(d: dict) -> GoalTemplate:
    return GoalTemplate(
        name=d["name"],
        description=d.get("description", ""),
        parameters=tuple(d.get("parameters", [])),
        sub_goal_templates=tuple(
            _sub_goal_template_from_dict(s) for s in d.get("sub_goal_templates", [])
        ),
        success_count=int(d.get("success_count", 0)),
        fail_count=int(d.get("fail_count", 0)),
    )


# ---------------------------------------------------------------------------
# Keyword extraction from task string
# ---------------------------------------------------------------------------

def _tokenize(task: str) -> set[str]:
    """Split task string into lowercase word tokens."""
    import re
    return set(re.findall(r"[a-z]+", task.lower()))


def _extract_param_values(
    task: str,
    parameters: tuple[str, ...],
) -> dict[str, str] | None:
    """Attempt to extract values for each parameter from the task string.

    Returns a mapping {param_name: value} if all parameters can be filled,
    or None if any parameter cannot be resolved.
    """
    tokens = _tokenize(task)
    result: dict[str, str] = {}

    for param in parameters:
        value: str | None = None

        if param == "room":
            for token in tokens:
                if token in _KNOWN_ROOMS:
                    value = token
                    break
        elif param == "object":
            for token in tokens:
                if token in _KNOWN_OBJECTS:
                    value = token
                    break
        else:
            # Generic param — try to find any content word not already used
            used = set(result.values())
            for token in tokens:
                if token not in _KNOWN_ROOMS and token not in _KNOWN_OBJECTS:
                    if token not in used:
                        value = token
                        break

        if value is None:
            return None  # Could not fill this parameter
        result[param] = value

    return result


# ---------------------------------------------------------------------------
# Substitution helpers
# ---------------------------------------------------------------------------

def _substitute(pattern: str, params: dict[str, str]) -> str:
    """Replace ${param} placeholders in pattern with actual values."""
    result = pattern
    for key, value in params.items():
        result = result.replace(f"${{{key}}}", value)
    return result


def _substitute_payload(value, params: dict[str, str]):
    """Recursively substitute ${param} placeholders inside a strategy payload."""
    if isinstance(value, str):
        return _substitute(value, params)
    if isinstance(value, dict):
        return {k: _substitute_payload(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_payload(v, params) for v in value]
    return value


def _instantiate_sub_goal(sgt: SubGoalTemplate, params: dict[str, str]) -> SubGoal:
    """Create a concrete SubGoal from a SubGoalTemplate and parameter values.

    Strategy payload resolution (in priority order):
    1. A stored ``strategy_params`` on the template -> substitute ${param} in its
       string leaves (carries tool_call/code payloads through reuse, verbatim for
       concrete templates).
    2. Back-compat: a strategy with no stored payload -> the extracted params
       (the historical robot behaviour for templates compiled before v2).
    3. No strategy -> empty payload.
    """
    depends_on = tuple(_substitute(dep, params) for dep in sgt.depends_on)
    stored = dict(getattr(sgt, "strategy_params", {}) or {})
    if stored:
        strategy_params = _substitute_payload(stored, params)
    elif sgt.strategy:
        strategy_params = dict(params)
    else:
        strategy_params = {}
    return SubGoal(
        name=_substitute(sgt.name_pattern, params),
        description=_substitute(sgt.description_pattern, params),
        verify=_substitute(sgt.verify_pattern, params),
        strategy=sgt.strategy,
        timeout_sec=sgt.timeout_sec,
        depends_on=depends_on,
        fail_action=sgt.fail_action,
        strategy_params=strategy_params,
    )


# ---------------------------------------------------------------------------
# TemplateLibrary
# ---------------------------------------------------------------------------

class TemplateLibrary:
    """Store, retrieve, and persist GoalTemplates."""

    def __init__(self, persist_path: str | None = None) -> None:
        # None => in-memory only (no home-dir reads/writes), matching
        # StrategyStats. _DEFAULT_PATH is a documented constant, not an
        # automatic fallback.
        self._path: str | None = persist_path
        self._templates: list[GoalTemplate] = []
        self.load()

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, template: GoalTemplate) -> None:
        """Add or replace a template (matched by name)."""
        self._templates = [t for t in self._templates if t.name != template.name]
        self._templates.append(template)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def match(self, task: str) -> tuple[GoalTemplate, dict[str, str]] | None:
        """Match task description to a stored template using keyword extraction.

        Returns (template, extracted_params) or None if no confident match.

        For concrete templates (0 parameters), any task containing a keyword
        related to the template name is considered a match.
        """
        best: tuple[GoalTemplate, dict[str, str]] | None = None

        for template in self._templates:
            if not template.parameters:
                # Concrete template — match based on template name keywords vs task tokens
                if self._matches_concrete(template, task):
                    best = (template, {})
                    break
            else:
                params = _extract_param_values(task, template.parameters)
                if params is not None:
                    # Confirm there's enough signal — at least one param matched something
                    if params:
                        best = (template, params)
                        break

        return best

    def _matches_concrete(self, template: GoalTemplate, task: str) -> bool:
        """Check if a task string is matched by a concrete template.

        Side-effecting sub-goals (``tool_call`` / ``code_as_policy``) require the
        task to contain ALL words of the sub-goal name (full subset): a wrong
        autonomous dispatch is far costlier than a missed cache hit, and a single
        shared token (e.g. "write") must not hijack an unrelated task into a stale
        tool_call. Non-side-effecting sub-goals (skills/primitives) keep the
        lenient single-token match so synonym reuse still works ("go to kitchen"
        -> a ``reach_kitchen`` template). A miss here just falls back to LLM
        decomposition, which is the safe default.
        """
        tokens = _tokenize(task)
        for sgt in template.sub_goal_templates:
            name_words = set(sgt.name_pattern.lower().replace("_", " ").split())
            if not name_words:
                continue
            if sgt.strategy in ("tool_call", "code_as_policy"):
                if name_words.issubset(tokens):
                    return True
            elif name_words & tokens:
                return True
        return False

    # ------------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------------

    def instantiate(self, template: GoalTemplate, params: dict[str, str]) -> GoalTree:
        """Create a concrete GoalTree from template + parameter values."""
        sub_goals = tuple(
            _instantiate_sub_goal(sgt, params)
            for sgt in template.sub_goal_templates
        )
        # Build a descriptive goal string
        goal = _substitute(template.description, params)
        return GoalTree(goal=goal, sub_goals=sub_goals)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist templates to JSON file (no-op in in-memory mode)."""
        if self._path is None:
            return
        path = Path(self._path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [_goal_template_to_dict(t) for t in self._templates]
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            logger.debug("TemplateLibrary: saved %d templates to %s", len(self._templates), path)
        except OSError as exc:
            logger.warning("TemplateLibrary: save failed: %s", exc)

    def load(self) -> None:
        """Load templates from JSON file (no-op in in-memory mode / if absent)."""
        if self._path is None:
            return
        path = Path(self._path)
        if not path.exists():
            return
        try:
            raw = path.read_text()
            data = json.loads(raw)
            self._templates = [_goal_template_from_dict(d) for d in data]
            logger.debug("TemplateLibrary: loaded %d templates from %s", len(self._templates), path)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("TemplateLibrary: load failed (%s) — starting empty", exc)
            self._templates = []
