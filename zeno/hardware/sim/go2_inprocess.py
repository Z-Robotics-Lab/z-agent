# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Single-source in-process Go2 agent builder (Rule 3/11).

This is the ONE canonical constructor for the lightweight, fully in-process
Go2 agent: MuJoCoGo2 base (real physics, no external process), optional Piper
arm, RGB-D perception, manipulation skills (perception_grasp + pick/place),
Go2 locomotion skills, persistent scene graph, and VLM perception.

Both launchers call it so they can never drift:

* ``vector-cli --sim-go2``      -> :func:`zeno.vcli.cli._init_agent`
* bare-REPL NL "启动 go2 仿真"     -> ``SimStartTool._start_go2`` (VECTOR_NO_ROS2=1)

It deliberately does NOT launch the external ROS2 nav stack — callers that want
it (cli.py's --sim-go2 default) add it *around* this call. VECTOR_NO_ROS2=1
yields the proven fully-in-process fetch/place path (D163/D164 Decision C(b)):
in-process ``MuJoCoGo2.navigate_to`` plans collision-free via the
visibility-graph planner, so FAR/TARE is only needed for explore, never fetch.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _noop(_msg: str) -> None:  # pragma: no cover - trivial
    pass


def reconcile_render_backend(gui: bool) -> bool:
    """Reconcile the offscreen GL backend with the viewer request; return effective gui.

    EGL (headless offscreen render) and a GLFW passive viewer CANNOT coexist in one
    process: opening the viewer starves the perception renderer's context
    ('Failed to make the EGL context current'), so fetch/place perceive nothing and
    grade verified=False (verified 2026-07-01: egl+gui=True grasp 0/3 vs egl+headless
    5/5 vs glfw+gui=True 2/2). A GLFW viewer may open ONLY when the offscreen backend
    is glfw, which needs a display.

    mujoco binds its GL backend at import time, so this MUST run before the first
    ``import mujoco``. Policy:
      * viewer wanted + display + backend not yet bound -> bind glfw, keep the viewer;
      * backend already glfw + display               -> keep the viewer;
      * otherwise (headless, no display, or egl already bound) -> egl, DROP the viewer
        so perception always keeps its GL context.
    """
    import sys as _sys

    display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    mujoco_bound = "mujoco" in _sys.modules
    cur = os.environ.get("MUJOCO_GL", "").lower()

    if gui and display:
        if not mujoco_bound:
            # Backend not yet bound: a viewer is requested and a display exists, so
            # bind glfw (viewer + offscreen renderer coexist). Override even an
            # explicit MUJOCO_GL=egl here — egl + a viewer is simply broken, and the
            # caller asked for a window, so glfw is the only way to honour gui=True.
            os.environ["MUJOCO_GL"] = "glfw"
            return True
        if cur == "glfw":
            return True  # already glfw-bound -> viewer is safe
    # Headless, no display, or egl already bound: protect perception, no viewer.
    if gui:
        logger.warning(
            "MuJoCoGo2: GLFW viewer suppressed (no display or EGL backend already "
            "bound) so the perception renderer keeps its GL context; running headless."
        )
    os.environ.setdefault("MUJOCO_GL", "egl")
    return False


def build_inprocess_go2_agent(
    *,
    gui: bool = True,
    with_arm: bool = False,
    api_key: str = "",
    config: dict[str, Any] | None = None,
    status: Callable[[str], None] | None = None,
) -> Any:
    """Build the fully in-process Go2 agent and return it.

    Args:
        gui: open the GLFW viewer window (False = headless real physics).
        with_arm: attach the in-process Piper arm + manipulation skills.
        api_key: OpenRouter/LLM key for the optional VLM perception backend.
        config: agent config dict (from ``config/user.yaml`` when present).
        status: optional human-facing progress sink (e.g. rich console.print);
            everything is also logged at debug level. Defaults to a no-op.

    Returns:
        A fully-wired ``Agent`` whose ``_base`` is the connected ``MuJoCoGo2``.
        The external ROS2 nav stack is NOT launched here.
    """
    emit = status or _noop
    cfg = config or {}

    # The MuJoCoGo2 scene (bare go2 vs go2+piper) is selected by connect() via
    # _build_room_scene_xml(), which reads VECTOR_SIM_WITH_ARM. The in-process
    # builder is authoritative: set the env from the with_arm param BEFORE the
    # base is built so the arm scene loads regardless of how the caller was
    # launched (the ROS2 path sets it on the child_env instead — same contract).
    os.environ["VECTOR_SIM_WITH_ARM"] = "1" if with_arm else "0"

    # Reconcile the offscreen GL backend with the viewer request BEFORE mujoco is
    # imported (it binds the backend at import). Without this, gui=True under the
    # default egl backend starves the perception renderer and fetch/place perceive
    # nothing (see reconcile_render_backend).
    gui = reconcile_render_backend(gui)

    from zeno.core.agent import Agent  # type: ignore[import]
    from zeno.hardware.sim.mujoco_go2 import MuJoCoGo2  # type: ignore[import]

    emit("Starting Go2 MuJoCo simulation...")
    base = MuJoCoGo2(gui=gui, room=True, backend="auto")
    base.connect()
    base.stand()

    # Attach the in-process Piper arm when requested so the full fetch (look ->
    # navigate_to_object -> perception_grasp) and pick/place are reachable — a
    # capability behind a flag is NOT done (North Star).
    piper_arm = piper_gripper = None
    if with_arm:
        try:
            from zeno.hardware.sim.mujoco_piper import MuJoCoPiper
            from zeno.hardware.sim.mujoco_piper_gripper import (
                MuJoCoPiperGripper,
            )

            piper_arm = MuJoCoPiper(base)
            piper_arm.connect()
            piper_gripper = MuJoCoPiperGripper(base)
            piper_gripper.connect()
            emit("Piper arm attached (in-process)")
        except Exception as exc:  # noqa: BLE001 — arm optional, never crash launch
            emit(f"Piper arm unavailable: {exc}")
            piper_arm = piper_gripper = None

    agent = Agent(
        base=base, arm=piper_arm, gripper=piper_gripper,
        llm_api_key=api_key, config=cfg,
    )

    # Register Go2 locomotion skills.
    from zeno.skills.go2 import get_go2_skills

    for skill in get_go2_skills():
        agent._skill_registry.register(skill)

    # Manipulation (Piper pick/place + perception-grasp) — single-sourced with
    # the ROS2 NL path via register_manipulation_skills so the launchers never
    # drift (Rule 3/11).
    if piper_arm is not None:
        from zeno.skills.manipulation_setup import (
            register_manipulation_skills,
        )

        if register_manipulation_skills(agent, base):
            emit("Manipulation: perception_grasp + pick/place")

    # VLM perception (GPT-4o via OpenRouter), optional.
    if api_key:
        try:
            from zeno.perception.vlm_go2 import Go2VLMPerception

            agent._vlm = Go2VLMPerception(config={"api_key": api_key})
            emit("VLM: GPT-4o via OpenRouter")
        except Exception:  # noqa: BLE001 — VLM optional
            agent._vlm = None

    # Real RGB-D + detector + segmenter perception over the in-process base so
    # look/explore can depth-localize VLM-named objects to accurate world
    # (x, y, z). Single-sourced with the ROS2 launcher via _build_go2_perception
    # (Rule 3/11) — leaves perception None when the base has no camera.
    from zeno.vcli.tools.sim_tool import _build_go2_perception

    agent._perception = _build_go2_perception(base)
    if agent._perception is not None:
        emit("Perception: RGB-D detector + segmenter")

    # Persistent scene graph (rooms -> viewpoints -> objects).
    from zeno.core.scene_graph import SceneGraph

    sg_path = os.path.expanduser("~/.zeno/scene_graph.yaml")
    os.makedirs(os.path.dirname(sg_path), exist_ok=True)
    sg = SceneGraph(persist_path=sg_path)
    sg.load()
    sg_stats = sg.stats()
    if sg_stats["rooms"] > 0:
        emit(
            f"Memory: scene graph restored ({sg_stats['rooms']} rooms, "
            f"{sg_stats['objects']} objects)"
        )
    else:
        emit("Memory: scene graph (rooms -> viewpoints -> objects)")
    agent._spatial_memory = sg
    base._scene_graph = agent._spatial_memory

    return agent
