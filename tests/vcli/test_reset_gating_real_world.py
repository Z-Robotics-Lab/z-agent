# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""/reset must be honest per world (sim-to-real migration, secondary audit #2).

Field forensics (2026-07-10, real-robot REPL audit): the ``/reset`` REPL command
writes the SIM vnav-bridge file flag ``/tmp/vector_reset_pose`` and prints a green
"Robot will stand up at current position." Its help text already says "sim only".
On go2w_real the driver is ROS2/nav.sh and NEVER reads that flag — the only
consumer is ``scripts/go2_vnav_bridge.py`` (the MuJoCo sim path). So on real
hardware the command is a dead no-op presented to the operator as a working
tip-over recovery — a stale sim affordance masquerading as a live hardware
recovery (safety-adjacent UX).

Fix (additive, worlds-untouched-stay-identical): a duck-typed optional world hook
``supports_pose_reset() -> bool``. A world that OMITS the hook is byte-identical to
today (dev / sim go2 keep writing the flag). go2w_real returns False, so ``/reset``
refuses honestly (no flag write, no false-green) and names the real recovery path
(站起来 / standup + resume). Strictly stricter — it never *adds* a working reset,
it only stops LYING on a world that has no consumer.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from zeno.vcli import cli


_RESET_FLAG = "/tmp/vector_reset_pose"


class _DummyRegistry:
    """Minimal registry stand-in (the /reset branch never touches it)."""

    def list_tools(self) -> list[str]:
        return []


@pytest.fixture(autouse=True)
def _clean_flag() -> Any:
    """Ensure the sim reset flag is absent before and after each test."""
    try:
        os.remove(_RESET_FLAG)
    except FileNotFoundError:
        pass
    yield
    try:
        os.remove(_RESET_FLAG)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# The world hook (opt-out): absent => byte-identical; False => honest refusal
# ---------------------------------------------------------------------------


def test_go2w_real_declines_pose_reset() -> None:
    """The REAL Go2W world declares it does NOT support the sim pose-reset flag."""
    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    world = Go2WRealWorld()
    assert hasattr(world, "supports_pose_reset"), (
        "go2w_real must expose supports_pose_reset() so /reset can refuse honestly"
    )
    assert world.supports_pose_reset() is False


def test_dev_world_has_no_pose_reset_hook_byte_identical() -> None:
    """Dev world omits the hook entirely — /reset stays byte-identical (writes flag)."""
    from zeno.vcli.worlds.dev import DevWorld

    # The whole point of an OPT-OUT hook: worlds that do not set it are untouched.
    assert not hasattr(DevWorld(), "supports_pose_reset")


def test_sim_go2w_world_omits_hook_byte_identical() -> None:
    """The Isaac (sim) go2w world keeps the working reset — must NOT gain the hook."""
    from zeno.vcli.worlds.go2w import IsaacGo2WWorld

    # The sim path IS the vnav-bridge consumer of the flag; it stays byte-identical.
    assert not hasattr(IsaacGo2WWorld(), "supports_pose_reset")


# ---------------------------------------------------------------------------
# /reset behaviour, driven through the real _handle_slash_command
# ---------------------------------------------------------------------------


def test_reset_on_real_world_refuses_and_writes_no_flag() -> None:
    """On go2w_real, /reset must NOT write the sim flag and must not print success."""
    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    app_state: dict[str, Any] = {"world": Go2WRealWorld()}
    cont = cli._handle_slash_command(
        "reset", [], registry=_DummyRegistry(), app_state=app_state
    )
    assert cont is True
    assert not os.path.exists(_RESET_FLAG), (
        "/reset on go2w_real must not write /tmp/vector_reset_pose "
        "(no consumer on hardware — writing it is a false-green no-op)"
    )


def test_reset_without_world_still_writes_flag_byte_identical() -> None:
    """No world in app_state (sim/dev default) => current behaviour: flag written."""
    app_state: dict[str, Any] = {"world": None}
    cont = cli._handle_slash_command(
        "reset", [], registry=_DummyRegistry(), app_state=app_state
    )
    assert cont is True
    assert os.path.exists(_RESET_FLAG), (
        "/reset with no gating world must stay byte-identical (writes the sim flag)"
    )


def test_reset_with_hookless_world_writes_flag_byte_identical() -> None:
    """A world that omits the hook (dev) => byte-identical: flag written."""
    from zeno.vcli.worlds.dev import DevWorld

    app_state: dict[str, Any] = {"world": DevWorld()}
    cont = cli._handle_slash_command(
        "reset", [], registry=_DummyRegistry(), app_state=app_state
    )
    assert cont is True
    assert os.path.exists(_RESET_FLAG)


def test_reset_hook_raising_is_swallowed_and_treated_as_supported() -> None:
    """A world whose hook raises must not crash /reset; falls back to writing flag."""

    class _AngryWorld:
        name = "angry"

        def supports_pose_reset(self) -> bool:
            raise RuntimeError("boom")

    app_state: dict[str, Any] = {"world": _AngryWorld()}
    cont = cli._handle_slash_command(
        "reset", [], registry=_DummyRegistry(), app_state=app_state
    )
    # Never crashes the REPL; a broken hook degrades to the legacy behaviour.
    assert cont is True
    assert os.path.exists(_RESET_FLAG)
