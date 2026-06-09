# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""CapabilityRegistry — per-run registry of routable capabilities.

Worlds populate it via ``World.register_capabilities`` (the dev world registers
the chat capability; the robot world will register detectors/planners/VLA
policies in Phase C.3). The StrategySelector reads the registered names to know
which strategy strings resolve to capability dispatch; the GoalExecutor looks a
capability up by name at execution time.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def validate_input(schema: dict[str, Any], payload: dict[str, Any]) -> str | None:
    """Light boundary check: every ``schema['required']`` key is present.

    Returns an error message string on failure, or ``None`` when the payload is
    acceptable. Intentionally minimal in C.1 — capabilities validate their own
    value shapes inside ``invoke``.
    """
    if not isinstance(payload, dict):
        return "capability input must be a dict"
    required = schema.get("required", []) if isinstance(schema, dict) else []
    missing = [k for k in required if k not in payload]
    if missing:
        return f"missing required input(s): {', '.join(missing)}"
    return None


class CapabilityRegistry:
    """Collects Capability instances by name."""

    def __init__(self) -> None:
        self._caps: dict[str, Any] = {}

    def register(self, capability: Any) -> None:
        """Register *capability* (keyed by ``capability.name``); replaces by name."""
        name = getattr(capability, "name", "")
        if not name:
            logger.warning("CapabilityRegistry: ignoring capability with no name")
            return
        self._caps[name] = capability

    def get(self, name: str) -> Any | None:
        """Return the capability registered under *name*, or None."""
        return self._caps.get(name)

    def names(self) -> frozenset[str]:
        """Return the set of registered capability names."""
        return frozenset(self._caps.keys())

    def __contains__(self, name: object) -> bool:
        return name in self._caps

    def __len__(self) -> int:
        return len(self._caps)
