# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Level 63 — Phase B.1.1: tool-backed + code-as-policy execution branches.

Acceptance criteria (docs/agent-kernel-phase-b-plan.md, B-1):
- A dev sub-goal (tool_call -> file_write) actually mutates a tree *through* the
  permission gate; an off-allowlist tool and a denied permission both block it.
- The reused guards still fire: bash deny-list, file_write overwrite guard.
- A robot `code` sub-goal still runs; a `code` sub-goal calling open()/import is
  rejected (sandbox), yielding success=False.
- StrategySelector resolves strategy="tool_call" -> StrategyResult("tool", ...).
- The robot path is byte-identical when no code/tool dispatcher is wired
  (defaults None -> branches report "none configured", never crash).

Pure kernel logic — no robot, no network, no mujoco fixtures.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zeno.vcli.cognitive.code_executor import CodeExecutor
from zeno.vcli.cognitive.goal_executor import GoalExecutor
from zeno.vcli.cognitive.strategy_selector import StrategyResult, StrategySelector
from zeno.vcli.cognitive.tool_dispatcher import ToolDispatcher
from zeno.vcli.cognitive.types import SubGoal
from zeno.vcli.permissions import PermissionContext
from zeno.vcli.tools.base import CategorizedToolRegistry
from zeno.vcli.tools.bash_tool import BashTool
from zeno.vcli.tools.file_tools import FileWriteTool
from zeno.vcli.worlds.dev import DEV_TOOL_ALLOWLIST, DEV_VOCAB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Result:
    """A StrategyResult-like object (avoids MagicMock's `name` kwarg trap)."""

    def __init__(self, executor_type: str, name: str, params: dict[str, Any]) -> None:
        self.executor_type = executor_type
        self.name = name
        self.params = params


def _registry() -> CategorizedToolRegistry:
    reg = CategorizedToolRegistry()
    reg.register(FileWriteTool(), category="code")
    reg.register(BashTool(), category="code")
    return reg


def _dispatcher(
    *,
    allowlist: frozenset[str] = DEV_TOOL_ALLOWLIST,
    ask: Any = None,
    cwd: Path | None = None,
) -> ToolDispatcher:
    return ToolDispatcher(
        _registry(),
        PermissionContext(),
        allowlist=allowlist,
        ask_permission=ask,
        cwd=cwd,
    )


_ALLOW = lambda _n, _p: "y"  # noqa: E731
_DENY = lambda _n, _p: "n"  # noqa: E731


# ---------------------------------------------------------------------------
# StrategySelector resolves tool_call
# ---------------------------------------------------------------------------


def test_selector_resolves_tool_call() -> None:
    sel = StrategySelector()
    sg = SubGoal(
        name="w",
        description="write a file",
        verify="file_exists('x')",
        strategy="tool_call",
        strategy_params={"tool": "file_write", "args": {"file_path": "x"}},
    )
    result = sel.select(sg)
    assert isinstance(result, StrategyResult)
    assert result.executor_type == "tool"
    assert result.name == "tool_call"
    assert result.params == {"tool": "file_write", "args": {"file_path": "x"}}


def test_dev_vocab_exposes_tool_call_strategy() -> None:
    assert "tool_call" in DEV_VOCAB.strategies
    assert "tool_call" in DEV_VOCAB.strategy_descriptions
    assert "file_write" in DEV_TOOL_ALLOWLIST


def test_decomposer_keeps_tool_call_strategy() -> None:
    """tool_call must survive the decomposer's KNOWN_STRATEGIES gate."""
    from zeno.vcli.cognitive.goal_decomposer import GoalDecomposer

    gd = GoalDecomposer(backend=None, **DEV_VOCAB.as_kwargs())
    assert "tool_call" in gd.KNOWN_STRATEGIES


# ---------------------------------------------------------------------------
# ToolDispatcher — the keystone: real file_write through the permission gate
# ---------------------------------------------------------------------------


