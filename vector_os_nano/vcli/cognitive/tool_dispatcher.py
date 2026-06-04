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

from vector_os_nano.vcli.tools.base import ToolContext

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
        try:
            perm = self._permissions.check(tool, args, ctx)
        except Exception as exc:  # noqa: BLE001
            return False, f"permission check error: {exc}"

        if perm.behavior == "deny":
            return False, f"permission denied: {perm.reason or tool_name}"
        if perm.behavior == "ask":
            response = self._ask(tool_name, args) if self._ask else "n"
            if response == "n":
                return False, f"permission denied by resolver for {tool_name}"
            if response == "a":
                try:
                    self._permissions.add_always_allow(tool_name)
                except Exception:  # noqa: BLE001
                    pass

        try:
            result = tool.execute(args, ctx)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ToolDispatcher: %s raised %s", tool_name, exc)
            return False, f"tool error: {exc}"

        is_error = bool(getattr(result, "is_error", False))
        content = getattr(result, "content", "")
        return (not is_error), ("" if not is_error else str(content))
