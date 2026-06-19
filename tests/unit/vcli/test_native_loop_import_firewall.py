# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""M1 import firewall — native_loop.py must import ONLY the honest spine.

REPLACE-NOT-REBUILD enforced BY CONSTRUCTION (next-prompt.md review fix 5): the
native tool-use producer reuses the EXISTING verify spine and the model owns
decompose/route/replan. If ``native_loop.py`` ever imports the bespoke planner
stack (``goal_decomposer`` / ``goal_executor`` / ``strategy_selector`` /
``vgg_harness``), the strangle has started re-growing a planner — this test FAILS
loudly so that regression cannot land.

It scans the SOURCE (AST), so a transitive runtime import via the engine delegate
does NOT trip it; the firewall is on what native_loop.py itself names.
"""
from __future__ import annotations

import ast
from pathlib import Path

import vector_os_nano.vcli.native_loop as native_loop

# The bespoke planner modules the strangle must NOT depend on. Matched as the LAST
# dotted segment of any import target, so both ``import x.goal_decomposer`` and
# ``from x.goal_decomposer import y`` are caught.
FORBIDDEN_MODULES = frozenset(
    {"goal_decomposer", "goal_executor", "strategy_selector", "vgg_harness"}
)

# The spine native_loop is ALLOWED to lean on (informational — asserted present).
ALLOWED_SPINE_HINTS = frozenset(
    {"actor_causation", "trace_store", "types", "skill_wrapper", "goal_verifier"}
)


def _imported_module_segments(source: str) -> set[str]:
    """Return the set of last-dotted-segments of every imported module name."""
    tree = ast.parse(source)
    segments: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                segments.add(alias.name.rsplit(".", 1)[-1])
                segments.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                segments.add(node.module.rsplit(".", 1)[-1])
                segments.add(node.module)
                for alias in node.names:
                    segments.add(alias.name)
    return segments


def test_native_loop_does_not_import_the_bespoke_planner() -> None:
    source = Path(native_loop.__file__).read_text(encoding="utf-8")
    segments = _imported_module_segments(source)
    leaked = FORBIDDEN_MODULES & segments
    assert not leaked, (
        "native_loop.py imports the bespoke planner stack "
        f"{sorted(leaked)} — the strangle is re-growing a planner. "
        "The MODEL owns decompose/route/replan; the runner only "
        "captures -> dispatches -> verifies -> grades -> records."
    )


def test_native_loop_imports_the_spine() -> None:
    """Sanity: the producer DOES reuse the honest spine (not a parallel re-impl)."""
    source = Path(native_loop.__file__).read_text(encoding="utf-8")
    segments = _imported_module_segments(source)
    assert "actor_causation" in segments
    assert "trace_store" in segments
    assert "skill_wrapper" in segments
