# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""zeno.acceptance — the in-product visual-acceptance subsystem (ADR-002).

The "eyes": same-process render capture for the honest visual second witness. Kept as a
LIGHT package (no eager MuJoCo import — cv2/mujoco load lazily inside ``capture.snapshot``)
so the verdict-emit hook can import it cheaply. The runnable orchestration (gate, harness,
sim-lock) lives under ``tools/acceptance/`` and reuses these primitives.
"""
