# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R2a PART C — acceptance through the REAL cli.main, driven by a stdlib PTY.

These are the project's FIRST honest capability tests: each spawns the actual
``python -m zeno.vcli.cli -p <prompt> --json`` entrypoint under a PTY
(``tests/harness/pty_cli.run_cli_turn``), reads the machine verdict line
(``ZENO_VERDICT`` primary / ``VECTOR_VERDICT`` legacy alias), and asserts the
verdict + exit code. No ``~/sandbox`` bypass, no engine
poking — the product is the system under test.

Cases (RED -> GREEN):
  * NO-OP / staged 'done' (verify='True')  -> verified False / exit 2 (RAN)
  * GROUNDED (a tool_call that actually writes a file a real oracle reads)
                                           -> verified True  / exit 0
  * two different prompts                  -> different VerdictReport.goal
                                              (no stale reuse across runs)
  * empty-oracle / non-oracle verify       -> fail-closed (verified False)

All runs are deterministic via the ``VECTOR_FAKE_LLM`` seam (canned plan, no live
LLM); the dev world is the default (no MuJoCo). Marked ``cli_main`` + ``capability``
so the CI gate counts them.
"""
from __future__ import annotations

import uuid

import pytest

from tests.harness.pty_cli import run_cli_turn


def _unique(name: str) -> str:
    """A per-run unique filename so concurrent/repeat runs never collide."""
    return f"{name}_{uuid.uuid4().hex[:8]}.txt"


# ---------------------------------------------------------------------------
# NO-OP / staged 'done' — verify='True' -> RAN -> verified False / exit 2
# ---------------------------------------------------------------------------


@pytest.mark.cli_main
@pytest.mark.capability
def test_noop_staged_done_is_not_verified(tmp_path) -> None:
    fname = _unique("noop")
    plan = {
        "goal": "stage a 'done' with no real evidence",
        "sub_goals": [
            {
                "name": "stage_done",
                "description": "write a file but claim done with verify='True'",
                "verify": "True",  # sentinel — carries NO grounded evidence
                "strategy": "tool_call",
                "strategy_params": {"tool": "file_write", "args": {"file_path": fname, "content": "x\n"}},
            }
        ],
    }
    result = run_cli_turn(
        "stage a done with no evidence then finish", fake_plan=plan, cwd=tmp_path
    )
    assert result.verified is False
    assert result.exit_code == 2
    assert result.evidence == "RAN"


# ---------------------------------------------------------------------------
# GROUNDED — a tool_call that actually drives the actor; a real oracle reads
#            real post-state -> GROUNDED -> verified True / exit 0
# ---------------------------------------------------------------------------


@pytest.mark.cli_main
@pytest.mark.capability
def test_grounded_turn_is_verified(tmp_path) -> None:
    # The dev-world file oracle (`path_contains`) only reads WITHIN cwd, so run
    # the child IN tmp_path and use a relative filename — the actor writes a real
    # file the real oracle then reads back.
    fname = _unique("marker")
    plan = {
        "goal": "create a marker file containing ready",
        "sub_goals": [
            {
                "name": "write_marker",
                "description": "write the marker file with the content ready",
                # A REAL dev-world oracle reading actual post-state on disk.
                "verify": f"path_contains({fname!r}, 'ready')",
                "strategy": "tool_call",
                "strategy_params": {
                    "tool": "file_write",
                    "args": {"file_path": fname, "content": "ready\n"},
                },
            }
        ],
    }
    result = run_cli_turn(
        "create the marker file then verify it", fake_plan=plan, cwd=tmp_path
    )
    assert result.verified is True
    assert result.exit_code == 0
    assert result.evidence == "GROUNDED"
    assert result.verdict["n_grounded"] == 1
    # The actor really wrote the file (the oracle did not lie).
    assert (tmp_path / fname).exists()


# ---------------------------------------------------------------------------
# Two different prompts -> different goal (no stale verdict reuse)
# ---------------------------------------------------------------------------


@pytest.mark.cli_main
@pytest.mark.capability
def test_two_prompts_yield_distinct_goals(tmp_path) -> None:
    f1 = _unique("alpha")
    f2 = _unique("beta")
    plan_a = {
        "goal": "GOAL_ALPHA write alpha",
        "sub_goals": [{
            "name": "wa", "description": "write alpha",
            "verify": f"path_contains({f1!r}, 'A')", "strategy": "tool_call",
            "strategy_params": {"tool": "file_write", "args": {"file_path": f1, "content": "A\n"}},
        }],
    }
    plan_b = {
        "goal": "GOAL_BETA write beta",
        "sub_goals": [{
            "name": "wb", "description": "write beta",
            "verify": f"path_contains({f2!r}, 'B')", "strategy": "tool_call",
            "strategy_params": {"tool": "file_write", "args": {"file_path": f2, "content": "B\n"}},
        }],
    }
    ra = run_cli_turn("write the alpha file then verify it", fake_plan=plan_a, cwd=tmp_path)
    rb = run_cli_turn("write the beta file then verify it", fake_plan=plan_b, cwd=tmp_path)
    assert ra.goal == "GOAL_ALPHA write alpha"
    assert rb.goal == "GOAL_BETA write beta"
    assert ra.goal != rb.goal  # no stale reuse across separate cli.main runs
    assert ra.verified is True and rb.verified is True


# ---------------------------------------------------------------------------
# Empty / non-oracle verify -> fail-closed (a phantom predicate cannot ground)
# ---------------------------------------------------------------------------


@pytest.mark.cli_main
@pytest.mark.capability
def test_non_oracle_verify_fails_closed(tmp_path) -> None:
    # A verify that calls a function NOT in the dev oracle set classifies RAN —
    # an absent oracle can only make the gate stricter (fail closed). The step
    # "succeeds" and the file is written, but the verdict is NOT verified.
    fname = str(tmp_path / _unique("phantom"))
    plan = {
        "goal": "verify with a non-oracle predicate",
        "sub_goals": [
            {
                "name": "phantom",
                "description": "write a file but verify with a phantom oracle",
                "verify": "totally_made_up_oracle() == 1",
                "strategy": "tool_call",
                "strategy_params": {"tool": "file_write", "args": {"file_path": fname, "content": "z\n"}},
            }
        ],
    }
    result = run_cli_turn(
        "verify with a phantom predicate then finish", fake_plan=plan, cwd=tmp_path
    )
    assert result.verified is False
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Sentinel identity transition (D184) — the harness scanner accepts EITHER
# prefix (ZENO_VERDICT primary / VECTOR_VERDICT legacy alias), and the REAL
# cli child dual-emits both lines with one identical payload.
# ---------------------------------------------------------------------------

from tests.harness.pty_cli import _find_verdict_line  # noqa: E402

_PAYLOAD = '{"verified": true, "evidence": "GROUNDED", "goal": "g"}'


def test_scanner_accepts_legacy_sentinel_only() -> None:
    # Pure function, no PTY: a pre-transition child (legacy line only) parses.
    out = f"noise\r\nVECTOR_VERDICT {_PAYLOAD}\r\n"
    parsed = _find_verdict_line(out)
    assert parsed is not None and parsed["verified"] is True


def test_scanner_accepts_primary_sentinel_only() -> None:
    # A post-drop child (ZENO_VERDICT only) parses — the scanner already spans
    # the future legacy removal.
    out = f"noise\r\nZENO_VERDICT {_PAYLOAD}\r\n"
    parsed = _find_verdict_line(out)
    assert parsed is not None and parsed["verified"] is True


def test_scanner_on_dual_emit_returns_one_payload() -> None:
    out = f"ZENO_VERDICT {_PAYLOAD}\nVECTOR_VERDICT {_PAYLOAD}\n"
    parsed = _find_verdict_line(out)
    assert parsed is not None and parsed["goal"] == "g"
    assert _find_verdict_line("no sentinel here\n") is None


@pytest.mark.cli_main
@pytest.mark.capability
def test_real_child_dual_emits_both_sentinel_lines(tmp_path) -> None:
    # The REAL `-p --json` child prints BOTH sentinel lines; a legacy-only
    # scanner (re-implemented verbatim below) extracts the SAME payload the
    # harness returned. This is the transition's end-to-end proof.
    import json as _json

    fname = _unique("dual")
    plan = {
        "goal": "create a marker file containing ready",
        "sub_goals": [
            {
                "name": "write_marker",
                "description": "write the marker file with the content ready",
                "verify": f"path_contains({fname!r}, 'ready')",
                "strategy": "tool_call",
                "strategy_params": {
                    "tool": "file_write",
                    "args": {"file_path": fname, "content": "ready\n"},
                },
            }
        ],
    }
    result = run_cli_turn(
        "create the marker file then verify it", fake_plan=plan, cwd=tmp_path
    )
    assert "ZENO_VERDICT " in result.raw_output
    assert "VECTOR_VERDICT " in result.raw_output
    # Legacy-only scan (the pre-rename harness behavior, byte-for-byte).
    legacy = None
    for raw in result.raw_output.splitlines():
        line = raw.strip("\r\n").lstrip("\r")
        idx = line.find("VECTOR_VERDICT ")
        if idx == -1:
            continue
        try:
            legacy = _json.loads(line[idx + len("VECTOR_VERDICT ") :].strip())
            break
        except _json.JSONDecodeError:
            continue
    assert legacy is not None, "old VECTOR_VERDICT scanner no longer matches"
    assert legacy == result.verdict
    assert result.verified is True and result.exit_code == 0
