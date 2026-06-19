# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R2a PART B — the VECTOR_FAKE_LLM backend-injection seam (deterministic test LLM).

The seam at the SINGLE create_backend site
(``cli.create_backend_with_fake_seam``) is gated ONLY on the env var
``VECTOR_FAKE_LLM=<json-path>``. These tests pin:

(1) ABSENT env -> the real ``create_backend`` is called unchanged (production path
    byte-identical; the seam adds nothing when the var is unset).
(2) PRESENT env -> a ``FakeBackend`` whose ``.call()`` returns the canned plan JSON.
(3) The FakeBackend satisfies the ``LLMBackend`` Protocol (structural .call()).
(4) RED — a canned plan whose ``verify`` is the sentinel ``"True"`` STILL classifies
    RAN through the REAL decomposer + evidence gate (verdict NOT verified): the
    seam injects only the LLM, never a verdict.

No network, no MuJoCo — pure seam + gate logic.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from vector_os_nano.vcli.backends import LLMBackend


@pytest.mark.cli_main
def test_absent_env_uses_real_create_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VECTOR_FAKE_LLM", raising=False)
    from vector_os_nano.vcli import cli

    sentinel = object()
    with patch.object(cli, "create_backend", return_value=sentinel) as real:
        out = cli.create_backend_with_fake_seam(
            provider="anthropic", api_key="k", model="m", base_url=None
        )
    real.assert_called_once_with(provider="anthropic", api_key="k", model="m", base_url=None)
    assert out is sentinel


@pytest.mark.cli_main
def test_present_env_uses_fake_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = {
        "goal": "g",
        "sub_goals": [
            {"name": "s1", "description": "d", "verify": "True", "strategy": "tool_call"},
        ],
    }
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setenv("VECTOR_FAKE_LLM", str(plan_file))
    from vector_os_nano.vcli import cli

    # create_backend must NOT be called when the fake seam is active.
    with patch.object(cli, "create_backend") as real:
        backend = cli.create_backend_with_fake_seam(
            provider="anthropic", api_key="k", model="m", base_url=None
        )
    real.assert_not_called()
    from tests.harness.fake_backend import FakeBackend

    assert isinstance(backend, FakeBackend)


@pytest.mark.cli_main
def test_fake_backend_satisfies_protocol_and_returns_canned_plan(tmp_path: Path) -> None:
    plan = {"goal": "build", "sub_goals": [{"name": "s1", "description": "d", "verify": "True"}]}
    plan_file = tmp_path / "p.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    from tests.harness.fake_backend import FakeBackend

    backend = FakeBackend.from_json_file(plan_file)
    assert isinstance(backend, LLMBackend)  # structural Protocol check
    resp = backend.call(messages=[], tools=[], system=[], max_tokens=100)
    parsed = json.loads(resp.text)
    assert parsed == plan


@pytest.mark.cli_main
def test_canned_plan_with_true_verify_classifies_ran_not_grounded(tmp_path: Path) -> None:
    # RED — the moat holds through the REAL decomposer: a canned plan that the LLM
    # "approves" with verify='True' still carries NO grounded evidence. The
    # decomposer parses + validates it, then the evidence gate classifies the step
    # RAN, so a VerdictReport over it is NOT verified. The fake LLM injects only the
    # plan; it cannot launder a verdict.
    from vector_os_nano.vcli.cognitive.goal_decomposer import GoalDecomposer
    from vector_os_nano.vcli.cognitive.trace_store import classify_step_evidence
    from vector_os_nano.vcli.cognitive.types import ExecutionTrace, StepRecord
    from vector_os_nano.vcli.verdict import VerdictReport
    from tests.harness.fake_backend import FakeBackend

    plan = {
        "goal": "do the thing",
        "sub_goals": [
            {
                "name": "act",
                "description": "act on the project",
                "verify": "True",  # sentinel — no real oracle
                "strategy": "tool_call",
                "strategy_params": {"tool": "file_write", "args": {"file_path": "x.txt", "content": "y"}},
            }
        ],
    }
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")

    # The REAL decomposer parses the canned plan (FakeBackend supplies the text).
    backend = FakeBackend.from_json_file(plan_file)
    decomposer = GoalDecomposer(backend=backend)
    tree = decomposer.decompose("do the thing", world_context="")
    assert tree.sub_goals[0].verify == "True"

    # A step that "succeeded" with verify_result True still classifies RAN — even
    # over a real dev oracle set — because verify='True' is a tautology.
    oracle = frozenset({"file_exists", "path_contains", "grep_count"})
    step = StepRecord(
        sub_goal_name=tree.sub_goals[0].name,
        strategy="tool_call",
        success=True,
        verify_result=True,
        duration_sec=0.1,
    )
    assert classify_step_evidence(step, tree.sub_goals[0], oracle) == "RAN"
    trace = ExecutionTrace(goal_tree=tree, steps=(step,), success=True, total_duration_sec=0.1)
    report = VerdictReport.from_trace(trace, oracle)
    assert report.verified is False
    assert report.evidence == "RAN"
