# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""World plugins for the agent kernel.

A *world* adapts the domain-general kernel to a domain (dev/code, robot, ...).
The default ``DevWorld`` ships with the kernel; ``RobotWorld`` is selected when
a robot agent is connected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zeno.vcli.worlds.base import DecomposeVocab, World
from zeno.vcli.worlds.registry import (
    WorldRegistry,
    get_world_registry,
    resolve_world,
    resolve_world_named,
)

if TYPE_CHECKING:  # import for type-checkers only — never at runtime module load
    from zeno.vcli.worlds.dev import DevWorld, dev_verify_namespace
    from zeno.vcli.worlds.robot import RobotWorld

# The concrete kernel worlds are re-exported LAZILY (PEP 562). Importing this
# package for the seam (base.World / the registry) must NOT drag in a concrete
# world — that would defeat the registry's lazy ``_ensure_builtin_worlds`` design
# and violate Invariant 4 (the kernel imports no world at module load; worlds
# load only on resolution). ``from zeno.vcli.worlds import DevWorld``
# still works — it resolves through ``__getattr__`` on first access.
# Guarded by tests/vcli/test_plug_and_play_boundary.py.
_LAZY_REEXPORTS = {
    "DevWorld": ("zeno.vcli.worlds.dev", "DevWorld"),
    "dev_verify_namespace": ("zeno.vcli.worlds.dev", "dev_verify_namespace"),
    "RobotWorld": ("zeno.vcli.worlds.robot", "RobotWorld"),
}

__all__ = [
    "World",
    "DecomposeVocab",
    "DevWorld",
    "RobotWorld",
    "dev_verify_namespace",
    "resolve_world",
    "resolve_world_named",
    "WorldRegistry",
    "get_world_registry",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve a concrete-world re-export on first attribute access."""
    target = _LAZY_REEXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(target[0]), target[1])


def __dir__() -> list[str]:
    return sorted(__all__)