def test_tool_dispatch_writes_file_through_permission_gate(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    disp = _dispatcher(ask=_ALLOW, cwd=tmp_path)

    ok, err = disp.dispatch("file_write", {"file_path": str(target), "content": "hi\n"})

    assert ok is True, err
    assert target.read_text() == "hi\n"


def test_tool_dispatch_denied_permission_blocks_write(tmp_path: Path) -> None:
    target = tmp_path / "nope.txt"
    disp = _dispatcher(ask=_DENY, cwd=tmp_path)  # ask -> "n"

    ok, err = disp.dispatch("file_write", {"file_path": str(target), "content": "x"})

    assert ok is False
    assert "denied" in err.lower()
    assert not target.exists()


def test_tool_dispatch_none_resolver_auto_denies(tmp_path: Path) -> None:
    target = tmp_path / "nope.txt"
    disp = _dispatcher(ask=None, cwd=tmp_path)  # headless default

    ok, err = disp.dispatch("file_write", {"file_path": str(target), "content": "x"})

    assert ok is False
    assert not target.exists()


def test_tool_dispatch_off_allowlist_denied(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    disp = _dispatcher(allowlist=frozenset({"file_read"}), ask=_ALLOW, cwd=tmp_path)

    ok, err = disp.dispatch("file_write", {"file_path": str(target), "content": "x"})

    assert ok is False
    assert "allowlist" in err
    assert not target.exists()


def test_tool_dispatch_unknown_tool_denied(tmp_path: Path) -> None:
    disp = ToolDispatcher(
        _registry(), PermissionContext(),
        allowlist=frozenset({"made_up_tool"}), ask_permission=_ALLOW, cwd=tmp_path,
    )
    ok, err = disp.dispatch("made_up_tool", {})
    assert ok is False
    assert "unknown tool" in err


def test_tool_dispatch_bash_deny_list_still_blocks(tmp_path: Path) -> None:
    """The bash deny-list (tool.check_permissions) is reused, not bypassed."""
    disp = _dispatcher(allowlist=frozenset({"bash"}), ask=_ALLOW, cwd=tmp_path)

    ok, err = disp.dispatch("bash", {"command": "rm -rf /"})

    assert ok is False
    assert "denied" in err.lower()


def test_tool_dispatch_overwrite_guard_still_applies(tmp_path: Path) -> None:
    """file_write refuses to clobber an existing, unread file."""
    target = tmp_path / "exists.txt"
    target.write_text("original")
    disp = _dispatcher(ask=_ALLOW, cwd=tmp_path)

    ok, err = disp.dispatch("file_write", {"file_path": str(target), "content": "new"})

    assert ok is False
    assert "overwrite" in err.lower() or "has not" in err.lower()
    assert target.read_text() == "original"  # untouched


# ---------------------------------------------------------------------------
# GoalExecutor dispatch routing (tool + code branches)
# ---------------------------------------------------------------------------


def test_executor_routes_tool_branch(tmp_path: Path) -> None:
    target = tmp_path / "via_executor.txt"
    disp = _dispatcher(ask=_ALLOW, cwd=tmp_path)
    ex = GoalExecutor(strategy_selector=None, verifier=None, tool_dispatcher=disp)

    ok, err, _ = ex._execute_strategy(
        _Result("tool", "tool_call", {"tool": "file_write",
                                      "args": {"file_path": str(target), "content": "ok\n"}})
    )

    assert ok is True, err
    assert target.read_text() == "ok\n"


def test_executor_tool_branch_requires_tool_key() -> None:
    disp = _dispatcher(ask=_ALLOW)
    ex = GoalExecutor(strategy_selector=None, verifier=None, tool_dispatcher=disp)
    ok, err, _ = ex._execute_strategy(_Result("tool", "tool_call", {"args": {}}))
    assert ok is False
    assert 'params["tool"]' in err


def test_executor_code_branch_runs_and_rejects_sandbox_escape() -> None:
    ex = GoalExecutor(strategy_selector=None, verifier=None, code_executor=CodeExecutor({}))

    ok, _, _ = ex._execute_strategy(_Result("code", "code_as_policy", {"code": "x = 21 * 2\nx"}))
    assert ok is True

    ok_imp, err_imp, _ = ex._execute_strategy(
        _Result("code", "code_as_policy", {"code": "import os"})
    )
    assert ok_imp is False
    assert "not allowed" in err_imp

    ok_open, _, _ = ex._execute_strategy(
        _Result("code", "code_as_policy", {"code": "open('/etc/passwd')"})
    )
    assert ok_open is False


# ---------------------------------------------------------------------------
# Robot path is byte-identical when nothing is wired (defaults None)
# ---------------------------------------------------------------------------


def test_unwired_branches_report_none_configured() -> None:
    ex = GoalExecutor(strategy_selector=None, verifier=None)  # no code/tool deps

    ok_t, err_t, _ = ex._execute_strategy(_Result("tool", "tool_call", {"tool": "file_write"}))
    assert ok_t is False
    assert "none configured" in err_t

    ok_c, err_c, _ = ex._execute_strategy(_Result("code", "code_as_policy", {"code": "1"}))
    assert ok_c is False
    assert "none configured" in err_c


def test_unknown_executor_type_reports_no_match() -> None:
    ex = GoalExecutor(strategy_selector=None, verifier=None)
    ok, err, _ = ex._execute_strategy(_Result("bogus", "x", {}))
    assert ok is False
    # Stage 2b improved the opaque fallback to a clear, named error.
    assert "no strategy matched for" in err
    assert "x" in err and "bogus" in err
