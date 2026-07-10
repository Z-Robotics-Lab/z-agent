# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""TriggerServiceMixin — std_srvs/Trigger stance & safety calls for Go2WHardware.

Split out of ``go2w_hw.py`` (repo rule: files under 400 lines). Provides the
stance/safety helpers that map one-to-one onto the robot's EXISTING
std_srvs/Trigger services (added by the running nav stack; this mixin defines no
new interface). Semantics mirror ``nav.sh`` so the two control faces agree:

    /standup /liedown                 — stance
    /estop        (== latched zero)   — emergency stop
    /estop_release (== resume)        — release estop AND manual latches
    /manual       (guard silent)      — hardware-remote takeover
    /nav_cancel                       — clear the latched /way_point

The host class must supply ``self._node``, ``self._clients`` (service name ->
rclpy client), and a module ``logger``/``time``; ``Go2WHardware`` does. Every
call is fail-honest: unavailable service or a ``success=False`` response returns
False and NEVER raises into the caller.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class TriggerServiceMixin:
    """Trigger-service stance/safety helpers (mixed into Go2WHardware)."""

    # Attributes provided by the host class (declared for readers/type-checkers).
    _node: Any
    _clients: dict[str, Any]

    def standup(self) -> bool:
        """Stand up / BalanceStand (ready to walk). /standup."""
        return self._call_trigger("/standup")

    def liedown(self) -> bool:
        """Lie down (safe from any state). /liedown."""
        return self._call_trigger("/liedown")

    def estop(self) -> bool:
        """Latched emergency stop: zero velocity locked until release. /estop."""
        return self._call_trigger("/estop")

    def estop_release(self) -> bool:
        """Release estop AND manual latches, resume autonomous arbitration."""
        return self._call_trigger("/estop_release")

    # resume is the operator-facing name for the same release (matches nav.sh).
    resume = estop_release

    def manual(self) -> bool:
        """Silence the guard for hardware-remote takeover (teleop owns control)."""
        return self._call_trigger("/manual")

    def nav_cancel(self) -> bool:
        """Clear the latched /way_point so the planner stops pursuing it."""
        return self._call_trigger("/nav_cancel")

    def _call_trigger(self, service: str, timeout: float = 5.0) -> bool:
        """Call a std_srvs/Trigger service; return its ``success`` (False on any
        error / unavailability — fail honest, never raise into the caller)."""
        client = self._clients.get(service)
        if self._node is None or client is None:
            logger.warning("Go2WHardware: %s unavailable (not connected)", service)
            return False
        try:
            if not client.wait_for_service(timeout_sec=timeout):
                logger.warning("Go2WHardware: %s not ready", service)
                return False
            from std_srvs.srv import Trigger

            future = client.call_async(Trigger.Request())
            deadline = time.monotonic() + timeout
            while not future.done() and time.monotonic() < deadline:
                time.sleep(0.02)
            if not future.done():
                logger.warning("Go2WHardware: %s call timed out", service)
                return False
            resp = future.result()
            ok = bool(getattr(resp, "success", False))
            if not ok:
                logger.warning("Go2WHardware: %s -> success=False (%s)",
                               service, getattr(resp, "message", ""))
            return ok
        except Exception as exc:  # noqa: BLE001 — service boundary, fail honest
            logger.warning("Go2WHardware: %s call error: %s", service, exc)
            return False
