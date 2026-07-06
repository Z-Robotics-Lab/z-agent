# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Playground verify predicates — deterministic sim-oracle ground truth.

These predicates read the sim's deterministic ground truth — NOT the VLM. The
arm/scene predicates read object positions, joint positions and FK off the
connected arm; the base predicates read position/heading off the connected
mobile base (Go2). The VLM detect/describe pipeline stays the agent's perception
*skill*; these predicates check the oracle. Generator (perceive) and verifier
(check) stay independent (ADR-008).
"""

from __future__ import annotations
