# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""M1 STEP 3 (C) — native producer in the DEV world: a real, documented leak finding.

Steps 1-2 + 3A-B proved the native producer covers the go2 ACTION surface (walk,
turn -> at_position, facing). The legacy planner's other job is being WORLD-AGNOSTIC:
the same loop must ACT in the dev world too (write a file, run a tool) and prove it
with a dev verify predicate. This module probes that — and surfaces a REAL FINDING the
M1-step-3 prompt explicitly asked to report if it exists: through the REAL
``cli.main --native-loop`` PTY, the native loop CANNOT act in the dev world yet,
because it offers NO dev action tools. We document the leak precisely AND prove the
gap is the cli.main wiring, not the native PRODUCER.

THE LEAK (verified empirically, not asserted on paper):

    ``native_loop._build_motor_tools(agent)`` builds the loop's action surface from
    ``wrap_skills(agent)`` — i.e. ``agent._skill_registry``. In the dev world,
    ``cli._init_agent`` returns ``None`` (no ``--sim``/``--sim-go2``), so there is no
    agent and no skill registry: the loop offers ONLY ``verify`` + ``finish`` and
    ZERO action tools. The dev world's ONLY action mechanism is the LEGACY planner's
    ``tool_call`` strategy, which dispatches kernel tools (``file_write`` / ``bash``
    via ``DEV_TOOL_ALLOWLIST`` + ``ToolDispatcher``). The native loop never wires that
    kernel "code" toolset. So a dev write-then-verify script through
    ``cli.main --native-loop`` dispatches ``file_write`` -> "Unknown tool", writes
    NOTHING, and ``path_contains`` fails -> RAN / exit 2.

This is a PLANNER-ONLY mechanism native does not yet cover: the dev-world ACTION
path. It is NOT a spine/grading defect (the verify spine, the dev predicates, and the
GROUNDED classification all work — ``path_contains`` is a PREDICATE oracle and grades
GROUNDED on a True read). It is purely that the native loop's action surface is
``wrap_skills(agent)`` and the dev world hands it no agent.

THE PRODUCER IS WORLD-AGNOSTIC (the second test proves the gap is wiring, not native):
when a dev action IS wrapped as a skill onto an agent (the SAME registration pattern
the trichotomy teleport case uses), ``run_turn_native`` dispatches it, the file is
written, and ``verify(path_contains(...))`` grades GROUNDED / verified True / exit 0
through the UNTOUCHED spine. So the native PRODUCER already works outside go2; closing
the leak is a wiring change (surface the dev "code" toolset as native action tools),
deferred to the orchestrator — it is NOT a deletion blocker hidden in the producer.

This file needs NO live key and NO sim (it is a dev PTY + an in-process run). Reproduce::

    PATH=/usr/bin:$PATH .venv/bin/python -m pytest \\
      tests/vcli/test_native_loop_devworld_pty.py -v -s
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tests.harness.pty_cli import run_cli_turn


# ---------------------------------------------------------------------------
# (C.1) THE LEAK — through the REAL cli.main --native-loop PTY, dev world
# ---------------------------------------------------------------------------


def test_native_devworld_via_cli_main_offers_no_action_tools_so_write_leaks() -> None:
    """A dev write-then-verify script through cli.main --native-loop -> RAN / exit 2.

    The documented leak: the native loop in the dev world (no agent) offers no
    action tools, so ``file_write`` is an Unknown tool, the file is never written,
    and ``path_contains`` fails -> RAN. The verify SPINE is honest throughout (it
    correctly reports the file was not created); the gap is the missing dev ACTION
    surface, captured here so the orchestrator sees exactly what native does NOT yet
    cover before any legacy deletion.
    """
    r = run_cli_turn(
        "create out.txt containing the word ready",
        tool_script={
            "turns": [
                {"tool_calls": [
                    {"name": "file_write",
                     "input": {"file_path": "out.txt", "content": "ready\n"}}
                ]},
                {"tool_calls": [
                    {"name": "verify",
                     "input": {"expr": "path_contains('out.txt', 'ready')"}}
                ]},
                {"tool_calls": [{"name": "finish", "input": {}}], "stop_reason": "end_turn"},
            ]
        },
        extra_args=["--native-loop"],
        timeout_sec=90.0,
    )
    print(f"\n[devworld leak] cli.main --native-loop -> {r.verdict}")
    # The honest spine reports the write never happened: not verified, RAN, exit 2.
    assert r.verified is False, f"dev write must NOT verify (no action tool); {r.verdict}"
    assert r.evidence == "RAN", f"got evidence={r.evidence}; {r.verdict}"
    assert r.exit_code == 2, f"ran-not-verified must exit 2; got {r.exit_code}"
    per_step = r.verdict.get("per_step") or []
    assert per_step, f"expected one verify-only step; got {per_step}"
    step = per_step[0]
    # The TELL of the leak: the producing strategy is EMPTY (file_write was an Unknown
    # tool, so no action chain was recorded) and the verify failed (file not written).
    assert step["strategy"] == "", (
        f"native dev loop has no action tool -> empty strategy; got "
        f"{step['strategy']!r}. If this is non-empty, the leak is CLOSED."
    )
    assert step["verify"].startswith("path_contains"), f"got verify={step['verify']!r}"
    assert step["verify_result"] is False, (
        "file_write is not a native tool, so the file was never written and "
        "path_contains must be False"
    )
    assert step["evidence"] == "RAN"


