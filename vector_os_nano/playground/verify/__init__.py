# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Playground verify predicates — deterministic sim-oracle ground truth.

These predicates read the sim's deterministic ground truth (object positions,
joint positions, FK) — NOT the VLM. The VLM detect/describe pipeline stays the
agent's perception *skill*; these predicates check the oracle. Generator
(perceive) and verifier (check) stay independent (ADR-008).
"""

from __future__ import annotations
