# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Routable capabilities (Phase C) — the model-zoo seam.

A capability is anything a sub-goal can route to with a typed (input -> output)
contract and measured stats. C.1 ships the protocol, registry, and the chat
adapter; specialized models (detectors/planners/VLA) register in C.3.
"""
from __future__ import annotations

from zeno.vcli.cognitive.capabilities.chat import LLMChatCapability
from zeno.vcli.cognitive.capabilities.registry import (
    CapabilityRegistry,
    validate_input,
)
from zeno.vcli.cognitive.capabilities.types import (
    Capability,
    CapabilityResult,
)

__all__ = [
    "Capability",
    "CapabilityResult",
    "CapabilityRegistry",
    "LLMChatCapability",
    "validate_input",
]