# ---------------------------------------------------------------------------
# (C.2) THE PRODUCER IS WORLD-AGNOSTIC — native ACTS in dev when a skill is wrapped
# ---------------------------------------------------------------------------


def test_native_devworld_grounds_when_dev_action_skill_is_wrapped() -> None:
    """run_turn_native covers a dev write -> verify(path_contains) when the action is a
    wrapped skill -> GROUNDED / verified True / exit 0.

    Same registration pattern as the trichotomy teleport case (a test-only skill on a
    real ``Agent``), but a DEV (non-robot) action: write a file. This isolates the
    leak to the cli.main dev-world wiring (no agent -> no action tools) and proves the
    native PRODUCER + the honest spine already work outside go2. ``path_contains`` is
    a PREDICATE oracle, so a True read grades GROUNDED; the step is NOT_GRADED for
    actor-causation (a dev predicate, not a robot predicate) -> no downgrade.
    """
    from vector_os_nano.core.agent import Agent
    from vector_os_nano.core.types import SkillResult
    from vector_os_nano.vcli.cognitive.actor_causation import ActorCaused
    from vector_os_nano.vcli.cognitive.trace_store import (
        classify_step_evidence,
        verify_oracle_names,
    )
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.permissions import PermissionContext
    from vector_os_nano.vcli.session import Session
    from vector_os_nano.vcli.tools.base import CategorizedToolRegistry
    from vector_os_nano.vcli.verdict import VerdictReport
    from vector_os_nano.vcli.worlds.dev import DevWorld

    from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn

    # A test-only DEV action skill: writes a file (relative to cwd, the same tree the
    # dev ``path_contains`` predicate reads). No robot, no motor — a pure dev action.
    class _WriteFileSkill:
        name = "write_file"
        description = "TEST-ONLY: write text content to a file (a dev action skill)."
        parameters = {
            "file_path": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
        }
        preconditions: list[str] = []
        effects: dict = {}

        def execute(self, params, context):
            Path(params["file_path"]).write_text(str(params.get("content", "")), encoding="utf-8")
            return SkillResult(success=True, result_data={"file_path": params.get("file_path")})

    prev_cwd = os.getcwd()
    work_dir = tempfile.mkdtemp(prefix="native_devworld_")
    os.chdir(work_dir)
    try:
        # A dev-style agent: NO hardware (arm/base/gripper all None), one dev action
        # skill registered — exactly the surface wrap_skills would expose if the dev
        # world handed the loop an agent.
        agent = Agent(config={})
        agent._skill_registry.register(_WriteFileSkill())

        backend = FakeToolScriptBackend.from_tool_script([
            tool_turn(("write_file", {"file_path": "out.txt", "content": "ready\n"})),
            tool_turn(("verify", {"expr": "path_contains('out.txt', 'ready')"})),
            tool_turn(end=True),
        ])
        eng = VectorEngine(
            backend=backend, registry=CategorizedToolRegistry(),
            permissions=PermissionContext(),
        )
        eng._world = DevWorld()
        eng.init_vgg(agent=agent, skill_registry=agent._skill_registry, world=DevWorld())
        eng._vgg_agent = agent
        eng._backend = backend

        session = Session(
            session_id="native-devworld", created_at="t", updated_at="t",
            path=Path(work_dir) / "native_devworld.jsonl",
        )
        trace = eng.run_turn_native("create out.txt containing ready", session=session)

        assert len(trace.steps) == 1, f"expected one write->verify step; got {len(trace.steps)}"
        names = verify_oracle_names(agent, eng)
        sub, step = trace.goal_tree.sub_goals[0], trace.steps[0]

        # The native loop dispatched the DEV action skill (routing held outside go2).
        assert step.strategy == "write_file", f"strategy={step.strategy!r}"
        assert sub.verify.startswith("path_contains"), f"verify={sub.verify!r}"
        # The action actually ran — the file exists with the content.
        assert Path("out.txt").read_text(encoding="utf-8") == "ready\n", "skill must write the file"
        assert step.verify_result is True, "path_contains must read True after the write"
        # A dev predicate is NOT a robot predicate -> NOT_GRADED -> no causation downgrade.
        assert step.actor_caused is ActorCaused.NOT_GRADED, (
            f"a dev predicate must be NOT_GRADED (not a robot predicate); got "
            f"{step.actor_caused.value}"
        )
        assert classify_step_evidence(step, sub, names) == "GROUNDED"

        # SAME verdict gate -> the dev path verifies cleanly through the native producer.
        report = VerdictReport.from_trace(trace, names)
        assert report.verified is True, f"a grounded dev step must verify; {report.evidence}"
        assert report.evidence == "GROUNDED"
        assert report.exit_code() == 0
    finally:
        os.chdir(prev_cwd)
        import shutil

        shutil.rmtree(work_dir, ignore_errors=True)
