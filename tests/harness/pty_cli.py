# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""pty_cli — drive the REAL vector-cli through a stdlib PTY and read its verdict.

R2a PART C: this is the project's #1-failure fix made concrete. Instead of a
``~/sandbox`` script that pokes the engine directly (bypassing the product), this
harness spawns the ACTUAL entrypoint::

    python -m zeno.vcli.cli -p <prompt> --json

under a stdlib ``pty`` (so the child sees a TTY, exactly like real use), waits for
the fixed ``VECTOR_VERDICT {<json>}`` sentinel line on the child's stdout, parses
the JSON into a ``VerdictReport``-shaped dict, captures the child's exit code, and
asserts the machine invariant ``parsed["verified"] == (exit_code == 0)``.

Deterministic, network-free runs use the ``VECTOR_FAKE_LLM`` seam: pass a
``fake_plan`` dict (written to a temp file the child reads) to inject a canned
decompose plan, so the REAL decomposer / validator / GoalVerifier / evidence-gate
all run on a fixed plan with no live LLM.

STDLIB ONLY — uses ``pty`` + ``subprocess`` + ``os``; deliberately NO ``pexpect``
(a new dependency would be a CEO gate this build avoids).
"""
from __future__ import annotations

import json
import os
import pty
import select
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The fixed sentinel the child prints on stdout (see vcli.verdict.VERDICT_SENTINEL).
_SENTINEL = "VECTOR_VERDICT"

# Generous default — a sync dev-world turn (file_write + verify) is sub-second,
# but allow headroom for cold imports.
_DEFAULT_TIMEOUT_SEC = 90.0


@dataclass(frozen=True)
class CliTurnResult:
    """The outcome of one real cli.main turn driven through the PTY."""

    verdict: dict[str, Any]   # parsed VECTOR_VERDICT payload
    exit_code: int
    raw_output: str           # full child output (for debugging)

    @property
    def verified(self) -> bool:
        return bool(self.verdict.get("verified", False))

    @property
    def evidence(self) -> str:
        return str(self.verdict.get("evidence", ""))

    @property
    def goal(self) -> str:
        return str(self.verdict.get("goal", ""))


def _write_fake_plan(fake_plan: dict[str, Any]) -> str:
    """Write a canned decompose plan to a temp file; return its path."""
    fd, path = tempfile.mkstemp(prefix="vector_fake_plan_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(fake_plan, fh, ensure_ascii=False)
    return path


def _write_tool_script(tool_script: dict[str, Any]) -> str:
    """Write a canned NATIVE tool-use script to a temp file; return its path.

    The M1 native-loop seam (VECTOR_FAKE_LLM_TOOLS) — a ``{"turns": [...]}`` JSON
    object the child's ``FakeToolScriptBackend`` replays as ordered native tool_use
    turns. Parallel to ``_write_fake_plan`` but for the strangler-fig native path.
    """
    fd, path = tempfile.mkstemp(prefix="vector_tool_script_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(tool_script, fh, ensure_ascii=False)
    return path


def _drain(master_fd: int, timeout_sec: float) -> str:
    """Read all bytes from the PTY master until EOF or timeout."""
    chunks: list[bytes] = []
    deadline = _now() + timeout_sec
    while True:
        remaining = deadline - _now()
        if remaining <= 0:
            break
        r, _, _ = select.select([master_fd], [], [], min(0.5, remaining))
        if master_fd in r:
            try:
                data = os.read(master_fd, 4096)
            except OSError:
                break  # slave closed
            if not data:
                break  # EOF
            chunks.append(data)
        # loop continues until EOF or deadline
    return b"".join(chunks).decode("utf-8", errors="replace")


def _now() -> float:
    import time

    return time.monotonic()


def _find_verdict_line(output: str) -> dict[str, Any] | None:
    """Scan child output for the fixed VECTOR_VERDICT sentinel line, parse its JSON.

    The sentinel is unique, so even if Rich/banner noise leaks onto the same PTY
    (stdout+stderr share the line discipline) the verdict is unambiguous. Returns
    the parsed payload, or None if no sentinel line is present.
    """
    for raw in output.splitlines():
        line = raw.strip("\r\n").lstrip("\r")
        idx = line.find(_SENTINEL + " ")
        if idx == -1:
            continue
        payload = line[idx + len(_SENTINEL) + 1 :].strip()
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            continue
    return None


def run_cli_turn(
    prompt: str,
    *,
    fake_plan: dict[str, Any] | None = None,
    tool_script: dict[str, Any] | None = None,
    scenario: str | None = None,
    sim: bool = False,
    sim_go2: bool = False,
    live: bool = False,
    extra_env: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    cwd: str | Path | None = None,
) -> CliTurnResult:
    """Run ONE real cli.main turn through a PTY and return its parsed verdict.

    Args:
        prompt:     the user turn text (passed as ``-p <prompt>``).
        fake_plan:  optional canned decompose plan dict; injected via the
                    ``VECTOR_FAKE_LLM`` seam (deterministic, no live LLM).
        scenario:   optional ``--scenario <id>`` (playground world).
        sim/sim_go2: pass ``--sim`` / ``--sim-go2`` (heavy — caller serializes).
        live:       run against the REAL LLM provider (no fake seam). When True the
                    harness does NOT inject the placeholder ``ANTHROPIC_API_KEY`` —
                    the child inherits the real env and ``resolve_credentials``
                    loads the repo-root ``.env`` from ``cwd`` (the live provider key
                    reaches the child). Scripted callers leave this False so a fake
                    key keeps deterministic runs network-free.
        extra_env / extra_args: escape hatches for additional env / CLI flags.
        timeout_sec: max wait for the child to finish.
        cwd:        working dir for the child (defaults to repo root).

    Asserts the machine invariant ``verified == (exit_code == 0)`` before returning.
    Raises AssertionError if no VECTOR_VERDICT line was emitted.
    """
    argv = [
        sys.executable, "-m", "zeno.vcli.cli",
        "-p", prompt, "--json", "--no-permission",
    ]
    if scenario:
        argv += ["--scenario", scenario]
    if sim:
        argv.append("--sim")
    if sim_go2:
        argv.append("--sim-go2")
    if extra_args:
        argv += list(extra_args)

    env = dict(os.environ)
    # Ensure the child can import `tests` (the FakeBackend lives under tests/harness).
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_REPO_ROOT), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    # Test ISOLATION (M1): each PTY child's turn path is decided by ITS OWN args,
    # never by an ambient global env. Strip any inherited VECTOR_NATIVE_LOOP so a
    # legacy `fake_plan` test always runs the legacy path; a native test opts in
    # explicitly via ``tool_script`` (which re-sets it below) or ``--native-loop``
    # in ``extra_args``. Without this strip, running the whole suite with
    # VECTOR_NATIVE_LOOP=1 set would silently route legacy decompose-plan children
    # through the native loop and false-fail them.
    env.pop("VECTOR_NATIVE_LOOP", None)
    # Likewise strip any inherited VECTOR_NATIVE_FIRST (STEP 5 native-first mode) so
    # an ambient global never silently routes a legacy/native-loop child through the
    # native-attempt-then-fallback path. A native-first test opts in explicitly via
    # ``--native-first`` in ``extra_args`` (set below).
    env.pop("VECTOR_NATIVE_FIRST", None)
    _native_first = bool(extra_args) and "--native-first" in extra_args
    if extra_args and "--native-loop" in extra_args:
        env["VECTOR_NATIVE_LOOP"] = "1"
    if _native_first:
        env["VECTOR_NATIVE_FIRST"] = "1"
    # A deterministic API key so create_backend* runs (the fake seam ignores it).
    # In a LIVE run we must NOT inject this placeholder — it would shadow the real
    # provider creds in resolve_credentials' priority order and the child would talk
    # to a dead Anthropic key instead of the repo-root .env provider. So leave the
    # inherited env untouched (the real key reaches the child) and let
    # resolve_credentials load the repo-root .env from cwd (==_REPO_ROOT below).
    if not live:
        env.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
    # Isolate HOME so the dev world's persistent template/experience tier
    # (~/.vector/goal_templates.json) is per-run — a compiled template from a
    # prior turn must NEVER short-circuit a later decompose and reuse a stale
    # goal/plan. Also keeps the harness from polluting the developer's real
    # ~/.vector. Caller can override via extra_env["HOME"].
    home_dir = tempfile.mkdtemp(prefix="vector_pty_home_")
    env["HOME"] = home_dir
    if fake_plan is not None:
        plan_path = _write_fake_plan(fake_plan)
        env["VECTOR_FAKE_LLM"] = plan_path
    else:
        plan_path = None
    # M1 native-loop seam: a native tool-use SCRIPT (parallel to fake_plan). When
    # given, point VECTOR_FAKE_LLM_TOOLS at the written script (overriding any
    # placeholder a caller passed via extra_env).
    if tool_script is not None:
        script_path = _write_tool_script(tool_script)
        env["VECTOR_FAKE_LLM_TOOLS"] = script_path
    else:
        script_path = None
    if extra_env:
        env.update(extra_env)
    if tool_script is not None:
        # A native tool-script IS an opt-in to the native path: ensure the real
        # written path wins over any placeholder in extra_env. Select the always-on
        # native loop UNLESS the caller asked for STEP 5 native-first — in which case
        # native-first (already set above) is the producer-selection seam and we must
        # NOT force VECTOR_NATIVE_LOOP (which would shadow the native-first routing
        # decision with the unconditional native bypass). Scripted callers that don't
        # pass --native-first are byte-identical (they still get VECTOR_NATIVE_LOOP=1).
        env["VECTOR_FAKE_LLM_TOOLS"] = script_path
        if not _native_first:
            env["VECTOR_NATIVE_LOOP"] = "1"

    master_fd, slave_fd = pty.openpty()
    try:
        proc = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(cwd or _REPO_ROOT),
            env=env,
            close_fds=True,
        )
        os.close(slave_fd)  # parent keeps only the master end
        output = _drain(master_fd, timeout_sec)
        try:
            proc.wait(timeout=max(1.0, timeout_sec))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)
        exit_code = proc.returncode if proc.returncode is not None else 1
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
        if plan_path is not None:
            try:
                os.unlink(plan_path)
            except OSError:
                pass
        if script_path is not None:
            try:
                os.unlink(script_path)
            except OSError:
                pass
        import shutil

        shutil.rmtree(home_dir, ignore_errors=True)

    verdict = _find_verdict_line(output)
    assert verdict is not None, (
        "no VECTOR_VERDICT line emitted by cli.main "
        f"(exit={exit_code}). Raw output:\n{output}"
    )
    # The machine invariant the whole instrument rests on.
    assert bool(verdict.get("verified", False)) == (exit_code == 0), (
        f"verified={verdict.get('verified')} but exit_code={exit_code} "
        f"(must agree). verdict={verdict}"
    )
    return CliTurnResult(verdict=verdict, exit_code=exit_code, raw_output=output)


# ---------------------------------------------------------------------------
# REPL session driver — drive the INTERACTIVE REPL (not -p) by NL, capture output.
# ---------------------------------------------------------------------------
#
# The REPL CUTOVER acceptance instrument: the interactive ``vector-cli`` REPL is the
# owner's ONLY test interface (bare ``vector-cli`` + natural language). Unlike the
# ``-p`` path it emits a HUMAN-readable verdict line ("verdict GROUNDED verified=True
# (1/1 grounded)"), not the ``VECTOR_VERDICT`` JSON sentinel — so this driver returns
# the full transcript and the caller asserts on the rendered text. Same STDLIB-only
# pty/subprocess machinery; a background reader thread accumulates output while the
# main thread sends NL lines at paced delays.


@dataclass(frozen=True)
class ReplSessionResult:
    """The transcript + exit code of one interactive REPL session driven by NL."""

    transcript: str
    exit_code: int


def run_repl_session(
    lines: list[tuple[float, str]],
    *,
    sim: bool = False,
    sim_go2: bool = False,
    tool_script: dict[str, Any] | None = None,
    native: bool = True,
    live: bool = False,
    boot_sec: float = 30.0,
    settle_sec: float = 5.0,
    extra_env: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
) -> ReplSessionResult:
    """Drive the REAL interactive ``cli.main`` REPL under a PTY; capture the transcript.

    Args:
        lines:     ordered ``(delay_before_send_sec, text)`` NL turns; the delay is the
                   wait AFTER the previous line (e.g. give a walk turn time to run)
                   BEFORE sending this one.
        sim/sim_go2: pre-boot a sim via the launch flag (heavy — caller serializes).
        tool_script: a canned native tool-use script injected via VECTOR_FAKE_LLM_TOOLS
                   (deterministic, network-free); None = the real LLM drives native.
        native:    REPL native-first default (True = VECTOR_REPL_NATIVE unset/ON;
                   False = VECTOR_REPL_NATIVE=0 forces the legacy REPL).
        live:      real LLM provider (do NOT inject the placeholder key; the child's
                   resolve_credentials loads the repo-root .env).
        boot_sec:  wait after launch before the first line (sim boot headroom).
        settle_sec: wait after the final line before reading EOF / killing.

    Returns the full transcript (for the caller to assert on the rendered verdict) and
    the child exit code. ``--headless`` is added for ``sim``/``sim_go2`` so no GL window
    opens during an automated drive.
    """
    argv = [
        sys.executable, "-m", "zeno.vcli.cli", "--no-permission",
    ]
    if sim:
        argv.append("--sim")
    if sim_go2:
        argv.append("--sim-go2")
    if (sim or sim_go2) and (not extra_args or "--headless" not in extra_args):
        argv.append("--headless")
    if extra_args:
        argv += list(extra_args)

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_REPO_ROOT), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    env.setdefault("TERM", "xterm-256color")
    # The REPL turn path is decided by THIS session's env only — strip the -p seams.
    env.pop("VECTOR_NATIVE_LOOP", None)
    env.pop("VECTOR_NATIVE_FIRST", None)
    if native:
        env.pop("VECTOR_REPL_NATIVE", None)  # default ON
    else:
        env["VECTOR_REPL_NATIVE"] = "0"
    if not live:
        env.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
    home_dir = tempfile.mkdtemp(prefix="vector_pty_repl_home_")
    env["HOME"] = home_dir
    script_path = None
    if tool_script is not None:
        script_path = _write_tool_script(tool_script)
        env["VECTOR_FAKE_LLM_TOOLS"] = script_path
    if extra_env:
        env.update(extra_env)

    import threading

    master_fd, slave_fd = pty.openpty()
    chunks: list[bytes] = []
    stop = threading.Event()

    def _reader() -> None:
        while not stop.is_set():
            try:
                r, _, _ = select.select([master_fd], [], [], 0.3)
            except OSError:
                break
            if master_fd in r:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                chunks.append(data)

    proc = subprocess.Popen(
        argv, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        cwd=str(_REPO_ROOT), env=env, close_fds=True,
    )
    os.close(slave_fd)
    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()

    import time as _time

    try:
        _time.sleep(boot_sec)
        for delay, text in lines:
            if delay:
                _time.sleep(delay)
            os.write(master_fd, (text + "\n").encode("utf-8"))
        _time.sleep(settle_sec)
    finally:
        stop.set()
        try:
            proc.wait(timeout=15.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        if script_path is not None:
            try:
                os.unlink(script_path)
            except OSError:
                pass
        import shutil

        shutil.rmtree(home_dir, ignore_errors=True)

    exit_code = proc.returncode if proc.returncode is not None else 1
    transcript = b"".join(chunks).decode("utf-8", errors="replace")
    return ReplSessionResult(transcript=transcript, exit_code=exit_code)
