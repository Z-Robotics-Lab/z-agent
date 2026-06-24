# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Both sim bases conform UNIFORMLY to BaseProtocol (project CLAUDE.md Rule 11).

Pure introspection — NO sim/MuJoCo/torch model is constructed. We inspect the
class attribute surface (methods + properties live in the class dict / MRO), so
this is fast and offline. The point is to catch per-robot method drift: today
MuJoCoG1 lacks several BaseProtocol members MuJoCoGo2 has, which breaks the
"every body conforms uniformly, no method drift" invariant.
"""
from __future__ import annotations

import pytest

from vector_os_nano.hardware.base import BaseProtocol
from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1
from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2

# The full BaseProtocol surface (kept explicit so the test fails loud if a
# member is renamed/removed in base.py without updating conformance here).
_BASE_PROTOCOL_MEMBERS: tuple[str, ...] = (
    "name",
    "connect",
    "disconnect",
    "stop",
    "walk",
    "set_velocity",
    "get_position",
    "get_heading",
    "get_velocity",
    "get_odometry",
    "get_lidar_scan",
    "supports_holonomic",
    "supports_lidar",
)


def test_expected_members_match_protocol() -> None:
    """Our explicit list equals the runtime_checkable Protocol's own attr set."""
    proto_attrs = set(getattr(BaseProtocol, "__protocol_attrs__", set()))
    if proto_attrs:  # py3.12 exposes this; guard if the dunder ever changes
        assert proto_attrs == set(_BASE_PROTOCOL_MEMBERS), (
            f"BaseProtocol attrs {sorted(proto_attrs)} != expected "
            f"{sorted(_BASE_PROTOCOL_MEMBERS)}"
        )


@pytest.mark.parametrize("cls", [MuJoCoGo2, MuJoCoG1], ids=["go2", "g1"])
@pytest.mark.parametrize("member", _BASE_PROTOCOL_MEMBERS)
def test_class_exposes_protocol_member(cls: type, member: str) -> None:
    """Every BaseProtocol member is present on the class (no construction)."""
    assert hasattr(cls, member), (
        f"{cls.__name__} is missing BaseProtocol member '{member}'"
    )


@pytest.mark.parametrize("cls", [MuJoCoGo2, MuJoCoG1], ids=["go2", "g1"])
@pytest.mark.parametrize(
    "method",
    [
        "connect",
        "disconnect",
        "stop",
        "walk",
        "set_velocity",
        "get_position",
        "get_heading",
        "get_velocity",
        "get_odometry",
        "get_lidar_scan",
    ],
)
def test_protocol_methods_are_callable(cls: type, method: str) -> None:
    """Method-shaped members resolve to callables on the class."""
    assert callable(getattr(cls, method)), (
        f"{cls.__name__}.{method} is not callable"
    )


@pytest.mark.parametrize("cls", [MuJoCoGo2, MuJoCoG1], ids=["go2", "g1"])
@pytest.mark.parametrize("prop", ["name", "supports_holonomic", "supports_lidar"])
def test_protocol_properties_are_properties(cls: type, prop: str) -> None:
    """Capability/identity members are exposed as properties on the class."""
    attr = getattr(cls, prop, None)
    assert isinstance(attr, property), (
        f"{cls.__name__}.{prop} should be a property, got {type(attr).__name__}"
    )


def test_g1_disconnect_aliases_close() -> None:
    """G1's disconnect() must exist (sim_tool.stop calls base.disconnect())."""
    assert hasattr(MuJoCoG1, "disconnect")
    assert callable(MuJoCoG1.disconnect)
    # close() is retained — disconnect is an ADDITIVE alias, not a rename.
    assert hasattr(MuJoCoG1, "close")
