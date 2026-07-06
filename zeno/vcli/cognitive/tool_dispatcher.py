# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""ToolDispatcher — execute a kernel tool from a verified sub-goal.

Bridges the VGG ``GoalExecutor``'s ``tool`` strategy to the kernel's real tool
registry, running every dispatch through the *same* ``PermissionContext`` gate
the interactive agent loop uses. A per-world allowlist bounds which tools a
sub-goal may invoke autonomously; anything off the allowlist is denied before
any permission check or execution.

Keystone decision (see docs/agent-kernel-phase-b-plan.md): dev side effects are
*tool-backed*, not a widened code sandbox. This reuses every existing safety
guard — the bash deny-list, the file_write overwrite guard, deny/always-allow
rules — behind one audited surface, instead of injecting filesystem primitives
into ``CodeExecutor`` (which would bypass ``PermissionContext``).
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable

from zeno.vcli.tool_execution import (
    DECISION_ASK_DENY,
    DECISION_CHECK_ERROR,
    DECISION_DENY,
    execute_resolved_tool,
    resolve_permission,
)
from zeno.vcli.tools.base import ToolContext

logger = logging.getLogger(__name__)


class _DispatchSession:
    """Minimal session stub exposing the ``read_files`` set the file tools read.

    The file_write overwrite guard refuses to clobber an existing file that has
    not been read this session. A fresh stub keeps that guard active (the set is
    empty, so existing files are protected) while letting new-file writes through.
    """

    def __init__(self) -> None:
        self.read_files: set[str] = set()


class ToolDispatcher:
    """Dispatch a named kernel tool with full permission checking.

    Args:
        registry: A ToolRegistry / CategorizedToolRegistry — must have ``get(name)``.
        permissions: The PermissionContext shared with the agent loop.
        allowlist: Tool names a sub-goal may invoke. ``None``/empty denies all.
        ask_permission: Resolver for ``ask``-level tools, called with
            ``(tool_name, params) -> "y" | "a" | "n"``. ``None`` auto-denies
            (the safe headless default).
        session: Optional session exposing ``read_files``. Defaults to an
            in-memory stub so the overwrite guard still protects existing files.
        cwd: Working directory for tool execution. Defaults to ``Path.cwd()``.
    """

    def __init__(
        self,
        registry: Any,
        permissions: Any,
        *,
        allowlist: "frozenset[str] | set[str] | None" = None,
        ask_permission: Callable[[str, dict[str, Any]], str] | None = None,
        session: Any = None,
        cwd: Path | None = None,
    ) -> None:
        self._registry = registry
        self._permissions = permissions
        self._allowlist = frozenset(allowlist) if allowlist is not None else frozenset()
        self._ask = ask_permission
        self._session = session if session is not None else _DispatchSession()
        self._cwd = cwd or Path.cwd()

    def _make_context(self) -> ToolContext:
        """Build a fresh per-dispatch ToolContext (own abort event)."""
        return ToolContext(
            agent=None,
            cwd=self._cwd,
            session=self._session,
            permissions=self._permissions,
            abort=threading.Event(),
            app_state=None,
        )

    def dispatch(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Run *tool_name* with *args*; return ``(success, error_message)``.

        Order: allowlist gate -> registry lookup -> ``PermissionContext.check``
        (which runs the tool's own ``check_permissions``: bash deny-list,
        file_write overwrite guard) -> ``ask`` resolution -> ``tool.execute``.

        The allowlist gate and the ``(success, error)`` shape are this path's own;
        the permission gate + execute core is the S5.1 shared seam
        (``vcli.tool_execution``) the ReAct loop also uses. Because a sub-goal runs
        autonomously, the seam is asked to fail closed on a buggy permission object
        or resolver (``swallow_*`` flags) rather than propagate — matching this
        path's pre-seam behaviour.
        """
        if not isinstance(tool_name, str) or not tool_name:
            return False, 'tool branch requires a non-empty params["tool"]'
        if tool_name not in self._allowlist:
            return False, f"tool '{tool_name}' is not in the dev allowlist"
        tool = self._registry.get(tool_name) if self._registry is not None else None
        if tool is None:
            return False, f"unknown tool: {tool_name}"
        if not isinstance(args, dict):
            args = {}

        ctx = self._make_context()
        decision = resolve_permission(
            tool, args, ctx, self._permissions, self._ask,
            swallow_check_errors=True,
            swallow_always_allow_errors=True,
        )

        if decision.kind == DECISION_CHECK_ERROR:
            return False, f"permission check error: {decision.reason}"
        if decision.kind == DECISION_DENY:
            return False, f"permission denied: {decision.reason or tool_name}"
        if decision.kind == DECISION_ASK_DENY:
            return False, f"permission denied for {tool_name} (resolver -> {decision.reason})"

        result = execute_resolved_tool(
            tool, args, ctx,
            error_prefix="tool error",
            on_error=lambda name, exc: logger.warning(
                "ToolDispatcher: %s raised %s", name or tool_name, exc
            ),
        )

        is_error = bool(getattr(result, "is_error", False))
        if is_error:
            # A raised tool already produced the "tool error: ..." content via the
            # seam; surface it. A non-raising tool that returns is_error keeps the
            # pre-seam contract of returning its own content as the error message.
            return False, str(getattr(result, "content", ""))
        return True, ""
