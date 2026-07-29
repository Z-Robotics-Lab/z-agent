# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""E2E: bringup over the SSH transport, cross-machine odometry (READ-ONLY).

Repeatable acceptance for the ssh nav transport (Phase 2). Drives the REAL
product tools — ``Go2WRealBringupTool`` / ``Go2WRealWhereTool`` — through the
real ``nav_transport`` ssh path (4090 -> NUC), and grades readiness on an
INDEPENDENT oracle the actor cannot author: ``ros2 topic hz /state_estimation``
measured on the 4090 over DDS domain 20. No LLM, no bypass of the transport.

SAFETY (enforced by construction): this harness starts/stops the nav STACK only.
It NEVER publishes a motion topic and NEVER calls a posture/estop service — the
only tools it runs are bringup (start/status/stop) and the read-only ``where``.
The driver ``connect()`` wires idle publishers (way_point/goal_point/teleop) but
NOTHING is ever published on them (no navigate/teleop call). The stack is always
torn down in ``finally`` (NEVER-KILL-INFRA: nav.sh stop only).

Flow: assert transport=ssh -> record NUC units (expect down) -> bringup start
map=zeno_office (ssh) -> poll /state_estimation on the 4090 until it flows
(<=READY_TIMEOUT) -> measure Hz over a window -> connect driver + read `where`
-> bringup status (fast path) -> bringup stop (ssh) -> verify NUC units gone.

Env: GO2W_NAV_TRANSPORT=ssh, GO2W_NAV_SSH_HOST, a sourced ROS jazzy + domain 20 +
CycloneDDS workstation profile (the wrapper ``run_e2e_nav_ssh_bringup.sh`` sets
these). Exit 0 = PASS. Usage: python -m tests.e2e.e2e_nav_ssh_bringup
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

READY_TIMEOUT_S = 120.0     # nav.sh pre-built-map start: SLAM ready ~40-70s
HZ_WINDOW_S = 15.0          # /state_estimation measurement window
ODOM_MIN_HZ = 10.0          # honest floor: odometry is genuinely flowing
SSH_HOST = os.environ.get("GO2W_NAV_SSH_HOST", "go2w-nuc").strip() or "go2w-nuc"
MAP = "zeno_office"         # explicit: the NUC has ~/maps/zeno_office (the 4090
#                             does not, so default-map auto-detect would go plain)


def log(msg: str) -> None:
    print(f"[e2e] {msg}", flush=True)


def _parse_hz(text: str) -> float | None:
    rates = re.findall(r"average rate:\s*([0-9.]+)", text)
    return float(rates[-1]) if rates else None


def measure_hz(topic: str, secs: float) -> float | None:
    """``ros2 topic hz`` for *secs* then parse the average (subscribe-only)."""
    try:
        r = subprocess.run(["ros2", "topic", "hz", topic],
                           capture_output=True, text=True, timeout=secs)
        return _parse_hz((r.stdout or "") + (r.stderr or ""))
    except subprocess.TimeoutExpired as e:  # ros2 topic hz never self-exits
        def _s(v: object) -> str:
            if isinstance(v, bytes):
                return v.decode(errors="replace")
            return v or "" if isinstance(v, str) else ""
        return _parse_hz(_s(e.stdout) + _s(e.stderr))
    except Exception as exc:  # noqa: BLE001
        log(f"measure_hz({topic}) error: {exc}")
        return None


