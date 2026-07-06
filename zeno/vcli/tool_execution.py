# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Shared tool-execution seam (Stage 5, S5.1).

ONE place that runs the permission gate for a single resolved tool and then
executes it, returning a neutral ``PermissionDecision`` + a ``ToolResult``. Both
planning paths call this so the permission/ask/execute core can never drift:

- the ReAct tool loop (``VectorEngine._execute_single_tool``), and
- the VGG ``tool`` sub-goal path (``ToolDispatcher.dispatch``).

This is an *additive* extraction (S5.1): both callers keep their own public entry
points and their own caller-specific concerns. Only the duplicated gate+execute
core lives here. The pieces that legitimately differ between the two callers are
passed in as parameters/strategy — they are NOT collapsed into one behaviour:

- **Allowlist + registry lookup** stay in each caller (the VGG side enforces a
  per-world allowlist before lookup; the ReAct side does not). By the time this
  seam runs, the caller has already resolved a concrete ``tool`` object.
- **Hooks + streaming callbacks** (``on_tool_start`` / ``on_tool_end`` / pre/post
  tool hooks) are the ReAct side's concern; the caller wraps this function with
  them. The seam itself stays pure (no hook firing) so the VGG side — which has
  no hooks — is unaffected.
- **Error-string shaping and the return shape** stay in each caller (ReAct returns
  a rich ``ToolCall`` + a tool-result dict; VGG returns ``(success, error)``).
  This seam returns a neutral ``PermissionDecision`` whose ``kind`` each caller
  maps to its own wording and ``permission_action`` label.
- **Robustness of the permission machinery itself** (whether a raised
  ``permissions.check`` or a raised ``add_always_allow`` is swallowed) is a
  strategy flag, because the two callers legitimately differ: the VGG path runs
  autonomously and fails closed on a buggy resolver/permission object, whereas the
  ReAct path lets such a programming error surface.

The permission *decision* itself (the 7-layer ``PermissionContext.check`` plus the
deny-by-default ``ask`` resolution) is identical for both, which is exactly the
duplication this removes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from zeno.vcli.tools.base import PermissionResult, ToolResult

logger = logging.getLogger(__name__)

# Decision-kind labels returned by ``resolve_permission``. These describe WHAT the
# gate decided; each caller maps them to its own user-facing strings and
# ``permission_action`` vocabulary (the two callers word these differently, so the
# wording stays caller-side — only the decision is shared).
DECISION_ALLOW = "allow"            # tool was already allowed (no prompt)
DECISION_ASK_ALLOW = "ask_allow"    # tool was ``ask`` and the user allowed it
DECISION_DENY = "deny"              # hard deny from ``permissions.check``
DECISION_ASK_DENY = "ask_deny"      # tool was ``ask`` and the resolver denied it
DECISION_CHECK_ERROR = "check_error"  # ``permissions.check`` raised (swallowed)


@dataclass(frozen=True)
class PermissionDecision:
    """Outcome of the shared permission gate for one tool.

    ``kind`` is one of the ``DECISION_*`` constants. ``allowed`` is the single
    bool both callers branch on. ``reason`` carries the underlying detail (the
    tool/user deny reason, the resolver response repr, or the check-error text) so
    each caller can format its own message without re-deriving anything.
    """

    kind: str
    allowed: bool
    reason: str = ""


def resolve_permission(
    tool: Any,
    params: dict[str, Any],
    ctx: Any,
    permissions: Any,
    ask_permission: Callable[[str, dict[str, Any]], str] | None,
    *,
    swallow_check_errors: bool = False,
    swallow_always_allow_errors: bool = False,
) -> PermissionDecision:
    """Run the 7-layer gate + deny-by-default ``ask`` resolution for one tool.

    Returns a ``PermissionDecision`` describing the gate outcome. The ``ask``
    resolution is deny-by-default: only an explicit ``"y"``/``"a"`` allows; ``"a"``
    also records an always-allow. Any other resolver output (``None``, ``""``,
    unexpected) fails closed — the gate must never allow on an undecided/buggy
    resolver. This logic is byte-identical to the inline copies it replaces; only
    the failure-isolation flags differ per caller.

    Args:
        swallow_check_errors: When True, a raised ``permissions.check`` is caught
            and turned into a ``DECISION_CHECK_ERROR`` deny (the autonomous VGG
            path fails closed). When False, the exception propagates (the ReAct
            path surfaces a real bug — its pre-seam behaviour).
        swallow_always_allow_errors: When True, a raised ``add_always_allow`` is
            swallowed (VGG); when False it propagates (ReAct).
    """
    tool_name: str = getattr(tool, "name", "") or getattr(tool, "__tool_name__", "")

    try:
        perm: PermissionResult = permissions.check(tool, params, ctx)
    except Exception as exc:  # noqa: BLE001
        if not swallow_check_errors:
            raise
        return PermissionDecision(
            kind=DECISION_CHECK_ERROR, allowed=False, reason=str(exc)
        )

    if perm.behavior == "deny":
        return PermissionDecision(kind=DECISION_DENY, allowed=False, reason=perm.reason)

    if perm.behavior == "ask":
        response = ask_permission(tool_name, params) if ask_permission else "n"
        if response == "a":
            try:
                permissions.add_always_allow(tool_name)
            except Exception:  # noqa: BLE001
                if not swallow_always_allow_errors:
                    raise
        elif response != "y":
            return PermissionDecision(
                kind=DECISION_ASK_DENY, allowed=False, reason=repr(response)
            )
        return PermissionDecision(kind=DECISION_ASK_ALLOW, allowed=True)

    return PermissionDecision(kind=DECISION_ALLOW, allowed=True)


def execute_resolved_tool(
    tool: Any,
    params: dict[str, Any],
    ctx: Any,
    *,
    error_prefix: str = "Tool error",
    on_error: Callable[[str, Exception], None] | None = None,
) -> ToolResult:
    """Invoke ``tool.execute`` once, turning any raised error into an error result.

    The execution try/except is the common tail both callers shared. The two
    callers differ only in cosmetics that must stay byte-identical, so they are
    parameters here, not collapsed:

    - ``error_prefix``: the error-message prefix on a raised tool (``"Tool error"``
      for the ReAct path, ``"tool error"`` for the VGG dispatcher).
    - ``on_error``: optional logging callback ``(tool_name, exc)`` invoked when the
      tool raises, so each caller keeps its own log level / ``exc_info``.

    Always returns a ``ToolResult`` (never raises) — the contract both callers rely
    on as their single ``is_error`` success signal.
    """
    try:
        return tool.execute(params, ctx)
    except Exception as exc:  # noqa: BLE001
        if on_error is not None:
            on_error(getattr(tool, "name", "") or "", exc)
        return ToolResult(content=f"{error_prefix}: {exc}", is_error=True)
