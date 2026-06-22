# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""RobotWorld.register_capabilities — registers the learned 'detect' capability.

Guarded two ways (keeps dev/go2-only/CI byte-identical):
  - only when the agent has an arm (the detector drives the manipulation route);
  - only when torch/transformers are importable.
The model is NOT loaded by registration (DetectorCapability is lazy), so this
runs without weights. We monkeypatch around the torch import-guard so the test
is deterministic whether or not torch is installed.
"""
from __future__ import annotations

import sys

from vector_os_nano.vcli.cognitive.capabilities import CapabilityRegistry
from vector_os_nano.vcli.worlds.robot import RobotWorld


class _Perc:
    def get_color_frame(self):
        import numpy as np

        return np.zeros((240, 320, 3), dtype=np.uint8)


class _ArmAgent:
    def __init__(self, perception=None):
        self._arm = object()  # has an arm
        self._perception = perception


class _BaseOnlyAgent:
    def __init__(self):
        self._arm = None  # go2 base only, no arm


def _torch_present() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


def test_arm_agent_registers_detect_when_torch_present():
    if not _torch_present():
        # Without torch the guard registers nothing — assert that, then done.
        reg = CapabilityRegistry()
        RobotWorld().register_capabilities(reg, _ArmAgent(), backend=None)
        assert "detect" not in reg.names()
        return
    reg = CapabilityRegistry()
    RobotWorld().register_capabilities(reg, _ArmAgent(), backend=None)
    assert "detect" in reg.names()
    cap = reg.get("detect")
    assert cap.kind == "detector" and cap.side_effecting is False
    # registration must NOT have loaded the model (lazy)
    assert getattr(cap, "_detector", None) is None


def test_detect_capability_bound_to_agent_perception():
    """R36: registration BINDS the agent's live RGB source into the capability so
    a producer-routed detect step can perceive on the capability-dispatch path
    (the kernel context is a SkillContext with no frame)."""
    if not _torch_present():
        return  # registration is a no-op without torch; covered elsewhere
    perc = _Perc()
    reg = CapabilityRegistry()
    RobotWorld().register_capabilities(reg, _ArmAgent(perception=perc), backend=None)
    cap = reg.get("detect")
    assert cap is not None
    assert getattr(cap, "_perception", None) is perc


def test_base_only_agent_registers_nothing():
    reg = CapabilityRegistry()
    RobotWorld().register_capabilities(reg, _BaseOnlyAgent(), backend=None)
    assert "detect" not in reg.names()
    assert len(reg) == 0


def test_no_agent_registers_nothing():
    reg = CapabilityRegistry()
    RobotWorld().register_capabilities(reg, None, backend=None)
    assert len(reg) == 0


def test_missing_torch_registers_nothing(monkeypatch):
    """Simulate torch absent: the ImportError guard registers nothing (CI-safe)."""
    real_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name in ("torch", "transformers"):
            raise ImportError(f"simulated-absent: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)
    # Drop any already-imported module so the guarded import actually re-runs.
    for mod in ("torch", "transformers"):
        monkeypatch.setitem(sys.modules, mod, None)

    reg = CapabilityRegistry()
    RobotWorld().register_capabilities(reg, _ArmAgent(), backend=None)
    assert "detect" not in reg.names()