def nuc_zdog_units() -> str:
    """The NUC's running zdog/navdog units (empty = stack down). READ-ONLY ssh."""
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST,
             "systemctl --user list-units 'zdog*' 'navdog*' --no-legend "
             "--state=running 2>/dev/null || true"],
            capture_output=True, text=True, timeout=20)
        return (r.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001
        return f"<ssh error: {exc}>"


def _ctx(base: object) -> object:
    from zeno.vcli.tools.base import ToolContext

    return ToolContext(agent=SimpleNamespace(_base=base), cwd=Path("/tmp"),
                       session=None, permissions=None, abort=threading.Event())


def run() -> int:
    from zeno.hardware.ros2.nav_transport import nav_transport
    from zeno.vcli.worlds.go2w_real_tools import (
        Go2WRealBringupTool, Go2WRealWhereTool)

    results: dict[str, object] = {}
    failures: list[str] = []

    # -- 0. transport must resolve to ssh (product config, not a test stub) ----
    t = nav_transport()
    log(f"transport = {t.describe()} (mode={t.mode})")
    if t.mode != "ssh":
        failures.append(f"transport resolved to {t.mode!r}, expected ssh "
                        "(set GO2W_NAV_TRANSPORT=ssh)")
        _summary(results, failures)
        return 1
    log(f"ssh command_argv(status) = {t.command_argv('status')}")

    bringup = Go2WRealBringupTool()
    started = False
    base = None
    try:
        # -- 1. baseline: stack should be down --------------------------------
        pre = nuc_zdog_units()
        log(f"NUC zdog units BEFORE start: {pre or '(none — stack down)'}")
        results["nuc_units_before"] = pre or "(none)"

        # -- 2. bringup START over ssh (explicit pre-built map) ---------------
        log(f"bringup start map={MAP} (ssh -> NUC) ...")
        res = bringup.execute({"action": "start", "map": MAP}, _ctx(None))
        started = True  # a transient unit may be up even if the reply is noisy
        log(f"start reply (is_error={res.is_error}):\n{res.content}")
        results["start_is_error"] = res.is_error
        if res.is_error:
            failures.append(f"bringup start reported error: {res.content[:200]}")

        # -- 3. poll /state_estimation on the 4090 until it flows -------------
        log("polling /state_estimation on the 4090 (cross-machine) ...")
        t0 = time.monotonic()
        ready_at: float | None = None
        while time.monotonic() - t0 < READY_TIMEOUT_S:
            hz = measure_hz("/state_estimation", 5.0)
            elapsed = time.monotonic() - t0
            if hz is not None:
                ready_at = elapsed
                log(f"  /state_estimation flowing at ~{hz:.1f} Hz "
                    f"(after {elapsed:.0f}s)")
                break
            log(f"  no /state_estimation yet ({elapsed:.0f}s) ...")
        results["ready_after_s"] = round(ready_at, 1) if ready_at else None
        if ready_at is None:
            failures.append("/state_estimation never flowed within "
                            f"{READY_TIMEOUT_S:.0f}s (SLAM not ready?)")

        # -- 4. measure the sustained Hz (the headline metric) ---------------
        if ready_at is not None:
            log(f"measuring /state_estimation over {HZ_WINDOW_S:.0f}s ...")
            hz = measure_hz("/state_estimation", HZ_WINDOW_S)
            results["state_estimation_hz"] = round(hz, 1) if hz else None
            log(f"/state_estimation sustained rate = "
                f"{hz:.1f} Hz" if hz else "/state_estimation rate = <none>")
            if hz is None or hz < ODOM_MIN_HZ:
                failures.append(f"/state_estimation Hz {hz} below floor "
                               f"{ODOM_MIN_HZ}")

        # -- 5. read-only `where` through the connected driver ---------------
        if ready_at is not None:
            try:
                from zeno.hardware.ros2.go2w_hw import Go2WHardware

                base = Go2WHardware()
                base.connect()  # idle pubs only; nothing is ever published
                for _ in range(24):
                    age = base.odom_age_s() if base.is_connected else None
                    if age is not None and age < 2.0:
                        break
                    time.sleep(0.5)
                where = Go2WRealWhereTool().execute({}, _ctx(base))
                log(f"where (READ-ONLY) reply (is_error={where.is_error}): "
                    f"{where.content}")
                results["where"] = where.content
                if where.is_error:
                    failures.append(f"where failed: {where.content[:160]}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"where step error: {exc}")

        # -- 6. bringup STATUS through the product (fast path if odom fresh) --
        try:
            st = bringup.execute({"action": "status"}, _ctx(base))
            log(f"bringup status reply (is_error={st.is_error}):\n{st.content}")
            results["status_is_error"] = st.is_error
        except Exception as exc:  # noqa: BLE001
            log(f"status step error: {exc}")

    finally:
        # -- 7. ALWAYS tear the stack down (nav.sh stop only) -----------------
        if base is not None:
            try:
                base.disconnect()
            except Exception:  # noqa: BLE001
                pass
        if started:
            log("bringup stop (ssh -> NUC) ...")
            try:
                stop = bringup.execute({"action": "stop"}, _ctx(None))
                log(f"stop reply (is_error={stop.is_error}):\n{stop.content}")
                results["stop_is_error"] = stop.is_error
                if stop.is_error:
                    failures.append(f"bringup stop reported error: "
                                   f"{stop.content[:160]}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"bringup stop error: {exc}")
            # -- 8. verify the NUC units are gone -----------------------------
            time.sleep(3.0)
            post = nuc_zdog_units()
            log(f"NUC zdog units AFTER stop: {post or '(none — clean)'}")
            results["nuc_units_after"] = post or "(none)"
            if post:
                failures.append(f"NUC still has running zdog units after stop: "
                               f"{post}")

    return _summary(results, failures)


def _summary(results: dict[str, object], failures: list[str]) -> int:
    log("================ E2E SUMMARY ================")
    for k, v in results.items():
        log(f"  {k} = {v}")
    if failures:
        log("RESULT: FAIL")
        for f in failures:
            log(f"  - {f}")
        return 1
    log("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(run())
