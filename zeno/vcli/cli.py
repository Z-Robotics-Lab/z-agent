# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Zeno — interactive REPL entry point.

Ties together VectorEngine, Session, PermissionContext, and all tools
into an interactive agent loop with Zeno's personality.

    python -m zeno.vcli.cli [options]
    # or via console_scripts: zeno [options]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Callable

import re

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle

from zeno.vcli.backends import create_backend
from zeno.vcli.env import read_env
from zeno.vcli import paths
from zeno.vcli.engine import VectorEngine, TurnResult
from zeno.vcli.session import (
    Session,
    create_session,
    get_latest_session,
    list_sessions,
    load_session,
)
from zeno.vcli.permissions import PermissionContext
from zeno.vcli.prompt import build_system_prompt
from zeno.vcli.turn_status import TurnStatus
from zeno.vcli.tools import CategorizedToolRegistry, ToolRegistry, discover_all_tools, discover_categorized_tools

logger = logging.getLogger(__name__)
console = Console()

VERSION = "0.1.0"


def _env(name: str, default: str | None = None) -> str | None:
    """Thin delegate over :func:`zeno.vcli.env.read_env` (ZENO_-first, VECTOR_
    fallback). Kept as a module-local name for the many call sites here; the
    ``default=None`` mirrors the old ``os.environ.get`` misses this file relied on.
    """
    return read_env(name, default)


def _persist_dir() -> Path:
    """Home dir the engine persists learned templates/stats + REPL history under.

    ~/.zeno is the WRITE root. If ~/.zeno does not yet exist but the legacy
    ~/.vector does (upgrade-in-place), return ~/.vector so the pre-rename learned
    templates / REPL history keep loading; the first save then lands in whichever
    dir this returns. Lazy ($HOME read per call) for test/sandbox isolation.
    """
    zeno_dir = paths.zeno_home()
    if not zeno_dir.exists() and paths.legacy_home().exists():
        return paths.legacy_home()
    return zeno_dir


TEAL = "#00b4b4"
DIM_TEAL = "#006666"

EXIT_COMMANDS: frozenset[str] = frozenset({"quit", "exit", "q"})

_LOGO_PATH = Path(__file__).resolve().parent.parent / "cli" / "logo_braille.txt"

# Popular models on OpenRouter for /model completion
KNOWN_MODELS: list[str] = [
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-haiku-4-5",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-4.1",
    "openai/o3-mini",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-pro",
    "deepseek/deepseek-chat-v3-0324",
    "meta-llama/llama-4-maverick",
]

# Slash command definitions: (name, description, has_args)
SLASH_COMMANDS: list[tuple[str, str, bool]] = [
    ("help", "Show all commands and shortcuts", False),
    ("login", "Set up API key (Anthropic or OpenRouter)", True),
    ("model", "Show or switch model  (/model <name>)", True),
    ("config", "Show saved configuration", False),
    ("tools", "List all registered tools", False),
    ("agent", "Show Zeno's identity and capabilities", False),
    ("status", "Show hardware, tools, session info", False),
    ("usage", "Show token usage this session", False),
    ("copy", "Copy last response to clipboard", False),
    ("export", "Export session as markdown", False),
    ("compact", "Compress context window", False),
    ("clear", "Reset conversation", False),
    ("clear_memory", "Clear scene graph (forget all explored rooms/objects)", False),
    ("reset", "Reset robot pose after a tip-over (SIM only; real worlds refuse)", False),
    ("scenario", "Show or enter a playground scenario  (/scenario <id>)", True),
    ("permissions", "Show or switch approval mode  (/permissions auto|manual)", True),
    ("sessions", "List saved sessions", False),
    ("quit", "Exit", False),
]


# ---------------------------------------------------------------------------
# Custom completer — slash commands with descriptions + model picker
# ---------------------------------------------------------------------------


class ZenoCompleter(Completer):
    """Context-aware completer for the zeno REPL.

    - Typing `/` shows all slash commands with descriptions
    - Typing `/model ` shows known model names
    - Typing `!` shows nothing (shell passthrough)
    """

    def get_completions(self, document: Document, complete_event: Any) -> Any:
        text = document.text_before_cursor

        # Only complete slash commands and exit keywords
        if not text.startswith("/") and not text.strip().lower() in ("q", "qu", "qui", "qui", "ex", "exi"):
            return

        word = document.get_word_before_cursor(WORD=True)

        # Slash commands
        if text.startswith("/"):
            parts = text.split(None, 1)
            cmd_part = parts[0]  # e.g. "/mod"

            if len(parts) == 1 and not text.endswith(" "):
                # Still typing the command name — filter slash commands
                prefix = cmd_part[1:]  # strip leading /
                for name, desc, _has_args in SLASH_COMMANDS:
                    if name.startswith(prefix):
                        yield Completion(
                            f"/{name}",
                            start_position=-len(cmd_part),
                            display=f"/{name}",
                            display_meta=desc,
                        )
            elif cmd_part == "/model" and len(parts) >= 1:
                # After "/model " — complete model names
                model_prefix = parts[1] if len(parts) > 1 else ""
                for m in KNOWN_MODELS:
                    if m.startswith(model_prefix):
                        yield Completion(
                            m,
                            start_position=-len(model_prefix),
                            display=m,
                        )

        # Exit commands
        elif word and not text.startswith("!"):
            lower_word = word.lower()
            for ec in EXIT_COMMANDS:
                if ec.startswith(lower_word) and ec != lower_word:
                    yield Completion(ec, start_position=-len(word))


# Compat alias — renamed VectorCompleter -> ZenoCompleter (fork identity).
# No external callers, but kept per the rename-leaves-an-alias convention.
VectorCompleter = ZenoCompleter


# ---------------------------------------------------------------------------
# prompt_toolkit theme — teal completion menu, styled toolbar
# ---------------------------------------------------------------------------

PT_STYLE = PTStyle.from_dict({
    # Completion menu
    "completion-menu": "bg:#0a0a1a",
    "completion-menu.completion": "bg:#0a0a1a #00b4b4",
    "completion-menu.completion.current": "bg:#00b4b4 #000000 bold",
    "completion-menu.meta.completion": "bg:#0a0a1a #555555",
    "completion-menu.meta.completion.current": "bg:#00b4b4 #000000",
    "completion-menu.multi-column-meta": "bg:#0a0a1a #555555",
    # Scrollbar
    "scrollbar.background": "bg:#0a0a1a",
    "scrollbar.button": "bg:#006666",
    # Bottom toolbar
    "bottom-toolbar": "bg:#0a0a1a #00b4b4",
    "bottom-toolbar.text": "bg:#0a0a1a #00b4b4",
    # Prompt
    "prompt": "bold #00b4b4",
})


# Zeno brand label — embedded as the title of every response Panel.
# (Was the braille dot-art "V" glyph before the Zeno rename; the constant name
# V_LABEL is kept so its 4 Panel-title call sites need no churn.)
V_LABEL = f"[bold {TEAL}] Zeno [/]"


# ---------------------------------------------------------------------------
# Response rendering — code block highlighting + path coloring
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_PATH_RE = re.compile(r"(?<!\w)(/[\w./\-_]+\.\w+)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def render_response(text: str, width: int = 80) -> Panel:
    """Render V's response with syntax-highlighted code blocks and paths.

    Fenced blocks are rendered via ``rich.syntax.Syntax`` keyed on the block's
    language tag (```python / ```bash / ...) so the highlighting is REAL and
    language-driven; an unknown/absent tag degrades to plain text rather than
    crashing the REPL. Prose between blocks keeps path/inline-code colouring.
    """
    parts = _CODE_BLOCK_RE.split(text)

    renderables: list = []
    prose = Text()
    i = 0
    while i < len(parts):
        if i + 2 < len(parts) and (i % 3) == 0:
            _append_highlighted_text(prose, parts[i])
            i += 1
            lang = parts[i] or "text"
            code = parts[i + 1]
            i += 2
            renderables.append(prose)
            renderables.append(
                Syntax(
                    code.rstrip("\n"),
                    lang,
                    theme="ansi_dark",
                    background_color="default",
                    word_wrap=True,
                )
            )
            prose = Text()
        else:
            _append_highlighted_text(prose, parts[i])
            i += 1
    renderables.append(prose)

    return Panel(
        Group(*renderables),
        title=V_LABEL,
        title_align="left",
        border_style=TEAL,
        padding=(0, 1),
        width=width,
    )


def _strip_markdown(raw: str) -> str:
    """Strip markdown formatting that should not appear in terminal output."""
    # Bold: **text** or __text__
    raw = re.sub(r"\*\*(.+?)\*\*", r"\1", raw)
    raw = re.sub(r"__(.+?)__", r"\1", raw)
    # Italic: *text* (single)
    raw = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", raw)
    # Headers: # ## ###
    raw = re.sub(r"^#{1,3}\s+", "", raw, flags=re.MULTILINE)
    # Horizontal rules
    raw = re.sub(r"^---+\s*$", "", raw, flags=re.MULTILINE)
    return raw


def _append_highlighted_text(target: Text, raw: str) -> None:
    """Append text with file paths in teal and `inline code` highlighted."""
    raw = _strip_markdown(raw)
    last = 0
    # Merge path and inline code patterns, process in order
    for m in re.finditer(r"(?P<path>(?<!\w)/[\w./\-_]+\.\w+)|(?P<code>`[^`]+`)", raw):
        if m.start() > last:
            target.append(raw[last:m.start()])
        if m.group("path"):
            target.append(m.group("path"), style=f"bold {TEAL}")
        elif m.group("code"):
            # Strip backticks
            code_text = m.group("code")[1:-1]
            target.append(code_text, style="#88c0d0")
        last = m.end()
    if last < len(raw):
        target.append(raw[last:])


# Last response storage for /copy
_last_response: str = ""


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="zeno",
        description="Zeno — Agentic CLI for Zeno",
    )
    parser.add_argument("--sim", action="store_true", help="Start with MuJoCo arm simulation")
    parser.add_argument("--sim-go2", action="store_true", help="Start with Go2 quadruped simulation")
    parser.add_argument(
        "--scenario",
        default=None,
        metavar="ID",
        help=(
            "Start in a named playground scenario (e.g. 'tabletop'). When set it "
            "selects the playground world (and its verify predicates) instead of "
            "the agent-driven default. Unknown ids fail loud with the valid set."
        ),
    )
    parser.add_argument(
        "--world",
        default=_env("WORLD"),
        metavar="ID",
        help=(
            "Select an explicit registered world by id (e.g. 'go2w'). Highest "
            "precedence — beats --scenario and the agent-driven default. Resolves "
            "through the world registry; unknown ids fail loud with the valid set. "
            "Env default: ZENO_WORLD (legacy VECTOR_WORLD still read as a fallback). "
            "Combine with ZENO_WORLD_PLUGINS (legacy VECTOR_WORLD_PLUGINS) to load a "
            "third-party world module before resolution."
        ),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Suppress the MuJoCo viewer window (default: window opens when --sim is active)",
    )
    parser.add_argument("--model", default=None, help="Model to use (overrides config; default reads ~/.zeno/config.yaml)")
    parser.add_argument("--resume", nargs="?", const="latest", default=None, help="Resume session")
    parser.add_argument("--api-key", default=None, help="API key (or set ANTHROPIC_API_KEY / OPENROUTER_API_KEY)")
    parser.add_argument("--base-url", default=None, help="API base URL")
    parser.add_argument("--no-permission", action="store_true", help="Allow all tools without prompts")
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--system-prompt", default=None, help="Path to custom system prompt file")
    parser.add_argument(
        "-p", "--print",
        dest="print_prompt",
        default=None,
        metavar="TEXT",
        help=(
            "Run ONE turn for TEXT non-interactively and exit (no REPL). With "
            "--json, also emit the machine-checkable verdict on stdout "
            "(ZENO_VERDICT primary + VECTOR_VERDICT legacy alias)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Emit the machine verdict on stdout for the -p turn as two sentinel "
            "lines with one identical payload: 'ZENO_VERDICT {<json>}' (primary) "
            "+ 'VECTOR_VERDICT {<json>}' (legacy alias; Rich/banner routed to "
            "stderr). Exit 0=verified / 2=ran-not-verified / 1=error|no-trace."
        ),
    )
    parser.add_argument(
        "--native-loop",
        action="store_true",
        default=None,
        help=(
            "Campaign #13 M1 (default OFF): run the -p turn through the frontier-model "
            "NATIVE TOOL-USE producer (engine.run_turn_native) instead of the legacy "
            "decompose plan. The verdict block is unchanged. Also enableable via "
            "ZENO_NATIVE_LOOP=1 (legacy VECTOR_NATIVE_LOOP=1 still honoured)."
        ),
    )
    parser.add_argument(
        "--native-first",
        action="store_true",
        default=None,
        help=(
            "STEP 5 native-attempt-then-fallback (default OFF): in the -p turn, ATTEMPT "
            "the native tool-use producer first; if it took NO action (could not route "
            "the goal) FALL BACK to the legacy decompose plan. A SEPARATE additive mode "
            "from --native-loop. Also enableable via ZENO_NATIVE_FIRST=1 (legacy "
            "VECTOR_NATIVE_FIRST=1 still honoured)."
        ),
    )
    return parser.parse_args(argv)


def _native_loop_enabled(args: Any) -> bool:
    """True iff the M1 native tool-use path is selected (flag OR env, default OFF).

    Single source for the strangler-fig flag: ``--native-loop`` on the CLI OR
    ``VECTOR_NATIVE_LOOP=1`` in the env. Default OFF — every existing path is
    byte-identical when neither is set.
    """
    if getattr(args, "native_loop", None):
        return True
    return _env("NATIVE_LOOP", "").strip() in ("1", "true", "True")


def _native_first_enabled(args: Any) -> bool:
    """True iff STEP 5 native-attempt-then-fallback is selected (flag OR env, default OFF).

    A SEPARATE, additive mode from ``_native_loop_enabled``: ``--native-first`` on the
    CLI OR ``VECTOR_NATIVE_FIRST=1`` in the env. Default OFF — every existing path is
    byte-identical when neither this nor ``--native-loop`` is set. This reader does NOT
    consult the native-loop flag/env, so the two modes stay independent.
    """
    if getattr(args, "native_first", None):
        return True
    return _env("NATIVE_FIRST", "").strip() in ("1", "true", "True")


def _print_native_enabled() -> bool:
    """PRINT-PATH CUTOVER (S5b): native is the DEFAULT producer on the ``-p`` path.

    Mirrors the owner-approved REPL cutover (``_repl_native_enabled``) on the
    NON-interactive acceptance entrypoint: ``run_one_turn`` ATTEMPTS the native
    tool-use producer first, then FALLS BACK to the legacy decompose+execute when
    native took NO action — so bare ``zeno -p`` + natural language exercises the
    redesign by default (CLAUDE.md North Star "Acceptance interface"), the same way
    the interactive REPL already does. Default ON; ``VECTOR_PRINT_NATIVE`` in
    {0, false, off, no} forces the pure-legacy ``-p`` path (byte-identical to the
    pre-cutover behavior) — a reversible escape hatch. The explicit ``--native-first``
    flag / ``VECTOR_NATIVE_FIRST`` stays an INDEPENDENT force-on reader (default OFF,
    unchanged) so its documented semantics are preserved; this is the additional
    default-ON knob, NOT a change to that flag's default.
    """
    return _env("PRINT_NATIVE", "").strip().lower() not in (
        "0",
        "false",
        "off",
        "no",
    )


def _native_trace_acted(trace: Any) -> bool:
    """True iff the native trace DISPATCHED at least one action skill.

    A native step's ``.strategy`` is the producing skill name and is the EMPTY string
    when no skill was dispatched (a verify-only step, or a dev world whose
    ``_build_motor_tools`` returns ``{}`` so nothing can be called). A trace with zero
    acted steps means the native producer could not route the goal -> the caller falls
    back to the legacy plan. Pure + defensive: a ``None`` trace, a trace with no
    ``steps``, or steps missing ``.strategy`` all yield False (empty-safe).
    """
    steps = getattr(trace, "steps", None) or ()
    return any((getattr(s, "strategy", "") or "").strip() for s in steps)


def _repl_native_enabled() -> bool:
    """REPL CUTOVER (2026-06-19, owner-approved): native is the DEFAULT REPL turn path.

    The interactive ``zeno`` REPL attempts the frontier-model NATIVE TOOL-USE
    producer first (then falls back to the legacy planner) so the owner's ONLY
    acceptance interface — bare ``zeno`` + natural language — exercises the
    redesign (CLAUDE.md North Star -> "Acceptance interface"). Default ON.
    ``VECTOR_REPL_NATIVE`` in {0, false, off, no} forces the pure-legacy REPL
    (byte-identical to the pre-cutover turn path) — a reversible escape hatch.
    """
    return _env("REPL_NATIVE", "").strip().lower() not in (
        "0",
        "false",
        "off",
        "no",
    )


def _intent_actionable(engine: Any, user_input: str) -> bool:
    """OPTIMIZATION HINT (NOT a correctness fork — rule 1; mirrors cli.py routing).

    The native producer costs an LLM round-trip; attempting it on PURE CHAT or
    sim-management turns ("启动 go2 仿真", "switch to arm") would waste one before the
    no-action fallback. ``classify_intent`` is the SAME observable hint the REPL
    already uses to pick the render shape — here it only decides whether to ATTEMPT
    native, never the verdict. An action-shaped turn (``use_vgg``) attempts native;
    everything else goes straight to the unchanged tool_use path (where SimStartTool
    + embodiment-switch live). On any classify error -> attempt native (fail OPEN to
    the redesign, never silently skip it; a no-op then falls back to legacy anyway).
    """
    try:
        return bool(engine.classify_intent(user_input).use_vgg)
    except Exception:  # noqa: BLE001
        return True


def _repl_attempt_native(
    engine: Any,
    user_input: str,
    session: Any,
    app_state: dict[str, Any],
    console: Any,
) -> bool:
    """Attempt the native tool-use producer for ONE REPL turn (the cutover path).

    Returns True iff the native producer DISPATCHED an action skill (it OWNS the
    turn): the honest verdict — single-sourced from the SAME gate the ``-p`` path
    uses (``VerdictReport.from_trace``; the loop NEVER computes ``verified``) — is
    rendered into the REPL conversation and a CLEAN one-line summary is appended to
    the REAL session for follow-up context. Returns False iff native took NO action
    (could not route the goal) -> the caller falls THROUGH to the unchanged legacy
    routing (no half-action, no double side-effect).

    Runs SYNCHRONOUSLY, like the existing tool_use path: the legged/arm sim animates
    in its own window, so a blocking turn reads as "do it, then tell me if it
    worked" and the verdict prints in order before the next prompt. A SCRATCH session
    isolates the native ReAct scaffolding (verify/finish tool calls + tool_results)
    from the persistent REPL session (step-5 finding b: persistent-session
    pollution); the world/embodiment state lives on ``engine._vgg_agent``, not in
    session text, so the scratch session loses no routing context — and an embodiment
    switch done on a prior (legacy) turn is already reflected on the engine.
    """
    from zeno.vcli.backends.openai_compat import ModelUnavailableError
    from zeno.vcli.cognitive.trace_store import (
        verify_oracle_names,
        verify_predicate_names,
    )
    from zeno.vcli.verdict import VerdictReport

    agent = getattr(engine, "_vgg_agent", None)
    scratch = create_session(metadata={"native_scratch": True})

    # TYPED INTERJECT window (field ask 2026-07-11): the background stdin reader
    # is ACTIVE ONLY while this blocking turn executes — opened here, closed in
    # the finally below, so it can never fight the prompt_toolkit prompt. The
    # kernel (native_loop) checks the queue at its safe boundaries via
    # app_state["interject"].
    _ij_reader = (app_state or {}).get("interject")
    if _ij_reader is not None:
        try:
            _ij_reader.start()
        except Exception:  # noqa: BLE001 — a broken reader must never block a turn
            _ij_reader = None

    # Suppress ROS2/subprocess stderr noise during the turn (the REPL does the same
    # around its legacy turn); restore unconditionally.
    _saved_stderr = sys.stderr
    trace: Any = None
    try:
        try:
            sys.stderr = open(os.devnull, "w")
        except OSError:
            pass
        with console.status(f"[{TEAL}]native[/] working…  [dim](Ctrl+C 安全中断)[/dim]", spinner="dots") as _status:
            # Live progress (D9 #2 perceived latency): stream the model's thinking
            # tail + each tool call into the spinner so the multi-second LLM wait
            # shows activity instead of a frozen line. Best-effort, never fatal.
            def _on_progress(msg: str) -> None:
                try:
                    _status.update(f"[{TEAL}]native[/] {msg}")
                except Exception:  # noqa: BLE001
                    pass
            try:
                trace = engine.run_turn_native(
                    user_input, agent=agent, session=scratch, app_state=app_state,
                    on_progress=_on_progress,
                )
            except KeyboardInterrupt:
                _operator_interrupt(app_state)
                return True  # turn handled; REPL stays alive
            except ModelUnavailableError as exc:
                # A BYO model that CANNOT run (out of credit / unknown id) is
                # user-actionable — surface it clearly and OWN the turn instead of
                # silently degrading to legacy, which would re-hit the same failure
                # and (D179) read as "model chose not to act". console.print writes
                # to stdout, unaffected by the stderr redirect; the finally restores.
                console.print(f"  [yellow]model unavailable:[/] {exc}")
                return True  # turn handled (reported) — do NOT fall through to legacy
            except Exception:  # noqa: BLE001 — native errored -> treat as no-action
                trace = None
    finally:
        if _ij_reader is not None:
            _ij_reader.stop()  # window closes BEFORE anything else prints
        if sys.stderr is not _saved_stderr:
            try:
                sys.stderr.close()
            except Exception:  # noqa: BLE001
                pass
        sys.stderr = _saved_stderr

    # TYPED INTERJECT: a queued line means the operator overrode this turn. The
    # kernel already cancelled motion + the remaining tool calls at its safe
    # boundary; report it here and OWN the turn — falling through to legacy would
    # re-run the OVERRIDDEN goal right after the operator cancelled it. The queued
    # line stays pending: the REPL picks it up as the immediate next turn.
    _interjected = False
    if _ij_reader is not None:
        try:
            _interjected = bool(_ij_reader.has_pending())
        except Exception:  # noqa: BLE001
            _interjected = False
    if _interjected:
        console.print("  [yellow]⏸ 插队 — 已取消当前动作,剩余步骤不再执行[/]")

    if trace is None or not _native_trace_acted(trace):
        # native could not route -> legacy fallback, EXCEPT on an interject (the
        # overridden goal must not be re-run by another producer).
        return True if _interjected else False

    sub_goals = list(getattr(trace.goal_tree, "sub_goals", ()) or ())
    steps = list(getattr(trace, "steps", ()) or ())
    console.print()
    for i, s in enumerate(steps):
        verify_expr = sub_goals[i].verify if i < len(sub_goals) else ""
        chain = (getattr(s, "strategy", "") or "").strip() or "(no action)"
        ok = bool(getattr(s, "verify_result", False))
        actor = getattr(getattr(s, "actor_caused", None), "value", "?")
        mark = "[green]✓[/]" if ok else "[yellow]·[/]"
        console.print(
            f"  [{TEAL}]▸[/] {chain} → verify {verify_expr} {mark} [dim](actor={actor})[/]"
        )

    verified = False
    try:
        # Predicate-role map (2026-07-13): both name sets come from the SAME live
        # namespace, so a world-served predicate oracle (stack_ready/at/turned)
        # grounds like a kernel one and an all-green turn reads N/N grounded.
        oracle_names = verify_oracle_names(agent, engine)
        predicate_names = verify_predicate_names(agent, engine)
        report = VerdictReport.from_trace(trace, oracle_names, predicate_names)
        verified = bool(report.verified)
        color = "green" if verified else "yellow"
        console.print(
            f"  [{TEAL}]verdict[/] {report.evidence} "
            f"[{color}]verified={report.verified}[/] "
            f"[dim]({report.n_grounded}/{report.n_steps} grounded)[/]"
        )
    except Exception as exc:  # noqa: BLE001 — fail closed (display only)
        console.print(f"  [yellow]verdict unavailable:[/] {exc}")

    # ADR-002 visual acceptance: the SAME env-gated PNG snapshot the -p path fires (see
    # _emit). Inert by construction — handed ONLY the agent (never the report), never
    # raises, and only fires on a turn carrying a connected sim agent. Wired here so the
    # BARE-REPL acceptance face captures the honest 3rd-person sim frame for the eyes,
    # instead of a desktop-window grab. NEVER reorder before the verdict is computed.
    if agent is not None:
        _safe_verdict_snapshot(agent)

    # Append a CLEAN summary to the REAL session (not the native scaffolding) so a
    # follow-up turn has context, mirroring the legacy VGG path's session record.
    try:
        summary = "\n".join(
            f"  {(sg.verify or '?')}: {'PASS' if st.verify_result else 'FAIL'}"
            for sg, st in zip(sub_goals, steps)
        )
        session.append_user(user_input)
        session.append_assistant(
            f"[native executed]\nGoal: {user_input}\nVerified: {verified}\n{summary}"
        )
    except Exception:  # noqa: BLE001 — session record is best-effort
        pass
    return True


# ---------------------------------------------------------------------------
# Input classification
# ---------------------------------------------------------------------------


def is_slash_command(text: str) -> bool:
    return text.strip().startswith("/")


def is_exit_command(text: str) -> bool:
    return text.strip().lower() in EXIT_COMMANDS


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _load_logo_lines() -> list[str]:
    """Load braille logo lines, or empty list if file missing."""
    try:
        return _LOGO_PATH.read_text(encoding="utf-8").rstrip().splitlines()
    except (FileNotFoundError, OSError):
        return []


def format_banner(model: str, agent: Any = None, scenario: str | None = None) -> str:
    """Return banner info text (testable, no side effects).

    When a playground ``scenario`` is active, its name is surfaced on its own
    line so a user can see at a glance which preset scene the session is in.
    """
    lines = [
        f"Zeno v{VERSION}",
        f"Model: {model}",
    ]
    if scenario:
        lines.append(f"Scenario: {scenario}")
    if agent is not None:
        arm = getattr(agent, "_arm", None)
        base = getattr(agent, "_base", None)
        if arm is not None:
            lines.append(f"Arm: {getattr(arm, 'name', type(arm).__name__)}")
        if base is not None:
            lines.append(f"Base: {getattr(base, 'name', type(base).__name__)}")
    lines.append("/help for commands, quit to exit")
    return "\n".join(lines)


def print_banner(
    model: str, provider: str, agent: Any = None, scenario: str | None = None
) -> None:
    """Print startup banner with braille logo (auto-scales to terminal width).

    When a playground ``scenario`` is active its name is shown in the info line.
    """
    import shutil
    term_w = shutil.get_terminal_size().columns
    logo_lines = _load_logo_lines()
    max_logo_w = max((len(l) for l in logo_lines), default=0) if logo_lines else 0

    console.print()
    if logo_lines and term_w >= max_logo_w:
        for line in logo_lines:
            console.print(f"[bold {TEAL}]{line}[/]")
            time.sleep(0.08)
    elif logo_lines:
        # Truncate each line to fit terminal
        for line in logo_lines:
            console.print(f"[bold {TEAL}]{line[:term_w - 1]}[/]")
            time.sleep(0.08)
    else:
        console.print(f"[bold {TEAL}]Zeno[/]")

    console.print(f"[dim]{'':>{min(40, term_w - 10)}}v{VERSION}[/]")
    time.sleep(0.15)

    info_parts = [f"Model: {model}", f"Provider: {provider}"]
    if scenario:
        info_parts.append(f"Scenario: {scenario}")
    if agent is not None:
        arm = getattr(agent, "_arm", None)
        base = getattr(agent, "_base", None)
        if arm is not None:
            info_parts.append(f"Arm: {getattr(arm, 'name', type(arm).__name__)}")
        if base is not None:
            info_parts.append(f"Base: {getattr(base, 'name', type(base).__name__)}")
    console.print(f"[dim]  {' | '.join(info_parts)}[/]")
    console.print(f"[dim]  Type / for commands, quit to exit[/]")
    console.print()


def _operator_interrupt(app_state: dict[str, Any] | None) -> None:
    """Ctrl+C during a blocking turn = SAFE interrupt, not a crash.

    Field trace 2026-07-10: during a 5 m walk the operator could not
    interject and Ctrl+C killed the whole CLI mid-navigate. Route the
    interrupt to the world (cancel motion, abort cognitive loops), report,
    and keep the session alive. Never raises.

    The cancel body now lives in ``interject.cancel_current_motion`` so the
    TYPED interject (field ask 2026-07-11) cancels through the SAME world
    ``on_operator_interrupt`` seam — this Ctrl+C handler's behaviour and
    output are byte-identical to before the extraction.
    """
    from zeno.vcli.interject import cancel_current_motion

    msg = cancel_current_motion(app_state)
    console.print(f"\n  [yellow]🛑 {msg}[/yellow]")


def ask_permission(tool_name: str, params: dict[str, Any]) -> str:
    # STDIN COLLISION (typed interject, 2026-07-13): the interject reader must
    # NOT consume the operator's y/n/a answer — suspend it for the whole prompt
    # (prints included, so the prompt is never interleaved with a queued-line
    # echo). No-op when no reader is registered (the -p path, tests).
    from zeno.vcli.interject import reader_suspended

    with reader_suspended():
        console.print(f"\n[yellow bold]Permission required:[/yellow bold]")
        console.print(f"  Tool: [{TEAL}]{tool_name}[/]")
        params_str = json.dumps(params, indent=2, ensure_ascii=False)
        if len(params_str) > 200:
            params_str = params_str[:200] + "..."
        console.print(f"  Params: [dim]{params_str}[/dim]")
        return Prompt.ask("  Allow? [y/n/a=always]", choices=["y", "n", "a"], default="y")


# ---------------------------------------------------------------------------
# /permissions mode persistence (field ask 2026-07-13: the operator re-typed
# /permissions auto every session on the real robot)
# ---------------------------------------------------------------------------

_APPROVAL_MODE_KEY = "approval_mode"  # config.yaml key: "auto" | "manual"

_AUTO_MODE_WARNING = (
    "[yellow]  ⚠ REAL ROBOT: /permissions auto — motion tools execute "
    "immediately; keep the hardware E-stop remote in hand[/yellow]"
)


def _save_approval_mode(auto: bool) -> None:
    """Persist the /permissions mode via the EXISTING zeno config mechanism.

    Written into ~/.zeno/config.yaml alongside the /login keys (same
    load_config/save_config path — no new persistence machinery). Best-effort:
    a config write failure never breaks the running session.
    """
    try:
        from zeno.vcli.config import load_config, save_config

        cfg = load_config()
        cfg[_APPROVAL_MODE_KEY] = "auto" if auto else "manual"
        save_config(cfg)
    except Exception:  # noqa: BLE001 — persistence is best-effort
        pass


def _apply_saved_approval_mode(args: Any, permissions: Any) -> None:
    """Load the persisted /permissions mode at startup (saved 'auto' -> auto).

    Precedence: an explicit ``--no-permission`` CLI flag ALWAYS wins — a saved
    'manual' never downgrades it, and a saved 'auto' only upgrades the default.
    Unknown/absent values are ignored (manual stays the shipped default).
    """
    if getattr(args, "no_permission", False):
        return  # explicit flag wins; never downgraded by a saved mode
    try:
        from zeno.vcli.config import load_config

        mode = str(load_config().get(_APPROVAL_MODE_KEY, "")).strip().lower()
    except Exception:  # noqa: BLE001 — an unreadable config keeps the default
        return
    if mode == "auto":
        permissions.no_permission = True


def _warn_if_auto_mode(permissions: Any) -> None:
    """Print the REAL-ROBOT warning when the session starts in auto mode.

    Persisting auto across sessions must NOT hide the risk — the warning prints
    EVERY session (same text the /permissions command shows on switch).
    """
    if getattr(permissions, "no_permission", False):
        console.print(_AUTO_MODE_WARNING)


# ---------------------------------------------------------------------------
# Hardware init
# ---------------------------------------------------------------------------


def _load_world_plugins() -> None:
    """Import every module named in ``VECTOR_WORLD_PLUGINS`` for its register() side-effect.

    Plug-and-play discovery (Invariant 3): a third-party world lives in its OWN
    module and self-registers into the process-wide world registry on import
    (``register()`` runs at module load). Set ``VECTOR_WORLD_PLUGINS`` to a
    comma-separated list of importable module names; each is imported here so its
    world id becomes resolvable by ``--world``. A module that fails to import (bad
    name, missing dep) is warned about and skipped — one broken plugin never
    crashes the CLI or blocks the others. No-op when the env var is unset/empty.
    """
    spec = _env("WORLD_PLUGINS", "").strip()
    if not spec:
        return
    import importlib

    for name in (m.strip() for m in spec.split(",")):
        if not name:
            continue
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 — one bad plugin must not crash the CLI
            logger.warning(
                "VECTOR_WORLD_PLUGINS: failed to import world plugin %r: %s", name, exc
            )
            console.print(
                f"[yellow]World plugin '{name}' failed to load:[/yellow] {exc}"
            )


def _resolve_active_world(args: argparse.Namespace, agent: Any) -> Any:
    """Select the active world, honouring ``--world`` then ``--scenario``.

    Plugin discovery runs first: ``VECTOR_WORLD_PLUGINS`` modules are imported so
    a BYO world's ``register()`` side-effect lands in the registry before we
    resolve a name.

    Precedence (highest first):
      1. ``--world <id>`` (or env ``VECTOR_WORLD``) -> resolve that registered
         world by id through the process-wide registry. Beats --scenario and the
         agent-driven default — an explicit named world always wins.
      2. ``--scenario <id>`` -> the playground world for that scenario. Loading
         the playground package (an explicit, user-requested track) registers its
         scenarios into the world registry via the lazy hook; we then resolve the
         named world. The kernel still never hard-imports the playground — this
         import only happens because the user asked for it.
      3. Otherwise -> ``resolve_world(agent)`` (exactly today's behaviour:
         a connected agent selects the robot world, else the default dev world).

    Fails loud on an unknown world/scenario id with the valid set — never a silent
    fallback to another world.
    """
    from zeno.vcli.worlds import (
        get_world_registry,
        resolve_world,
        resolve_world_named,
    )

    # Discover BYO world plugins BEFORE resolution, so a --world id contributed by
    # a plugin module's register() is resolvable below.
    _load_world_plugins()

    # 1. Explicit --world wins. Resolve by id straight through the registry.
    world_id = getattr(args, "world", None)
    if world_id:
        try:
            return get_world_registry().resolve(world_id)
        except KeyError as exc:
            console.print(f"[red]Unknown world:[/red] {exc}")
            raise

    scenario = getattr(args, "scenario", None)
    if not scenario:
        return resolve_world(agent)

    # Explicit playground track: importing the package runs register_scenarios(),
    # wiring the scenario factories into the process-wide world registry.
    import zeno.playground  # noqa: F401  (side-effect: register scenarios)

    try:
        return resolve_world_named(scenario)
    except KeyError as exc:
        # Surface the fail-loud message (valid set included) to the user, then
        # re-raise so an unknown scenario id never silently degrades to a default.
        console.print(f"[red]Unknown scenario:[/red] {exc}")
        raise


def _register_world_tools(world: Any, registry: Any, agent: Any) -> None:
    """Invoke the active world's ``register_tools`` hook (Phase-C seam).

    The CLI registers the kernel's general tools (code/general via
    ``discover_categorized_tools``) and the robot skill wrappers (via
    ``wrap_skills``) for every world. A *world* contributes its own domain tools
    here — the same hook the World Protocol declares (worlds/base.py) and the
    engine already honours for ``register_capabilities`` (engine.py init_vgg).

    Zero behaviour change for the two kernel worlds: ``DevWorld.register_tools``
    and ``RobotWorld.register_tools`` are no-ops (they register nothing into the
    passed registry — the CLI already did their tool assembly), so calling this
    for them adds nothing. A BYO world (e.g. go2w) registers its tools straight
    into the CLI's ``CategorizedToolRegistry`` under its own category, which is
    then visible to ``to_anthropic_schemas`` (a fresh category is never in the
    disabled set). Mirrors the ``hasattr`` + best-effort guard the engine uses for
    capabilities: a BYO world's registration failing must warn, never crash the
    CLI.
    """
    hook = getattr(world, "register_tools", None)
    if hook is None:
        return
    try:
        hook(registry, agent)
    except Exception as exc:  # noqa: BLE001 — a BYO world must not crash the CLI
        logger.warning(
            "world %r register_tools failed: %s",
            getattr(world, "name", repr(world)), exc,
        )


def _world_essential_categories(world: Any) -> frozenset[str]:
    """Read the active world's optional ``essential_categories()`` hook.

    A BYO world declares tool categories the intent router must ALWAYS keep in
    scope (its own domain category), so keyword routing — which only knows the
    kernel's categories — can't filter the world's tools out of the schema on the
    routed path (go2w-experience audit finding #1). Duck-typed like the other
    optional hooks: a world without it yields an empty set (byte-identical
    routing for dev/robot and any world that omits it). Best-effort — a broken
    hook must never crash the CLI.
    """
    hook = getattr(world, "essential_categories", None)
    if hook is None:
        return frozenset()
    try:
        return frozenset(hook())
    except Exception as exc:  # noqa: BLE001 — a BYO world must not crash the CLI
        logger.warning(
            "world %r essential_categories failed: %s",
            getattr(world, "name", repr(world)), exc,
        )
        return frozenset()


def _world_setup(world: Any, agent: Any) -> None:
    """Call the active world's optional ``setup(agent)`` lifecycle hook.

    Runs once, right after the world is resolved and its tools registered. A
    world without ``setup`` (dev/robot and every world that omits it) is a no-op,
    so this is byte-identical for existing worlds. A BYO world uses it to warm a
    bridge/cache. Best-effort — a failing setup is warned and swallowed so it
    never blocks the session start.
    """
    hook = getattr(world, "setup", None)
    if hook is None:
        return
    try:
        hook(agent)
    except Exception as exc:  # noqa: BLE001 — setup must not block the REPL
        logger.warning(
            "world %r setup failed: %s", getattr(world, "name", repr(world)), exc
        )


def _world_teardown(world: Any) -> None:
    """Call the active world's optional ``teardown()`` lifecycle hook at exit.

    Mirror of ``_world_setup``: runs once on session shutdown. A world without
    ``teardown`` is a no-op. Best-effort — a failing teardown is warned and
    swallowed so it never masks the real exit path.
    """
    hook = getattr(world, "teardown", None)
    if hook is None:
        return
    try:
        hook()
    except Exception as exc:  # noqa: BLE001 — teardown must not mask exit
        logger.warning(
            "world %r teardown failed: %s", getattr(world, "name", repr(world)), exc
        )


def enter_scenario(scenario_id: str, app_state: dict[str, Any]) -> Any:
    """Switch the LIVE session into the playground ``scenario_id`` (mid-session).

    This is the conversational / ``/scenario`` counterpart to the ``--scenario``
    launch flag: it makes the playground reachable WITHOUT relaunching. Loading
    the playground package (an explicit, user-requested track) registers its
    scenarios into the world registry via the lazy hook; we then resolve the
    named world, swap it into ``app_state`` and re-init the engine's VGG layer so
    the playground verify predicates take effect on the next decompose.

    The kernel still never hard-imports the playground — this import only happens
    because the user asked for it (one-way dependency intact).

    Returns the resolved world. Fails loud (``KeyError`` with the valid set) on an
    unknown scenario id — never a silent fallback to another world.
    """
    from zeno.vcli.worlds import resolve_world_named

    # Explicit playground track: importing the package runs register_scenarios().
    import zeno.playground  # noqa: F401  (side-effect: register scenarios)

    world = resolve_world_named(scenario_id)  # KeyError -> fail loud, caller reports

    app_state["world"] = world
    app_state["scenario"] = getattr(world, "name", scenario_id)

    # Re-init VGG so the verifier namespace picks up the playground predicates.
    # Best-effort: a missing engine (no API key yet) or init failure must not
    # crash the REPL — the world swap still stands for the next engine init.
    engine = app_state.get("engine")
    if engine is not None:
        try:
            engine.init_vgg(
                agent=app_state.get("agent"),
                skill_registry=app_state.get("skill_registry"),
                on_vgg_step=app_state.get("vgg_step_callback"),
                on_vgg_step_view=app_state.get("vgg_step_view_callback"),
                world=world,
                tool_permission_resolver=app_state.get("tool_permission_resolver"),
                # Mirror the launch path: learning tier (persist_dir) is dev-world only.
                persist_dir=_persist_dir() if not world.is_robot() else None,
            )
        except Exception as exc:  # noqa: BLE001 — display path, never crash REPL
            logger.warning("init_vgg after scenario switch failed: %s", exc)
    return world


def _build_world_embodiment(args: argparse.Namespace) -> Any:
    """Build the agent from an explicit ``--world`` embodiment (the BYO front door).

    When ``--world <id>`` selects a world that provides a ``build_embodiment()``
    hook, the object it returns becomes the session's agent — a first-class,
    ``--sim``-free path for a bring-your-own embodiment (e.g. go2w drives its
    Isaac stack over an HTTP bridge, no in-process MuJoCo). Duck-typed and
    optional: a world without the hook (or returning None) leaves the agent None
    (the plain dev/robot session), so this is byte-identical for every existing
    world. Resolution goes through the same registry + plugin discovery the world
    resolver uses, so a plugin-contributed world id is reachable here too.

    Best-effort: a failure resolving/building is warned and degrades to None —
    the session still starts (as a no-agent world), never crashing the CLI.
    """
    world_id = getattr(args, "world", None)
    if not world_id:
        return None
    try:
        from zeno.vcli.worlds import get_world_registry

        _load_world_plugins()  # a plugin may contribute this world id
        world = get_world_registry().resolve(world_id)  # KeyError surfaces in resolver
        builder = getattr(world, "build_embodiment", None)
        if builder is None:
            return None
        embodiment = builder()
        if embodiment is not None:
            logger.info("world %r provided a build_embodiment agent", world_id)
        return embodiment
    except KeyError:
        # An unknown --world id is reported (fail-loud) by _resolve_active_world,
        # which runs right after this; don't double-report here — just no agent.
        return None
    except Exception as exc:  # noqa: BLE001 — a BYO embodiment must not crash the CLI
        logger.warning("world %r build_embodiment failed: %s", world_id, exc)
        return None


def _init_agent(args: argparse.Namespace) -> Any:
    if not (args.sim or args.sim_go2):
        # No in-process simulator: an explicit --world may still supply a
        # first-class embodiment as the agent (the BYO front door). Absent that,
        # the session runs agent-less exactly as before.
        return _build_world_embodiment(args)
    try:
        from zeno.core.agent import Agent  # type: ignore[import]
        if args.sim:
            from zeno.hardware.sim.mujoco_arm import MuJoCoArm  # type: ignore[import]
            from zeno.hardware.sim.mujoco_gripper import MuJoCoGripper  # type: ignore[import]
            from zeno.hardware.sim.mujoco_perception import MuJoCoPerception  # type: ignore[import]
            from zeno.skills.pick import SIM_PICK_CONFIG
            arm = MuJoCoArm(gui=not getattr(args, "headless", False))
            arm.connect()
            gripper = MuJoCoGripper(arm)
            perception = MuJoCoPerception(arm)
            return Agent(
                arm=arm,
                gripper=gripper,
                perception=perception,
                config={"skills": {"pick": dict(SIM_PICK_CONFIG)}},
            )

        # --- Go2 full stack: MuJoCo + ROS2 bridge + nav stack + VLM + Rerun ---
        import os

        # Honor --headless: open the GLFW viewer window only when NOT headless. A
        # headless run (e.g. the R2a PTY acceptance harness, or CI) drives the REAL
        # MuJoCo physics with no on-screen window — the viewer's glXSwapBuffers
        # crashes (GLXBadDrawable) when launched from a PTY-spawned subprocess, and
        # it is never needed for a non-interactive turn. Interactive desktop use
        # (no --headless) is byte-identical: gui=True as before.
        _go2_gui = not getattr(args, "headless", False)

        # Load config for API key
        from zeno.core.config import load_config
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))), "config", "user.yaml")
        cfg = load_config(cfg_path) if os.path.exists(cfg_path) else {}
        api_key = (
            args.api_key
            or cfg.get("llm", {}).get("api_key")
            or os.environ.get("OPENROUTER_API_KEY", "")
        )

        # The in-process Piper arm is attached when the go2_piper attach scene
        # was selected (VECTOR_SIM_WITH_ARM=1) so this lightweight --sim-go2 path
        # is manipulation-capable — same capability the bare-REPL NL path
        # (sim_tool._start_go2 under VECTOR_NO_ROS2=1) provides. Both build the
        # agent through the SAME helper (Rule 3/11) so they can never drift.
        _with_arm = _env("SIM_WITH_ARM", "0") == "1"
        from zeno.hardware.sim.go2_inprocess import (
            build_inprocess_go2_agent,
        )
        agent = build_inprocess_go2_agent(
            gui=_go2_gui, with_arm=_with_arm, api_key=api_key, config=cfg,
            status=lambda m: console.print(f"[dim]  {m}[/dim]"),
        )

        # ROS2 bridge + nav stack (background). OPTIONAL: navigate_to_object plans
        # in-process via MuJoCoGo2.navigate_to (visibility-graph), so the external
        # nav stack is only needed for explore (TARE/FAR), never for the fetch flow.
        # VECTOR_NO_ROS2=1 skips it so the bare `cli --sim-go2` fetch runs fully
        # in-process — the lightweight path autonomous verification needs (the heavy
        # multi-process stack OOM/SIGKILLs an unattended round). Default unchanged.
        if _should_launch_ros2_stack():
            try:
                _launch_ros2_stack(agent._base)
                console.print(f"[dim]  ROS2: bridge + nav stack launched[/dim]")
            except Exception as exc:
                console.print(f"[dim]  ROS2: not available ({exc})[/dim]")
        else:
            console.print(
                f"[dim]  ROS2: skipped (VECTOR_NO_ROS2=1; in-process vgraph nav)[/dim]"
            )

        return agent

    except Exception as exc:
        console.print(f"[yellow]Warning: Could not init simulation: {exc}[/yellow]")
        import traceback
        traceback.print_exc()
        return None


def _should_launch_ros2_stack() -> bool:
    """Whether to launch the external ROS2 nav stack on a ``--sim-go2`` startup.

    The in-process ``MuJoCoGo2.navigate_to`` plans collision-free paths with the
    visibility-graph planner, so the external Vector Nav Stack is only needed for
    explore (TARE/FAR), never for the fetch flow (look -> navigate_to_object ->
    perception_grasp). ``VECTOR_NO_ROS2=1`` skips it, yielding the lightweight
    fully-in-process path autonomous fetch verification uses — the heavy
    multi-process stack OOM/SIGKILLs an unattended ``claude -p`` round. Default
    (unset, or any value other than the exact string "1") launches the stack so
    interactive sessions are byte-unchanged.
    """
    return _env("NO_ROS2", "0") != "1"


def _launch_ros2_stack(go2: Any) -> None:
    """Launch ROS2 bridge + Vector Nav Stack in background.

    Starts the bridge in a daemon thread and the nav stack as a subprocess.
    Non-blocking — returns immediately after launching.
    """
    import subprocess
    import signal
    import atexit
    import os
    import threading

    # 1. Start ROS2 bridge on existing MuJoCoGo2
    try:
        import rclpy
        if not rclpy.ok():
            rclpy.init()

        import importlib.util
        import sys
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        bridge_path = os.path.join(repo, "scripts", "go2_vnav_bridge.py")
        spec = importlib.util.spec_from_file_location("_vnav_bridge", bridge_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_vnav_bridge"] = mod
        spec.loader.exec_module(mod)

        node = mod.Go2VNavBridge(go2)

        def _spin():
            try:
                rclpy.spin(node)
            except Exception:
                pass

        t = threading.Thread(target=_spin, daemon=True)
        t.start()
    except ImportError:
        raise RuntimeError("ROS2 (rclpy) not available")

    # 2. Launch nav stack nodes
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(repo, "scripts", "launch_nav_only.sh")
    if os.path.isfile(script):
        log_path = "/tmp/vector_nav_only.log"
        # Truncate log if it has grown beyond 5 MB to prevent unbounded disk use
        if os.path.exists(log_path) and os.path.getsize(log_path) > 5 * 1024 * 1024:
            with open(log_path, "w") as _f:
                _f.write("")  # truncate
        log_fh = open(log_path, "a")
        proc = subprocess.Popen(
            [script], stdout=log_fh, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )

        # Use a list so the monitor thread can mutate the proc reference.
        proc_ref = [proc]

        def _nav_health_monitor(proc_ref: list, script: str, log_fh: Any, console: Any) -> None:
            """Daemon thread: poll nav stack every 5s, restart if crashed."""
            while True:
                time.sleep(5)
                current = proc_ref[0]
                if current.poll() is not None:
                    exit_code = current.returncode
                    console.print(f"  [red]nav stack crashed (exit {exit_code}), restarting...[/]")
                    try:
                        new_proc = subprocess.Popen(
                            [script], stdout=log_fh, stderr=subprocess.STDOUT,
                            preexec_fn=os.setsid,
                        )
                        proc_ref[0] = new_proc
                        time.sleep(3)  # let it initialize
                        console.print("  [green]nav stack restarted[/]")
                    except Exception as exc:
                        console.print(f"  [red]nav stack restart failed: {exc}[/]")

        monitor = threading.Thread(
            target=_nav_health_monitor,
            args=(proc_ref, script, log_fh, console),
            daemon=True,
        )
        monitor.start()

        def _cleanup():
            current = proc_ref[0]
            try:
                os.killpg(os.getpgid(current.pid), signal.SIGTERM)
                current.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(current.pid), signal.SIGKILL)
                except Exception:
                    pass
            log_fh.close()

        atexit.register(_cleanup)


# ---------------------------------------------------------------------------
# Slash command handler
# ---------------------------------------------------------------------------


def _handle_slash_command(
    cmd: str,
    args_rest: list[str],
    registry: ToolRegistry,
    session: Session | None = None,
    app_state: dict[str, Any] | None = None,
) -> bool:
    """Handle /command. Returns True to continue REPL, False to exit."""

    if cmd == "help":
        console.print()
        tbl = Table(show_header=False, box=None, padding=(0, 2))
        tbl.add_column(style=TEAL, no_wrap=True)
        tbl.add_column(style="dim")
        for name, desc, _has_args in SLASH_COMMANDS:
            tbl.add_row(f"/{name}", desc)
        tbl.add_row("!<cmd>", "Run shell command directly (e.g. !ls -la)")
        tbl.add_row("quit", "Exit (also: exit, q, Ctrl-D)")
        console.print(tbl)
        console.print()
        console.print(f"[bold {TEAL}]Shortcuts:[/]")
        console.print("[dim]  /          show command menu (auto-complete)[/dim]")
        console.print("[dim]  Tab        accept completion[/dim]")
        console.print("[dim]  Ctrl+R     search history[/dim]")
        console.print("[dim]  Ctrl+C     cancel current turn[/dim]")
        console.print("[dim]  <文字>+Enter (任务执行中) 插队: 取消当前动作,你的新指令立即接管[/dim]")
        console.print("[dim]  Ctrl+D     exit[/dim]")
        console.print()

    elif cmd in ("quit", "exit", "q"):
        return False

    elif cmd == "login":
        from zeno.vcli.config import load_config, save_config
        provider_choice = args_rest[0] if args_rest else None
        if provider_choice not in ("claude", "anthropic", "openrouter", None):
            console.print(f"[yellow]  Usage: /login claude | /login anthropic | /login openrouter[/]")
            return True

        if provider_choice is None:
            console.print(f"\n[bold {TEAL}]Authentication:[/]")
            console.print()
            console.print(f"  [{TEAL}]/login claude[/]      Log in with Claude subscription (opens browser)")
            console.print(f"  [{TEAL}]/login anthropic[/]   Enter Anthropic API key manually")
            console.print(f"  [{TEAL}]/login openrouter[/]  Enter OpenRouter key (multi-model)")
            console.print()
            console.print("[dim]  /login claude gives Zeno its own rate limit pool, independent of Claude Code.[/dim]\n")
            return True

        config = load_config()

        if provider_choice == "claude":
            from zeno.vcli.oauth import login_oauth
            console.print(f"\n[bold {TEAL}]Claude subscription login[/]")
            console.print("[dim]  Opening browser for authentication...[/dim]\n")
            creds = login_oauth()
            if creds:
                console.print(f"[green]  Authenticated.[/] Token saved to ~/.zeno/oauth_credentials.json")
                console.print(f"[dim]  Restart zeno to use your subscription.[/dim]\n")
            else:
                console.print("[red]  Authentication failed or timed out.[/]")
                console.print("[dim]  Make sure you have an active Claude subscription.[/dim]\n")

        elif provider_choice == "anthropic":
            console.print(f"\n[bold {TEAL}]Anthropic API key[/]")
            console.print("[dim]  Get your key at: https://console.anthropic.com/settings/keys[/dim]\n")
            key = Prompt.ask("  API key (sk-ant-...)")
            if key.strip():
                config["anthropic_api_key"] = key.strip()
                config["provider"] = "anthropic"
                save_config(config)
                console.print(f"[green]  Saved.[/] Restart zeno to apply.")
            else:
                console.print("[dim]  Cancelled.[/dim]")

        elif provider_choice == "openrouter":
            console.print(f"\n[bold {TEAL}]OpenRouter API key[/]")
            console.print("[dim]  Get your key at: https://openrouter.ai/keys[/dim]\n")
            key = Prompt.ask("  API key (sk-or-...)")
            if key.strip():
                config["openrouter_api_key"] = key.strip()
                config["provider"] = "openrouter"
                config["base_url"] = "https://openrouter.ai/api/v1"
                save_config(config)
                console.print(f"[green]  Saved.[/] Restart zeno to apply.")
            else:
                console.print("[dim]  Cancelled.[/dim]")

    elif cmd == "config":
        from zeno.vcli.config import load_config, load_claude_oauth, _config_read_path
        config = load_config()
        oauth = load_claude_oauth()
        console.print()
        tbl = Table(show_header=False, box=None, padding=(0, 2))
        tbl.add_column(style="dim", no_wrap=True)
        tbl.add_column()
        tbl.add_row("Config", f"[dim]{_config_read_path()}[/dim]")
        # Claude Code OAuth
        if oauth:
            sub = oauth.get("subscriptionType", "?")
            tbl.add_row("Claude auth", f"[green]{sub} (auto-detected from Claude Code)[/]")
        else:
            tbl.add_row("Claude auth", "[dim]not found[/]")
        # API keys
        ak = config.get("anthropic_api_key", "")
        ok = config.get("openrouter_api_key", "")
        tbl.add_row("Anthropic key", f"[green]{ak[:8]}...{ak[-4:]}[/]" if len(ak) > 12 else "[dim]not set[/]")
        tbl.add_row("OpenRouter key", f"[green]{ok[:8]}...{ok[-4:]}[/]" if len(ok) > 12 else "[dim]not set[/]")
        # Active
        active_provider = (app_state or {}).get("provider", config.get("provider", "?"))
        active_model = (app_state or {}).get("model", config.get("model", "?"))
        tbl.add_row("Active", f"[{TEAL}]{active_provider} / {active_model}[/]")
        console.print(tbl)
        console.print()

    elif cmd == "tools":
        tool_names = registry.list_tools()
        if not tool_names:
            console.print("[dim]No tools registered.[/dim]")
        else:
            console.print()
            tbl = Table(show_header=True, header_style=f"bold {TEAL}", box=None, padding=(0, 2))
            tbl.add_column("Tool", no_wrap=True)
            tbl.add_column("Type", no_wrap=True)
            tbl.add_column("Description")
            for name in tool_names:
                t = registry.get(name)
                desc = getattr(t, "description", "") if t else ""
                ro = "read-only" if t and hasattr(t, "is_read_only") and t.is_read_only({}) else "write"
                tbl.add_row(f"[{TEAL}]{name}[/]", f"[dim]{ro}[/]", f"[dim]{desc}[/]")
            console.print(tbl)
            console.print()

    elif cmd == "agent":
        console.print()
        console.print(
            Panel(
                "Zeno -- the AI core of Z-Robotics-Lab's robotics stack.\n"
                "Built by Z-Robotics-Lab. Forked from Vector Robotics (CMU RI).\n\n"
                "Capabilities:\n"
                "  Robot control    start sims, walk, explore, pick, place, navigate\n"
                "  Codebase work    read/write/edit files, run bash, search code\n"
                "  Perception       query world model, check hardware status\n"
                "  Web              fetch URLs for documentation and references\n\n"
                "Zeno owns the hardware. Arms, grippers, quadrupeds, cameras -- Zeno's body.\n"
                "Zeno speaks your language. Safety is non-negotiable.",
                title=V_LABEL,
                title_align="left",
                border_style=TEAL,
                padding=(1, 2),
                width=min(console.width, 76),
            )
        )
        console.print()

    elif cmd == "permissions":
        perms = (app_state or {}).get("permissions")
        if perms is None:
            console.print("[red]permission context unavailable in this mode[/red]")
        else:
            if args_rest and args_rest[0].lower() in ("auto", "manual"):
                perms.no_permission = args_rest[0].lower() == "auto"
                # Persist across sessions (field ask 2026-07-13) via the existing
                # config mechanism; the REAL-ROBOT warning still prints every
                # session that starts in auto (see _warn_if_auto_mode).
                _save_approval_mode(perms.no_permission)
            mode = "auto — tools run WITHOUT asking" if perms.no_permission \
                else "manual — each risky tool asks y/n/a"
            console.print(f"  Approval mode: [bold]{mode}[/bold]")
            console.print("[dim]  switch: /permissions auto | /permissions manual[/dim]")
            if perms.no_permission:
                console.print(
                    "[yellow]  ⚠ REAL ROBOT: motion tools execute immediately — "
                    "keep the hardware E-stop remote in hand[/yellow]")
        return True

    elif cmd == "sessions":
        sessions = list_sessions()
        if not sessions:
            console.print("[dim]No saved sessions.[/dim]")
        else:
            for s in sessions:
                console.print(f"  [{TEAL}]{s.session_id}[/]  {s.created_at}  ({s.message_count} msgs)")

    elif cmd == "usage":
        if session is not None:
            u = session.token_usage
            total = u.input_tokens + u.output_tokens
            console.print(f"  in={u.input_tokens:,}  out={u.output_tokens:,}  total={total:,}")
        else:
            console.print("[dim]No session.[/dim]")

    elif cmd == "compact":
        if session is not None:
            before, after = session.compact(keep_recent=8)
            console.print(f"[dim]  Compacted: {before} -> {after} entries (old context summarized)[/dim]")
        else:
            console.print("[dim]No session.[/dim]")

    elif cmd == "copy":
        if _last_response:
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=_last_response.encode(), check=True,
                )
                console.print(f"[dim]  Copied to clipboard ({len(_last_response)} chars)[/dim]")
            except FileNotFoundError:
                try:
                    subprocess.run(
                        ["xsel", "--clipboard", "--input"],
                        input=_last_response.encode(), check=True,
                    )
                    console.print(f"[dim]  Copied to clipboard ({len(_last_response)} chars)[/dim]")
                except FileNotFoundError:
                    console.print("[dim]  Install xclip or xsel for clipboard support[/dim]")
        else:
            console.print("[dim]  No response to copy.[/dim]")

    elif cmd == "export":
        if session is not None:
            export_dir = _persist_dir() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            export_path = export_dir / f"{session.session_id}.md"
            lines: list[str] = [f"# Zeno Session\n\nSession: {session.session_id}\n"]
            for entry in session._entries:
                etype = entry.get("type")
                if etype == "user":
                    lines.append(f"\n**You:** {entry['content']}\n")
                elif etype == "assistant":
                    lines.append(f"\n**Zeno:** {entry.get('text', '')}\n")
            export_path.write_text("\n".join(lines), encoding="utf-8")
            console.print(f"[dim]  Exported to {export_path}[/dim]")
        else:
            console.print("[dim]No session.[/dim]")

    elif cmd == "clear":
        if session is not None:
            session._entries.clear()
            console.print(f"[dim]  Conversation cleared.[/dim]")
        else:
            console.print("[dim]No session.[/dim]")

    elif cmd == "clear_memory":
        import os as _os
        _sg_path = str(paths.zeno_home() / "scene_graph.yaml")
        cleared = False

        # Clear in-memory scene graph if agent is running
        agent_obj = app_state.get("agent") if app_state else None
        if agent_obj is not None:
            sm = getattr(agent_obj, "_spatial_memory", None)
            if sm is not None:
                persist_path = getattr(sm, "_persist_path", None) or _sg_path
                from zeno.core.scene_graph import SceneGraph
                new_sg = SceneGraph(persist_path=persist_path)
                agent_obj._spatial_memory = new_sg
                base = getattr(agent_obj, "_base", None)
                if base is not None and hasattr(base, "_scene_graph"):
                    base._scene_graph = new_sg
                cleared = True

        # Delete the persisted scene graph + terrain map from BOTH the ~/.zeno write
        # root AND the legacy ~/.vector dir, so clearing memory truly wipes it (a stale
        # legacy copy would otherwise be migrated back in on the next sim start).
        for _base_dir in (paths.zeno_home(), paths.legacy_home()):
            for _fname in ("scene_graph.yaml", "terrain_map.npz"):
                try:
                    _os.remove(str(_base_dir / _fname))
                    cleared = True
                except FileNotFoundError:
                    pass

        if cleared:
            console.print(f"[dim]  Scene graph cleared. All rooms/objects forgotten.[/dim]")
        else:
            console.print(f"[dim]  No scene graph file found.[/dim]")

    elif cmd == "reset":
        import os as _os
        # /reset writes the SIM vnav-bridge flag /tmp/vector_reset_pose (consumed
        # only by scripts/go2_vnav_bridge.py -> MuJoCoGo2.reset_pose). On a world
        # with no such consumer (go2w_real: the driver is ROS2/nav.sh) the write is
        # a dead no-op — printing "Robot will stand up" would be a false-green
        # tip-over recovery (safety-adjacent UX). A world OPTS OUT via the duck-typed
        # supports_pose_reset()->False; absent hook (dev/sim) stays byte-identical.
        _world = (app_state or {}).get("world")
        _supports = getattr(_world, "supports_pose_reset", None)
        _reset_ok = True
        if callable(_supports):
            try:
                _reset_ok = bool(_supports())
            except Exception:  # noqa: BLE001 — a broken hook must not break /reset
                _reset_ok = True
        if not _reset_ok:
            console.print(
                "[yellow]  /reset is a simulator-only pose flag — this world has no "
                "consumer for it, so nothing would happen.[/]")
            console.print(
                "[dim]  On real hardware: say '站起来' / 'stand up' (standup_skill) to "
                "recover posture, then 'resume' (resume_skill) to release the "
                "E-stop/manual latch before moving.[/dim]")
        else:
            # Signal bridge to reset robot pose via file flag
            try:
                with open("/tmp/vector_reset_pose", "w") as _f:
                    _f.write("1")
                console.print(f"[dim]  Reset signal sent. Robot will stand up at current position.[/dim]")
            except OSError as _exc:
                console.print(f"[yellow]  Failed to send reset: {_exc}[/]")

    elif cmd == "model":
        if not args_rest:
            current = app_state.get("model", "unknown") if app_state else "unknown"
            console.print(f"  [{TEAL}]{current}[/]")
            console.print(f"[dim]  /model <name> to switch. Tab for suggestions.[/dim]")
        else:
            new_model = args_rest[0]
            if app_state is None:
                console.print("[yellow]No app state.[/]")
            else:
                prov = app_state["provider"]
                api_key = app_state["api_key"]

                # Auto-detect provider from model name
                # "openai/gpt-4o", "google/gemini-*", "meta-llama/*" → openrouter
                # "claude-*" without prefix → anthropic (if current provider)
                if "/" in new_model and prov == "anthropic":
                    # Model has provider prefix → switch to OpenRouter
                    prov = "openrouter"
                    # Use OpenRouter API key (from config or env)
                    import os
                    or_key = os.environ.get("OPENROUTER_API_KEY", "")
                    if not or_key:
                        try:
                            from zeno.vcli.config import load_config as _lc
                            or_key = _lc().get("openrouter_api_key", "")
                        except Exception:
                            pass
                    if not or_key:
                        # Try user.yaml
                        try:
                            import yaml
                            cfg_path = os.path.join(os.path.dirname(os.path.dirname(
                                os.path.dirname(os.path.abspath(__file__))
                            )), "config", "user.yaml")
                            with open(cfg_path) as f:
                                cfg = yaml.safe_load(f)
                            or_key = cfg.get("llm", {}).get("api_key", "")
                        except Exception:
                            pass
                    if or_key:
                        api_key = or_key
                    else:
                        console.print("[yellow]  No OpenRouter API key found (set OPENROUTER_API_KEY)[/]")
                        return True
                elif prov == "anthropic" and "/" in new_model:
                    new_model = new_model.split("/", 1)[1]
                elif prov == "openrouter" and "/" not in new_model:
                    new_model = f"anthropic/{new_model}"

                new_backend = create_backend(
                    provider=prov,
                    api_key=api_key,
                    model=new_model,
                    base_url=app_state.get("base_url"),
                )
                app_state["engine"]._backend = new_backend
                app_state["model"] = new_model
                app_state["provider"] = prov
                console.print(f"  Switched to [{TEAL}]{new_model}[/] ({prov})")

    elif cmd == "status":
        agent = (app_state or {}).get("agent")
        arm = getattr(agent, "_arm", None) if agent else None
        base = getattr(agent, "_base", None) if agent else None
        perc = getattr(agent, "_perception", None) if agent else None
        current_model = (app_state or {}).get("model", "unknown")
        tool_count = len(registry.list_tools())
        msg_count = len(session._entries) if session else 0

        console.print()
        tbl = Table(show_header=False, box=None, padding=(0, 2))
        tbl.add_column(style="dim", no_wrap=True)
        tbl.add_column()
        tbl.add_row("Model", f"[{TEAL}]{current_model}[/]")
        tbl.add_row("Arm", f"[green]{getattr(arm, 'name', type(arm).__name__)}[/]" if arm else "[dim]none[/]")
        tbl.add_row("Base", f"[green]{getattr(base, 'name', type(base).__name__)}[/]" if base else "[dim]none[/]")
        tbl.add_row("Perception", f"[green]{getattr(perc, 'name', type(perc).__name__)}[/]" if perc else "[dim]none[/]")
        tbl.add_row("Tools", str(tool_count))
        tbl.add_row("Messages", str(msg_count))
        console.print(tbl)
        console.print()

    elif cmd == "scenario":
        app = app_state or {}
        if not args_rest:
            # No id -> show the active scenario (or that none is active).
            active = app.get("scenario")
            if active:
                console.print(f"[{TEAL}]  Active scenario:[/] {active}")
            else:
                console.print("[dim]  No playground scenario active.[/]")
            console.print("[dim]  Switch with: /scenario <id>[/]")
        else:
            scenario_id = args_rest[0]
            try:
                world = enter_scenario(scenario_id, app)
            except KeyError as exc:
                # Fail loud with the valid set — never a silent fallback.
                console.print(f"[red]  Unknown scenario:[/red] {exc}")
            else:
                console.print(
                    f"[green]  Entered scenario:[/] {getattr(world, 'name', scenario_id)}"
                )

    else:
        console.print(f"[yellow]  Unknown: /{cmd}[/]  (type / + Tab)")

    return True


# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------


_ROOM_LABELS: dict[str, str] = {
    "living_room": "Living Room", "dining_room": "Dining Room",
    "kitchen": "Kitchen", "study": "Study",
    "master_bedroom": "Master Bedroom", "guest_bedroom": "Guest Bedroom",
    "bathroom": "Bathroom", "hallway": "Hallway",
}


def _setup_explore_events(console: Any) -> None:
    """Hook exploration background events into console output.

    Uses print() instead of console.print() because explore events fire
    from a background thread — Rich Console is not thread-safe.
    """
    try:
        from zeno.skills.go2.explore import set_event_callback
    except ImportError:
        return

    def _on_explore_event(event_type: str, data: dict) -> None:
        if event_type == "started":
            total = data.get("total_rooms", 8)
            print(f"  >> Exploration started ({total} rooms to discover)")

        elif event_type == "room_entered":
            room = data.get("room", "?")
            visited = data.get("visited", 0)
            total = data.get("total", 8)
            elapsed = data.get("elapsed_sec", 0)
            label = _ROOM_LABELS.get(room, room)
            bar = f"[{'#' * visited}{'.' * (total - visited)}]"
            print(f"  >> {label} {bar} {visited}/{total} ({elapsed}s)")

        elif event_type == "status":
            elapsed = data.get("elapsed_sec", 0)
            rooms = data.get("rooms_found", 0)
            total = data.get("total", 8)
            room = data.get("current_room", "?")
            pos = data.get("position", [0, 0])
            print(f"  .. {elapsed}s | {rooms}/{total} rooms | at {room} ({pos[0]}, {pos[1]})")

        elif event_type in ("completed", "complete"):
            rooms = data.get("rooms", [])
            reason = data.get("reason", "")
            elapsed = data.get("elapsed_sec", 0)
            if reason == "tare_finished":
                print(f"  >> Exploration complete ({elapsed}s, TARE: all frontiers covered). {len(rooms)} rooms.")
            else:
                print(f"  >> Exploration complete ({elapsed}s). {len(rooms)} rooms.")

        elif event_type == "stopped":
            reason = data.get("reason", "unknown")
            rooms = data.get("rooms", [])
            if reason == "cancelled":
                print(f"  >> Exploration stopped. {len(rooms)} rooms so far.")
            elif reason == "robot_fell":
                print("  >> Robot fell! Exploration aborted.")
            else:
                print(f"  >> Exploration {reason} — {len(rooms)} rooms.")

    set_event_callback(_on_explore_event)


def _wants_window(args: argparse.Namespace) -> bool:
    """Return True when the user wants a visible MuJoCo viewer window.

    A window is wanted when --sim or --sim-go2 is active (NL-triggered sims are
    handled separately in sim_tool.py) and --headless is NOT set.
    """
    return (args.sim or args.sim_go2) and not getattr(args, "headless", False)


def _maybe_reexec_under_mjpython(args: argparse.Namespace) -> None:
    """On macOS, re-exec the whole CLI under mjpython if a window is wanted.

    Gates (ALL must be true for re-exec to fire):
    1. sys.platform == 'darwin'                 — macOS only
    2. _wants_window(args)                      — --sim/--sim-go2 without --headless
    3. VECTOR_REEXEC != '1'                     — not already re-exec'd (loop guard)
    4. not running under pytest                 — never re-exec during tests
    5. mujoco.viewer._MJPYTHON is falsy         — not already under mjpython

    Falls back to a one-line warning (headless) when mjpython is missing.
    Does NOT call os.execv when any gate fails — safe for headless / CI / pytest.
    """
    if sys.platform != "darwin":
        return
    if not _wants_window(args):
        return
    if _env("REEXEC") == "1":
        return
    # Never re-exec under pytest (pytest sets this env or injects its own sys.argv)
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    # Check if already under mjpython
    try:
        import mujoco.viewer as _mj_viewer  # type: ignore[import]
        if getattr(_mj_viewer, "_MJPYTHON", None):
            return  # already under mjpython — nothing to do
    except Exception:
        pass  # mujoco not importable yet; proceed to re-exec attempt

    # Locate mjpython next to the running interpreter (the venv's bin/) — robust
    # regardless of where this file sits or how the CLI was launched. The old
    # parents[N]-from-__file__ computation was off by one and resolved to $HOME, so
    # mjpython was never found and the viewer silently fell back to headless.
    from zeno.vcli.tools.sim_tool import locate_mjpython
    mjpython: str | None = locate_mjpython()

    if not mjpython:
        print(
            "Warning: mjpython not found — running headless "
            "(install mujoco into .venv-nano to get a viewer window).",
            file=sys.stderr,
        )
        return

    # Re-exec the entire process under mjpython with the same argv.
    # ZENO_REEXEC=1 (legacy VECTOR_REEXEC mirror) prevents infinite loops.
    new_env = os.environ.copy()
    new_env["ZENO_REEXEC"] = "1"  # ZENO_ primary
    new_env["VECTOR_REEXEC"] = "1"  # legacy mirror (additive; _env/read_env falls back to it)
    os.execve(mjpython, [mjpython, "-m", "zeno.vcli.cli"] + sys.argv[1:], new_env)


# Loggers whose per-step INFO/WARNING lines are pure REPL noise on the non-verbose
# console (the rich step UI already surfaces every failure).  Quieted to ERROR on
# the non-verbose REPL; restored to NOTSET under --verbose.
_QUIET_LOGGERS: tuple[str, ...] = (
    "zeno.vcli.cognitive",   # step-failure WARNINGs duplicated by rich UI
    "zeno.skills",           # [PICK]/[SCAN] INFO lines
    "zeno.perception",       # perception pipeline INFO lines
    "zeno.hardware",         # [SIM DETECT] INFO/WARNING lines
)

# Back-compat alias used by the existing tests.
_COGNITIVE_LOGGER = _QUIET_LOGGERS[0]


def _setup_logging(verbose: bool) -> None:
    """Configure logging for the REPL entry path (CLI only).

    --verbose -> root DEBUG; all noisy sub-package loggers restored to NOTSET so
    they inherit the root level (full logging preserved).

    Non-verbose -> root WARNING; the sub-package loggers in _QUIET_LOGGERS are
    pinned to ERROR so their INFO/WARNING lines don't flood the console.  Every
    step failure is ALREADY surfaced in the rich step UI ("[FAIL] ..."); the
    duplicate log lines are pure noise.  The quieting is scoped to those specific
    package prefixes — NOT the root logger — so real ERRORs still surface and the
    engine/kernel loggers are unaffected.  Library code and the test suite never
    call this function; it is the CLI entry path only.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        # Undo any prior non-verbose quieting so --verbose always restores full logging.
        for name in _QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.NOTSET)
    else:
        logging.basicConfig(level=logging.WARNING)
        for name in _QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.ERROR)


def _ensure_sigint_under_mjpython() -> None:
    """Restore Python's default Ctrl-C handling when running under mjpython.

    mjpython drives a Cocoa main loop on macOS and can leave SIGINT bound to its
    own handler, so a single Ctrl-C is swallowed instead of raising
    KeyboardInterrupt in the REPL (R2-4: the owner had to ^C^C then type quit).
    Re-installing the default int handler makes one Ctrl-C abort the running task
    and return to the prompt. No-op off mjpython; harmless if it cannot be set
    (e.g. not the main thread).
    """
    from zeno.hardware.sim.viewer_mode import running_under_mjpython
    if not running_under_mjpython():
        return
    import signal
    try:
        signal.signal(signal.SIGINT, signal.default_int_handler)
    except (ValueError, OSError):
        pass  # not the main thread / no SIGINT on this platform — leave as-is


def create_backend_with_fake_seam(
    *, provider: str, api_key: str, model: str, base_url: str | None
) -> Any:
    """Create the LLM backend, with a TEST-ONLY deterministic injection seam.

    By default this is byte-identical to ``create_backend`` — the production path
    is unchanged. The ONLY override is gated on the env var
    ``VECTOR_FAKE_LLM=<json-path>``: when set, the network LLM is replaced by a
    ``FakeBackend`` that returns a canned decompose-plan response read from that
    JSON file (see ``tests/harness/fake_backend.py``). This replaces ONLY the
    network call — the REAL decomposer / validator / skill / GoalVerifier /
    evidence-gate / verdict all still run, so a canned plan whose step verifies
    ``"True"`` STILL classifies RAN and the verdict is honest. The seam never
    bypasses any verify / permission layer.

    Absent the env var, ``create_backend`` is called unchanged.
    """
    # M1 native-loop seam: a SCRIPT of native tool_use turns (not a decompose plan).
    # Gated on its own env var so the legacy plan seam stays byte-identical.
    tools_path = _env("FAKE_LLM_TOOLS")
    if tools_path:
        from tests.harness.fake_backend import FakeToolScriptBackend

        return FakeToolScriptBackend.from_json_file(tools_path)
    fake_path = _env("FAKE_LLM")
    if fake_path:
        # TEST-ONLY import (lazy, gated on the env var) — production never reaches
        # this branch, so it never imports the test harness. The repo root is on
        # sys.path when cli is run as a module from the project dir.
        from tests.harness.fake_backend import FakeBackend

        return FakeBackend.from_json_file(fake_path)
    return create_backend(provider=provider, api_key=api_key, model=model, base_url=base_url)


@dataclass
class TurnContext:
    """Everything cli.main's REPL (and a non-interactive turn) needs to run.

    Built ONCE by ``_build_turn_context`` from the shared setup that used to live
    inline in ``main()`` (credentials -> agent -> world -> registry -> session ->
    system prompt -> engine -> init_vgg). The REPL unpacks it into the SAME local
    names it used before (byte-identical loop); ``run_one_turn`` reuses it verbatim.
    """

    args: Any
    api_key: str
    provider: str
    model: str
    base_url: str | None
    agent: Any
    world: Any
    registry: Any
    permissions: Any
    session: Any
    system_prompt: Any
    robot_ctx_provider: Any
    intent_router: Any
    hooks: Any
    engine: "VectorEngine | None"
    app_state: dict[str, Any]


def _build_turn_context(
    args: Any,
    *,
    on_vgg_step: "Callable[[Any], None] | None" = None,
    on_vgg_step_view: "Callable[[dict[str, Any]], None] | None" = None,
    tool_permission_resolver: "Callable[[str, dict[str, Any]], str] | None" = None,
) -> TurnContext:
    """Shared setup for BOTH the REPL and a non-interactive ``-p`` turn.

    Identical to the block that used to live inline in ``main()`` (cli.py setup
    1271-1486). The display callbacks are injected so the REPL can pass its live
    step renderers while a headless turn passes None (no-op). The LLM backend is
    built through ``create_backend_with_fake_seam`` so a ``VECTOR_FAKE_LLM`` test
    run drives the REAL cli.main with a deterministic plan.
    """
    # Resolve API key + provider from CLI flags > env vars > config file
    from zeno.vcli.config import resolve_credentials
    api_key, provider, model, base_url = resolve_credentials(
        cli_api_key=args.api_key,
        cli_base_url=args.base_url,
        cli_model=args.model,
    )

    no_key = not api_key
    if no_key:
        # Each console.print is parsed independently — markup tags must balance
        # within a single call (rich does not span tags across print calls).
        console.print("[yellow]No API key configured.[/]")
        console.print("[dim]  /login claude     auto-detect Claude Code subscription[/dim]")
        console.print("[dim]  /login anthropic  enter Anthropic API key[/dim]")
        console.print("[dim]  /login openrouter enter OpenRouter key[/dim]\n")

    # Agent (optional hardware) + active world. An explicit --scenario selects a
    # playground world (its verify predicates win); otherwise a connected agent
    # selects the robot world, else the default cross-platform "dev" world. The
    # resolved world flows into init_vgg(world=...) below, which sets engine._world
    # BEFORE the verifier namespace is built, so the merge picks up its predicates.
    agent = _init_agent(args)
    world = _resolve_active_world(args, agent)

    # Tools (categorized registry for scalable tool management)
    registry: CategorizedToolRegistry = CategorizedToolRegistry()
    tools_list, cat_map = discover_categorized_tools()
    for t in tools_list:
        cat = "default"
        for c, names in cat_map.items():
            if t.name in names:
                cat = c
                break
        registry.register(t, category=cat)
    if agent is not None:
        from zeno.vcli.tools.skill_wrapper import wrap_skills
        for skill_tool in wrap_skills(agent):
            registry.register(skill_tool, category="robot")
    else:
        # Dev world: hide robot/diag/system tools. The 'sim' category (start/stop
        # _simulation) stays enabled so the user can spin up a sim conversationally
        # ("start the arm sim").
        for _c in ("robot", "diag", "system"):
            registry.disable_category(_c)

    # BYO-world tools (Phase-C hook): after the kernel's general tools + skill
    # wrappers are assembled, let the active world contribute its own domain
    # tools into the SAME registry. No-op for dev/robot (their register_tools is
    # a no-op); a plug-and-play world (go2w) adds its tools under its own
    # category here — no kernel edit. Runs regardless of agent so a robot-flavour
    # BYO world driven WITHOUT --sim still gets its tools.
    _register_world_tools(world, registry, agent)
    # BYO-world one-time activation: setup(agent) runs once the world is fully
    # resolved + its tools registered. No-op for any world that omits the hook.
    _world_setup(world, agent)

    # Permissions — the persisted /permissions mode (auto|manual) loads at
    # startup; the explicit --no-permission flag always wins.
    permissions = PermissionContext(no_permission=args.no_permission)
    _apply_saved_approval_mode(args, permissions)

    # Session
    session: Session
    if args.resume is not None:
        if args.resume == "latest":
            loaded = get_latest_session()
            if loaded is None:
                console.print("[dim]No previous session, starting new.[/dim]")
                session = create_session(metadata={"model": model})
            else:
                session = loaded
                console.print(f"[dim]Resumed: {session.session_id}[/dim]")
        else:
            session = load_session(args.resume)
            console.print(f"[dim]Resumed: {session.session_id}[/dim]")
    else:
        session = create_session(metadata={"model": model})

    # System prompt (with live robot context)
    robot_ctx_provider = None
    try:
        from zeno.vcli.robot_context import RobotContextProvider
        base = getattr(agent, "_base", None) if agent else None
        sg = getattr(agent, "_spatial_memory", None) if agent else None
        arm = getattr(agent, "_arm", None) if agent else None
        robot_ctx_provider = RobotContextProvider(base=base, scene_graph=sg, arm=arm)
    except ImportError:
        pass
    system_prompt = build_system_prompt(
        agent=agent, cwd=Path.cwd(), robot_context=robot_ctx_provider, world=world
    )

    # Wrap in DynamicSystemPrompt so robot state refreshes each turn
    try:
        from zeno.vcli.dynamic_prompt import DynamicSystemPrompt
        system_prompt = DynamicSystemPrompt(system_prompt, robot_ctx_provider)
    except ImportError:
        pass

    # Intent router + hooks
    intent_router = None
    hooks = None
    try:
        from zeno.vcli.intent_router import IntentRouter
        # Seed the router with the active world's essential tool categories so a
        # BYO world's own tools stay in scope on the routed path (finding #1).
        intent_router = IntentRouter(
            essential_categories=_world_essential_categories(world)
        )
    except ImportError:
        pass
    try:
        from zeno.vcli.hooks import ToolHookRegistry
        hooks = ToolHookRegistry()
    except ImportError:
        pass

    # Explore event streaming — wired via _setup_explore_events on first explore
    _setup_explore_events(console)

    # Backend + engine (deferred if no API key — /login can set it up). The
    # backend is built through the fake-LLM seam (production-identical unless
    # VECTOR_FAKE_LLM is set) at the SINGLE create_backend site.
    engine: VectorEngine | None = None
    if api_key:
        backend = create_backend_with_fake_seam(
            provider=provider, api_key=api_key, model=model, base_url=base_url
        )
        engine = VectorEngine(
            backend=backend, registry=registry, system_prompt=system_prompt,
            permissions=permissions, intent_router=intent_router, hooks=hooks,
        )

    # Mutable app state
    _spatial_memory = getattr(agent, "_spatial_memory", None) if agent else None
    _skill_registry = getattr(agent, "_skill_registry", None) if agent else None
    # An explicit --scenario selected a playground world; its name doubles as the
    # active scenario id (banner + mid-session /scenario read/write this).
    _active_scenario = getattr(args, "scenario", None) or None
    app_state: dict[str, Any] = {
        "agent": agent,
        "registry": registry,
        "engine": engine,
        "model": model,
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "scene_graph": _spatial_memory,
        "skill_registry": _skill_registry,
        "robot_ctx_provider": robot_ctx_provider,
        "world": world,
        "scenario": _active_scenario,
        "permissions": permissions,
    }
    def _default_tool_permission(n: str, prm: dict[str, Any]) -> str:
        # Consult the session PermissionContext FIRST — /permissions auto
        # (no_permission) and 'a'=always answers short-circuit the prompt.
        if permissions.no_permission or n in permissions.session_allow:
            return "y"
        ans = ask_permission(n, prm)
        if ans == "a":
            permissions.session_allow.add(n)
        return ans

    app_state["tool_permission_resolver"] = tool_permission_resolver or _default_tool_permission

    # VGG cognitive layer (optional) — init through the SAME path as the REPL so
    # the verifier namespace / oracle set is identical whether interactive or not.
    if engine is not None:
        try:
            engine.init_vgg(
                agent=agent,
                skill_registry=_skill_registry,
                on_vgg_step=on_vgg_step,
                on_vgg_step_view=on_vgg_step_view,
                world=world,
                tool_permission_resolver=app_state["tool_permission_resolver"],
                persist_dir=_persist_dir() if not world.is_robot() else None,
            )
        except Exception:  # noqa: BLE001
            pass

    return TurnContext(
        args=args,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        agent=agent,
        world=world,
        registry=registry,
        permissions=permissions,
        session=session,
        system_prompt=system_prompt,
        robot_ctx_provider=robot_ctx_provider,
        intent_router=intent_router,
        hooks=hooks,
        engine=engine,
        app_state=app_state,
    )


def _safe_verdict_snapshot(agent: Any) -> None:
    """Best-effort same-process visual snapshot at verdict time (ADR-002 visual acceptance).

    PNG-only, env-gated by ``VECTOR_SNAPSHOT_DIR``. It is handed ONLY the agent (never the
    ``VerdictReport``) so it CANNOT change the verdict, and any failure is swallowed here as
    defense-in-depth over ``capture.snapshot_on_verdict`` (which is itself non-raising). The
    capture module is imported lazily so non-sim turns never pay the cost.
    """
    try:
        from zeno.acceptance import capture

        capture.snapshot_on_verdict(agent)
    except Exception:  # noqa: BLE001 — a snapshot must NEVER affect the turn / verdict
        pass


def _sim_lock_enabled(args: Any) -> bool:
    """True when the global ONE-sim lock should wrap this turn — ``VECTOR_SIM_LOCK=1`` AND a sim is
    launched (ADR-002 Stage 0). Default OFF: interactive ``zeno`` and the test suite are
    unaffected; the EvolvingLoop and the acceptance harnesses opt in via the env so EVERY automated
    sim serializes through this one owner (no double-lock: only the sim-running cli process holds it).
    """
    if _env("SIM_LOCK", "0").strip().lower() not in ("1", "true", "on", "yes"):
        return False
    return bool(getattr(args, "sim_go2", False) or getattr(args, "sim", False))


def _hold_sim_lock_until_exit() -> None:
    """Acquire the global one-sim lock for this process's lifetime (released + nuke-after at exit).

    Raises ``sim_lock.SimBusy`` if the host cannot be cleared within ``VECTOR_SIM_LOCK_TIMEOUT`` (the
    caller turns that into a fail-fast 'sim busy' verdict — never a silent 2nd concurrent sim).
    """
    import atexit

    from zeno.acceptance import sim_lock

    timeout = float(_env("SIM_LOCK_TIMEOUT", "600"))
    cm = sim_lock.sim_lock(nuke_after=True, wait_timeout=timeout)
    cm.__enter__()  # acquire flock + clear-host preflight; raises SimBusy on failure
    atexit.register(lambda: _release_sim_lock(cm))


def _release_sim_lock(cm: Any) -> None:
    try:
        cm.__exit__(None, None, None)
    except Exception:  # noqa: BLE001 — release/teardown is best-effort at process exit
        pass


def run_one_turn(args: Any) -> int:
    """Run ONE turn for ``args.print_prompt`` non-interactively and return an exit code.

    This is the machine-checkable acceptance entrypoint (R2a). It reuses the SAME
    shared setup the REPL uses (``_build_turn_context``), runs the turn
    SYNCHRONOUSLY via ``engine.vgg_execute`` (NEVER ``vgg_execute_async`` — an
    in-flight async trace would emit a verdict on incomplete evidence), then builds
    a frozen ``VerdictReport`` from the EXISTING
    ``evidence_passed(trace, verify_oracle_names(agent, engine))`` (never a second
    opinion). Under ``--json`` it emits the verdict on stdout as
    ``ZENO_VERDICT {<json>}`` plus the legacy ``VECTOR_VERDICT {<json>}`` alias
    line (one identical payload — D184 identity transition) with all
    Rich/banner output already routed to stderr by ``main``.

    Exit codes: 0 = verified, 2 = ran (not verified), 1 = error / no trace.
    """
    from zeno.vcli.cognitive.trace_store import (
        verify_oracle_names,
        verify_predicate_names,
    )
    from zeno.vcli.verdict import VerdictReport

    prompt = args.print_prompt
    emit_json = bool(getattr(args, "json", False))

    def _emit(report: "VerdictReport", agent: Any = None) -> int:
        # ADR-002 visual acceptance: a same-process, env-gated PNG snapshot. Inert by
        # construction (it is not given the report, and never raises); only fires on paths
        # that carry a connected sim agent. NEVER reorder before computing the verdict.
        if agent is not None:
            _safe_verdict_snapshot(agent)
        if emit_json:
            # The machine verdict on real stdout (Rich/banner are on stderr):
            # ZENO_VERDICT primary + VECTOR_VERDICT legacy alias, one identical
            # payload (D184 — external scanners grep the legacy string until
            # the gated drop).
            for _line in report.to_sentinel_lines():
                print(_line, flush=True)
        else:
            console.print(
                f"[{TEAL}]verdict[/] {report.evidence} "
                f"verified={report.verified} ({report.n_grounded}/{report.n_steps} grounded)"
            )
        return report.exit_code()

    # ADR-002 Stage 0: serialize the global one-sim-at-a-time discipline when enabled (the loop /
    # harnesses set VECTOR_SIM_LOCK=1). Acquire BEFORE building the sim; hold for the process; release
    # + teardown at exit. Fail-fast (never run a 2nd concurrent sim) if the host can't be cleared.
    if _sim_lock_enabled(args):
        from zeno.acceptance.sim_lock import SimBusy

        try:
            _hold_sim_lock_until_exit()
        except SimBusy as exc:
            return _emit(VerdictReport.no_trace(goal=prompt or "", error=f"sim busy: {exc}"))

    try:
        ctx = _build_turn_context(args)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Setup error:[/] {exc}")
        return _emit(VerdictReport.no_trace(goal=prompt or "", error=str(exc)))

    engine = ctx.engine
    if engine is None:
        console.print("[yellow]No API key. Use /login to authenticate first.[/]")
        return _emit(VerdictReport.no_trace(goal=prompt or "", error="no engine (no API key)"))

    # S5b PRINT-PATH CUTOVER native-attempt-then-fallback (DEFAULT ON via
    # _print_native_enabled; also forced by --native-first / VECTOR_NATIVE_FIRST):
    # ATTEMPT the native producer first; if it DISPATCHED an action skill (routed the
    # goal) emit its verdict — otherwise it took NO action (zero skills dispatched ->
    # no half-action side-effects) and we FALL THROUGH to the EXISTING legacy
    # decompose+execute+verdict block below. Strictly ADDITIVE: a goal native cannot
    # route (e.g. the VECTOR_FAKE_LLM decompose-plan seam yields no tool_calls) falls
    # through to the byte-identical legacy verdict, so only goals native CAN route
    # change producer. VECTOR_PRINT_NATIVE in {0,false,off,no} forces the pure-legacy
    # -p path (reversible escape hatch). The fallback's vgg_decompose(prompt) uses the
    # RAW prompt, independent of any session text the native attempt may have appended.
    # The DEFAULT-ON print cutover must NOT pre-empt an EXPLICIT --native-loop (pure
    # native, no fallback) — defer to block 2 in that case; an explicit --native-first
    # still wins (preserving every prior flag behavior). So block 1 fires on: explicit
    # --native-first, OR the default cutover when --native-loop is NOT explicitly set.
    if _native_first_enabled(args) or (
        _print_native_enabled() and not _native_loop_enabled(args)
    ):
        try:
            trace = engine.run_turn_native(
                prompt, agent=getattr(engine, "_vgg_agent", None), session=ctx.session
            )
        except Exception:  # noqa: BLE001
            trace = None
        if trace is not None and _native_trace_acted(trace):
            try:
                oracle_names = verify_oracle_names(getattr(engine, "_vgg_agent", None), engine)
                predicate_names = verify_predicate_names(getattr(engine, "_vgg_agent", None), engine)
                report = VerdictReport.from_trace(trace, oracle_names, predicate_names)
            except Exception as exc:  # noqa: BLE001
                report = VerdictReport.no_trace(goal=prompt or "", error=f"verdict failed: {exc}")
            return _emit(report, agent=getattr(engine, "_vgg_agent", None))
        # Native took NO action -> fall through to the legacy block (no return here).

    # M1 strangler-fig (flag-gated, default OFF): the frontier-model NATIVE
    # TOOL-USE producer assembles the trace instead of the legacy decompose plan.
    # The verdict block below is UNCHANGED — the native producer hands the SAME
    # ExecutionTrace shape to the SAME VerdictReport.from_trace gate.
    if _native_loop_enabled(args):
        try:
            trace = engine.run_turn_native(
                prompt, agent=getattr(engine, "_vgg_agent", None), session=ctx.session
            )
        except Exception as exc:  # noqa: BLE001
            return _emit(VerdictReport.no_trace(goal=prompt or "", error=f"native loop failed: {exc}"))
        try:
            oracle_names = verify_oracle_names(getattr(engine, "_vgg_agent", None), engine)
            predicate_names = verify_predicate_names(getattr(engine, "_vgg_agent", None), engine)
            report = VerdictReport.from_trace(trace, oracle_names, predicate_names)
        except Exception as exc:  # noqa: BLE001
            report = VerdictReport.no_trace(goal=prompt or "", error=f"verdict failed: {exc}")
        return _emit(report, agent=getattr(engine, "_vgg_agent", None))

    # Decompose + execute SYNCHRONOUSLY. A non-VGG (chat / tool_use) route yields
    # no GoalTree -> no deterministic trace -> NO_TRACE (fail closed, exit 1).
    try:
        goal_tree = engine.vgg_decompose(prompt)
    except Exception as exc:  # noqa: BLE001
        return _emit(VerdictReport.no_trace(goal=prompt or "", error=f"decompose failed: {exc}"))

    if goal_tree is None:
        return _emit(VerdictReport.no_trace(goal=prompt or "", error="not a VGG turn (no trace)"))

    try:
        trace = engine.vgg_execute(goal_tree)  # SYNC — never vgg_execute_async
    except Exception as exc:  # noqa: BLE001
        return _emit(VerdictReport.no_trace(goal=goal_tree.goal, error=f"execute failed: {exc}"))

    # Build the verdict from the EXISTING gate, single-sourced from the SAME
    # namespace GoalVerifier uses. Fail CLOSED on any error reading the gate.
    try:
        oracle_names = verify_oracle_names(getattr(engine, "_vgg_agent", None), engine)
        predicate_names = verify_predicate_names(getattr(engine, "_vgg_agent", None), engine)
        report = VerdictReport.from_trace(trace, oracle_names, predicate_names)
    except Exception as exc:  # noqa: BLE001
        report = VerdictReport.no_trace(goal=goal_tree.goal, error=f"verdict failed: {exc}")

    return _emit(report, agent=getattr(engine, "_vgg_agent", None))


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    # --- macOS mjpython re-exec guard (must be before any credential/agent init) ---
    _maybe_reexec_under_mjpython(args)

    _setup_logging(args.verbose)
    _ensure_sigint_under_mjpython()

    # Non-interactive -p/--print: run ONE turn and exit with the verdict code.
    # Under --json route ALL Rich/banner output to stderr so stdout carries ONLY
    # the verdict sentinel lines (ZENO_VERDICT + legacy VECTOR_VERDICT, D184).
    if getattr(args, "print_prompt", None) is not None:
        if getattr(args, "json", False):
            global console
            console = Console(stderr=True)
        _code = run_one_turn(args)
        # The verdict line is already flushed to stdout and the exit code is
        # decided. A live sim (--sim/--sim-go2) leaves a MuJoCo physics daemon
        # thread + ROS2 stack running whose interpreter-teardown can SIGABRT/segv
        # AFTER the verdict — corrupting the process exit code so it no longer
        # matches the (already-correct) verdict. For a single-use non-interactive
        # turn there is nothing to gracefully shut down, so exit HARD with the
        # decided code (after flushing) to keep the harness invariant
        # ``verified == (exit_code == 0)`` honest. Interactive / non-sim turns are
        # unaffected (no daemon to crash). os._exit skips atexit/GC by design.
        if getattr(args, "sim", False) or getattr(args, "sim_go2", False):
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:  # noqa: BLE001
                pass
            os._exit(_code)
        sys.exit(_code)

    # Resolve API key + provider from CLI flags > env vars > config file
    from zeno.vcli.config import resolve_credentials
    api_key, provider, model, base_url = resolve_credentials(
        cli_api_key=args.api_key,
        cli_base_url=args.base_url,
        cli_model=args.model,
    )

    no_key = not api_key
    if no_key:
        # Each console.print is parsed independently — markup tags must balance
        # within a single call (rich does not span tags across print calls).
        console.print("[yellow]No API key configured.[/]")
        console.print("[dim]  /login claude     auto-detect Claude Code subscription[/dim]")
        console.print("[dim]  /login anthropic  enter Anthropic API key[/dim]")
        console.print("[dim]  /login openrouter enter OpenRouter key[/dim]\n")

    # Agent (optional hardware) + active world. An explicit --scenario selects a
    # playground world (its verify predicates win); otherwise a connected agent
    # selects the robot world, else the default cross-platform "dev" world. The
    # resolved world flows into init_vgg(world=...) below, which sets engine._world
    # BEFORE the verifier namespace is built, so the merge picks up its predicates.
    agent = _init_agent(args)
    world = _resolve_active_world(args, agent)

    # Tools (categorized registry for scalable tool management)
    registry: CategorizedToolRegistry = CategorizedToolRegistry()
    tools_list, cat_map = discover_categorized_tools()
    for t in tools_list:
        cat = "default"
        for c, names in cat_map.items():
            if t.name in names:
                cat = c
                break
        registry.register(t, category=cat)
    if agent is not None:
        from zeno.vcli.tools.skill_wrapper import wrap_skills
        for skill_tool in wrap_skills(agent):
            registry.register(skill_tool, category="robot")
    else:
        # Dev world: hide robot/diag/system tools. The 'sim' category (start/stop
        # _simulation) stays enabled so the user can spin up a sim conversationally
        # ("start the arm sim").
        for _c in ("robot", "diag", "system"):
            registry.disable_category(_c)

    # BYO-world tools (Phase-C hook): after the kernel's general tools + skill
    # wrappers are assembled, let the active world contribute its own domain
    # tools into the SAME registry. No-op for dev/robot (their register_tools is
    # a no-op); a plug-and-play world (go2w) adds its tools under its own
    # category here — no kernel edit. Runs regardless of agent so a robot-flavour
    # BYO world driven WITHOUT --sim still gets its tools.
    _register_world_tools(world, registry, agent)
    # BYO-world one-time activation: setup(agent) runs once the world is fully
    # resolved + its tools registered. No-op for any world that omits the hook.
    _world_setup(world, agent)

    # Permissions — the persisted /permissions mode (auto|manual) loads at
    # startup (field ask 2026-07-13); the explicit --no-permission flag always
    # wins. The REAL-ROBOT warning still prints below, every session, when auto.
    permissions = PermissionContext(no_permission=args.no_permission)
    _apply_saved_approval_mode(args, permissions)

    # Session
    session: Session
    if args.resume is not None:
        if args.resume == "latest":
            loaded = get_latest_session()
            if loaded is None:
                console.print("[dim]No previous session, starting new.[/dim]")
                session = create_session(metadata={"model": model})
            else:
                session = loaded
                console.print(f"[dim]Resumed: {session.session_id}[/dim]")
        else:
            session = load_session(args.resume)
            console.print(f"[dim]Resumed: {session.session_id}[/dim]")
    else:
        session = create_session(metadata={"model": model})

    # System prompt (with live robot context)
    robot_ctx_provider = None
    try:
        from zeno.vcli.robot_context import RobotContextProvider
        base = getattr(agent, "_base", None) if agent else None
        sg = getattr(agent, "_spatial_memory", None) if agent else None
        arm = getattr(agent, "_arm", None) if agent else None
        robot_ctx_provider = RobotContextProvider(base=base, scene_graph=sg, arm=arm)
    except ImportError:
        pass
    system_prompt = build_system_prompt(
        agent=agent, cwd=Path.cwd(), robot_context=robot_ctx_provider, world=world
    )

    # Wrap in DynamicSystemPrompt so robot state refreshes each turn
    try:
        from zeno.vcli.dynamic_prompt import DynamicSystemPrompt
        system_prompt = DynamicSystemPrompt(system_prompt, robot_ctx_provider)
    except ImportError:
        pass

    # Intent router + hooks
    intent_router = None
    hooks = None
    try:
        from zeno.vcli.intent_router import IntentRouter
        # Seed the router with the active world's essential tool categories so a
        # BYO world's own tools stay in scope on the routed path (finding #1).
        intent_router = IntentRouter(
            essential_categories=_world_essential_categories(world)
        )
    except ImportError:
        pass
    try:
        from zeno.vcli.hooks import ToolHookRegistry
        hooks = ToolHookRegistry()
    except ImportError:
        pass

    # Explore event streaming — wired via _setup_explore_events on first explore
    _setup_explore_events(console)

    # Backend + engine (deferred if no API key — /login can set it up). Built
    # through the SINGLE fake-LLM seam (production-identical unless VECTOR_FAKE_LLM
    # is set) so the REPL and the non-interactive -p path share one create_backend
    # site (the seam is byte-identical to create_backend in production).
    engine: VectorEngine | None = None
    if api_key:
        backend = create_backend_with_fake_seam(
            provider=provider, api_key=api_key, model=model, base_url=base_url
        )
        engine = VectorEngine(
            backend=backend, registry=registry, system_prompt=system_prompt,
            permissions=permissions, intent_router=intent_router, hooks=hooks,
        )

    # Mutable app state
    _spatial_memory = getattr(agent, "_spatial_memory", None) if agent else None
    _skill_registry = getattr(agent, "_skill_registry", None) if agent else None
    # An explicit --scenario selected a playground world; its name doubles as the
    # active scenario id (banner + mid-session /scenario read/write this).
    _active_scenario = getattr(args, "scenario", None) or None
    app_state: dict[str, Any] = {
        "agent": agent,
        "registry": registry,
        "engine": engine,
        "model": model,
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "scene_graph": _spatial_memory,
        "skill_registry": _skill_registry,
        "robot_ctx_provider": robot_ctx_provider,
        "world": world,
        "scenario": _active_scenario,
        "permissions": permissions,
    }

    # VGG cognitive layer (optional)
    _vgg_step_idx = [0]
    _vgg_total = [0]

    def _vgg_step_display(step: Any) -> None:
        """Print VGG step progress to console — human-readable."""
        _vgg_step_idx[0] += 1
        idx = _vgg_step_idx[0]
        total = _vgg_total[0]
        name = getattr(step, "sub_goal_name", "?")
        strategy = getattr(step, "strategy", "?")
        success = getattr(step, "success", False)
        dur = getattr(step, "duration_sec", 0.0)
        fallback = getattr(step, "fallback_used", False)
        err = getattr(step, "error", "")

        prefix = f"[{idx}/{total}]" if total > 0 else ""

        if success:
            console.print(f"  [{TEAL}]>[/] {prefix} {name} [green]done[/] [dim]{dur:.1f}s[/]")
        elif err == "aborted":
            console.print(f"  [{TEAL}]>[/] {prefix} {name} [yellow]aborted[/]")
        else:
            # Translate common errors to friendly messages
            friendly = err
            if "No rooms learned" in err or "room_not_explored" in err:
                friendly = "no map yet — run explore first"
            elif "navigation_failed" in err or "timed out" in err:
                friendly = "navigation timed out"
            elif "Skill not found" in err:
                friendly = f"skill not available: {strategy}"
            fb_tag = " [dim](tried fallback)[/]" if fallback else ""
            console.print(f"  [{TEAL}]>[/] {prefix} {name} [red]failed[/] — {friendly}{fb_tag} [dim]{dur:.1f}s[/]")

    # Observation surface (INC8): make the verified loop VISIBLE. The per-step
    # EXPORT VIEW (JSON-safe dict) is rendered to a readable line carrying the
    # sub-goal, strategy, verify predicate and a stable PASS/FAIL marker. Runs
    # alongside _vgg_step_display (best-effort) — never affects execution. The
    # verify predicate lives on the active goal tree's sub_goals; the REPL loop
    # refreshes this map when it decomposes each task.
    _vgg_verify_by_name: dict[str, str] = {}

    def _vgg_step_view_display(view: dict[str, Any]) -> None:
        """Render one per-step EXPORT VIEW (sub-goal/strategy/verify/PASS-FAIL)."""
        try:
            from zeno.vcli.cognitive.observation import render_step_view
            verify = _vgg_verify_by_name.get(view.get("sub_goal_name"))
            line = render_step_view(view, verify)
            ok = bool(view.get("success")) and bool(view.get("verify_result"))
            colour = "green" if ok else "red"
            # markup=False: the rendered line carries literal [PASS]/[FAIL]
            # markers that must NOT be parsed as rich style tags.
            console.print(f"    VGG {line}", style=colour, markup=False)
        except Exception:  # noqa: BLE001 — display must never break the loop
            pass

    # Stored so SimStartTool / a mid-session /scenario switch can reuse the real
    # step + view displays when they re-init VGG.
    app_state["vgg_step_callback"] = _vgg_step_display
    app_state["vgg_step_view_callback"] = _vgg_step_view_display
    # Stored so a mid-session /scenario switch (enter_scenario) re-inits VGG with the
    # SAME interactive permission prompt the launch path uses — otherwise switching
    # from a dev world would silently lose the prompt.
    def _gated_tool_permission(n: str, prm: dict[str, Any]) -> str:
        # PermissionContext first: /permissions auto + 'a'=always short-circuit.
        if permissions.no_permission or n in permissions.session_allow:
            return "y"
        ans = ask_permission(n, prm)
        if ans == "a":
            permissions.session_allow.add(n)
        return ans

    app_state["tool_permission_resolver"] = _gated_tool_permission

    try:
        engine.init_vgg(
            agent=agent,
            skill_registry=_skill_registry,
            on_vgg_step=_vgg_step_display,
            on_vgg_step_view=_vgg_step_view_display,
            world=world,
            tool_permission_resolver=_gated_tool_permission,
            # Learning tier (stats + templates) is dev-world only: keep the robot
            # decompose/execute path byte-identical and avoid cross-world stats
            # contamination (a dev 'tool_call' record must not promote onto a
            # robot sub-goal that has no ToolDispatcher).
            persist_dir=_persist_dir() if not world.is_robot() else None,
        )
        if engine._vgg_enabled:
            console.print(f"[dim]  VGG cognitive layer: enabled[/dim]")
    except Exception:
        pass

    # Banner — detect auth source for display
    from zeno.vcli.config import load_claude_oauth
    _oauth = load_claude_oauth()
    if _oauth and api_key == _oauth.get("accessToken"):
        provider_display = f"Claude {_oauth.get('subscriptionType', 'auth')}"
    elif provider == "openrouter":
        provider_display = "OpenRouter"
    elif base_url and "deepseek" in base_url:
        provider_display = "DeepSeek"
    elif provider == "openai_compat":
        provider_display = "OpenAI-compatible"
    elif base_url and "localhost" in base_url:
        provider_display = f"Local ({base_url})"
    else:
        provider_display = "Anthropic"
    print_banner(model, provider_display, agent, scenario=_active_scenario)
    console.print(f"[dim]Session: {session.session_id}[/dim]\n")
    # Persisted-auto safety surface: auto mode never starts silently.
    _warn_if_auto_mode(permissions)

    # REPL setup
    history_dir = _persist_dir()  # ~/.zeno write root; legacy ~/.vector read fallback keeps old REPL history
    history_dir.mkdir(parents=True, exist_ok=True)

    def _get_toolbar() -> HTML:
        agent_now = app_state.get("agent")
        current_model = app_state.get("model", "?")
        parts: list[str] = [f"<b>Zeno</b>"]
        arm_now = getattr(agent_now, "_arm", None) if agent_now else None
        base_now = getattr(agent_now, "_base", None) if agent_now else None
        if arm_now is not None:
            parts.append(f"arm:{getattr(arm_now, 'name', 'arm')}")
        if base_now is not None:
            parts.append(f"base:{getattr(base_now, 'name', 'base')}")
        parts.append(f"model:{current_model.split('/')[-1]}")
        parts.append(f"tools:{len(registry.list_tools())}")
        parts.append(f"msgs:{len(session._entries)}")
        return HTML(f' {" | ".join(parts)} ')

    pt_session: PromptSession = PromptSession(
        history=FileHistory(str(history_dir / "history")),
        completer=ZenoCompleter(),
        complete_while_typing=True,
        style=PT_STYLE,
    )

    _tool_start_times: dict[str, float] = {}
    # Ctrl-C UX (R2-4): one ^C aborts a running task and returns to the prompt;
    # a second consecutive ^C (at the prompt) exits cleanly. Reset on any input.
    interrupt_pending = False

    # TYPED INTERJECT (field ask 2026-07-11): a background stdin reader ACTIVE
    # ONLY while a blocking turn executes (each turn path opens/closes the
    # window). Typed lines queue; the kernel checks the queue at safe boundaries
    # (native-loop iteration top / per motor dispatch) and cancels via the SAME
    # world seam Ctrl+C uses; the queued line runs as the immediate next turn
    # (picked up below, before the prompt). Registered module-wide so
    # ask_permission suspends it around the y/n/a prompt (stdin collision).
    from zeno.vcli.interject import InterjectReader, set_current_reader
    interject_reader = InterjectReader()
    app_state["interject"] = interject_reader
    set_current_reader(interject_reader)

    try:
        while True:
            # ---- Read input ----
            # An interjected line (typed mid-turn) runs as the IMMEDIATE next
            # turn — echoed visibly so the operator sees what took over.
            _queued = interject_reader.pop()
            if _queued is not None:
                console.print(f"  [yellow]⏸ 插队:[/] {_queued}")
                raw = _queued
            else:
                try:
                    raw = pt_session.prompt(
                        HTML(f'<style fg="{TEAL}" bold="true">zeno&gt;</style> '),
                        bottom_toolbar=_get_toolbar,
                    )
                except EOFError:
                    break
                except KeyboardInterrupt:
                    if interrupt_pending:
                        break  # second consecutive Ctrl-C -> exit cleanly
                    interrupt_pending = True
                    console.print("\n[dim]Press Ctrl-C again or type quit to exit.[/dim]")
                    continue

            interrupt_pending = False  # any successful input clears the pending exit
            user_input = raw.strip()
            if not user_input:
                continue

            # ---- Exit ----
            if is_exit_command(user_input):
                break

            # ---- Slash commands ----
            if is_slash_command(user_input):
                parts = user_input.split()
                if not _handle_slash_command(parts[0][1:], parts[1:], registry, session, app_state):
                    break
                continue

            # ---- ! shell passthrough ----
            if user_input.startswith("!"):
                cmd = user_input[1:].strip()
                if cmd:
                    try:
                        proc = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30)
                        if proc.stdout:
                            console.print(proc.stdout, end="")
                        if proc.stderr:
                            console.print(f"[dim]{proc.stderr}[/]", end="")
                    except subprocess.TimeoutExpired:
                        console.print("[yellow]Command timed out (30s)[/]")
                    except Exception as exc:
                        console.print(f"[red]Error:[/] {exc}")
                continue

            # ---- Engine turn ----
            if engine is None:
                console.print(f"[yellow]No API key. Use /login to authenticate first.[/]")
                continue

            # CUTOVER (2026-06-19, owner-approved): native-attempt-then-fallback is the
            # REPL's DEFAULT turn path, so bare `zeno` + natural language runs the
            # redesign's NATIVE TOOL-USE producer (CLAUDE.md North Star "Acceptance
            # interface"). For an action-shaped turn, ATTEMPT native first; if it
            # DISPATCHED an action it OWNS the turn (its honest verdict is rendered).
            # If it took NO action (could not route — e.g. "启动 go2 仿真", embodiment
            # switch, chat) FALL THROUGH to the UNCHANGED legacy routing below, so sim
            # launch + NL embodiment switch keep working via the untouched tool_use
            # path. VECTOR_REPL_NATIVE=0 forces the pure-legacy REPL (reversible).
            # native OWNS navigation too (CEO architecture call 2026-06-19: the
            # model-driven producer is the correct design; the hardcoded legacy planner
            # is being strangled, not retreated to). Obstacle-AVOIDANCE for native nav
            # (route through the nav-stack instead of the open-loop walk) and LATENCY
            # are tracked native improvements (see docs/ARCHITECTURE.md), NOT reasons to
            # fall back to legacy.
            if _repl_native_enabled() and _intent_actionable(engine, user_input):
                if _repl_attempt_native(engine, user_input, session, app_state, console):
                    continue
                # native took NO action -> fall through to legacy routing (unchanged).

            try:
                # Single in-place progress region for the whole turn. A reasoning
                # model (DeepSeek) streams NO text for several seconds while it
                # thinks; the region shows one calm "thinking…" status that resolves
                # into the streamed answer — it is paused/cleared before any
                # tool-execution line is printed so box frames never stack and the
                # prompt is not duplicated.
                _turn_started = time.monotonic()

                def _status_content(text: str, elapsed: float, is_thinking: bool) -> Panel:
                    if is_thinking:
                        dots = "." * (int(elapsed) % 4)
                        label = f"thinking{dots}" + (
                            f"  [dim]{elapsed:.0f}s[/]" if elapsed >= 1 else ""
                        )
                        return Panel(
                            Text.from_markup(label, style="dim italic"),
                            title=V_LABEL,
                            title_align="left",
                            border_style=DIM_TEAL,
                            padding=(0, 1),
                            width=min(console.width, 80),
                        )
                    return Panel(
                        text,
                        title=V_LABEL,
                        title_align="left",
                        border_style=TEAL,
                        padding=(0, 1),
                        width=min(console.width, 80),
                    )

                status = TurnStatus(
                    content_factory=_status_content,
                    live_factory=lambda renderable: Live(
                        renderable,
                        console=console,
                        refresh_per_second=8,
                        transient=True,
                    ),
                )

                def on_text(chunk: str) -> None:
                    status.update_text(chunk)

                def on_reasoning(_chunk: str) -> None:
                    # Hidden reasoning trace: keep the "thinking…" status alive with
                    # an elapsed counter; never rendered as answer text.
                    status.thinking(time.monotonic() - _turn_started)

                def _format_tool_display(name: str, p: dict[str, Any]) -> str:
                    """Context-aware tool call display."""
                    if name == "file_read":
                        path = p.get("file_path", "")
                        short = path.split("/")[-1] if "/" in path else path
                        offset = p.get("offset", 0)
                        limit = p.get("limit", "")
                        loc = f":{offset}-{offset + limit}" if offset and limit else ""
                        return f"[dim]read[/] {short}{loc}"
                    if name == "file_edit":
                        path = p.get("file_path", "")
                        short = path.split("/")[-1] if "/" in path else path
                        old = str(p.get("old_string", ""))[:30]
                        new = str(p.get("new_string", ""))[:30]
                        return f"[dim]edit[/] {short}: [red]{old}[/] [dim]→[/] [green]{new}[/]"
                    if name == "file_write":
                        path = p.get("file_path", "")
                        short = path.split("/")[-1] if "/" in path else path
                        return f"[dim]write[/] {short}"
                    if name == "bash":
                        cmd = str(p.get("command", ""))[:60]
                        return f"[dim]$[/] {cmd}"
                    if name == "navigate":
                        room = p.get("room", "?")
                        return f"[dim]navigate →[/] {room}"
                    if name == "explore":
                        return "[dim]explore[/] starting background exploration"
                    if name in ("walk", "turn", "stand", "sit", "lie_down", "stop"):
                        parts = [name]
                        if p.get("direction"):
                            parts.append(str(p["direction"]))
                        if p.get("distance"):
                            parts.append(f"{p['distance']}m")
                        if p.get("angle"):
                            parts.append(f"{p['angle']}°")
                        return "[dim]" + " ".join(parts) + "[/]"
                    if name == "skill_reload":
                        return f"[dim]reload[/] {p.get('skill_name', '?')}"
                    if name == "scene_graph_query":
                        qt = p.get("query_type", "?")
                        room = p.get("room", "")
                        return f"[dim]scene_graph[/] {qt}" + (f" ({room})" if room else "")
                    if name in ("ros2_topics", "ros2_nodes"):
                        action = p.get("action", "?")
                        topic = p.get("topic", p.get("node", ""))
                        return f"[dim]{name}[/] {action}" + (f" {topic}" if topic else "")
                    if name == "ros2_log":
                        return f"[dim]log[/] {p.get('log_name', '?')}"
                    if name in ("glob", "grep"):
                        pattern = p.get("pattern", "")[:40]
                        return f"[dim]{name}[/] {pattern}"
                    if name == "nav_state":
                        return "[dim]nav_state[/]"
                    if name == "terrain_status":
                        return "[dim]terrain_status[/]"
                    if name == "start_simulation":
                        st = p.get("sim_type", "go2")
                        return f"[dim]sim start[/] {st}"
                    # Fallback: generic display
                    if p:
                        items = [f"{k}={str(v)[:20]}" for k, v in list(p.items())[:2]]
                        return f"[dim]{name}[/]({', '.join(items)})"
                    return f"[dim]{name}[/]"

                def _format_result_summary(name: str, result: Any) -> str:
                    """Extract key info from tool result for display."""
                    if result.is_error:
                        content = result.content or ""
                        # Show first line of error + suggested action
                        lines = content.split("\n")
                        msg = lines[0][:60]
                        suggested = next((l for l in lines if l.startswith("Suggested:")), "")
                        if suggested:
                            return f"  [dim]{msg}[/]\n    [yellow]{suggested}[/]"
                        return f"  [dim]{msg}[/]"

                    meta = result.metadata if hasattr(result, "metadata") else {}
                    if not meta:
                        return ""

                    # Navigate: show arrival info
                    if name == "navigate":
                        room = meta.get("room", "")
                        state = meta.get("robot_state_after", {})
                        pos = state.get("position", [])
                        if room and pos:
                            return f"  [dim]▸ 到达 {room} ({pos[0]}, {pos[1]})[/]"
                        if room:
                            return f"  [dim]▸ 到达 {room}[/]"
                    # Explore: show status
                    if name == "explore":
                        status = meta.get("status", "")
                        rooms = meta.get("rooms_visited", meta.get("all_rooms", []))
                        if rooms:
                            return f"  [dim]▸ {len(rooms)} rooms discovered[/]"
                    # Where am i
                    if name == "where_am_i":
                        room = meta.get("room", "")
                        pos = meta.get("position", [])
                        if room:
                            return f"  [dim]▸ {room} ({pos[0]}, {pos[1]})[/]" if pos else f"  [dim]▸ {room}[/]"
                    # Motor skills: show post-state
                    state = meta.get("robot_state_after", {})
                    if state:
                        room = state.get("room", "")
                        pos = state.get("position", [])
                        if room and pos:
                            return f"  [dim]▸ pos=({pos[0]}, {pos[1]}) room={room}[/]"

                    return ""

                _tool_displays: dict[str, str] = {}

                def on_tool_start(name: str, p: dict[str, Any]) -> None:
                    _tool_start_times[name] = time.monotonic()
                    _tool_displays[name] = _format_tool_display(name, p)

                def on_tool_end(name: str, result: Any) -> None:
                    elapsed = time.monotonic() - _tool_start_times.pop(name, time.monotonic())
                    display = _tool_displays.pop(name, name)
                    tag = "[green]ok[/]" if not result.is_error else "[red]fail[/]"
                    summary = _format_result_summary(name, result)
                    # Pause the live region BEFORE printing — printing into an active
                    # Live interleaves with its redraw and re-stacks the box frame.
                    with status.paused():
                        console.print(f"  [{TEAL}]▸[/] {display} {tag} [dim]{elapsed:.1f}s[/]")
                        if summary:
                            console.print(summary)

                    # Hook explore event callback after sim/explore tools run
                    if name in ("start_simulation", "explore"):
                        _setup_explore_events(console)

                # --- Routing (Stage 5, S5.4 cut-over) ---
                # The keyword gate is now an OPTIMIZATION HINT, not a correctness
                # fork: classify_intent (the single, observable decision the unified
                # controller uses) decides only the RENDERING shape here.
                #   * vgg route  -> the async plan renderer below (CLI stays
                #     responsive; this IS the unified plan path: vgg_decompose ->
                #     vgg_execute, deterministic verify + replan).
                #   * tool_use route -> run_turn_unified, which produces the answer
                #     via the ReAct loop AND closes the loop with a verified
                #     answer-only trace (chat is verified too; the moat is intact).
                # VECTOR_LEGACY_TURN=1 restores the exact pre-cutover fork
                # (vgg_decompose-then-run_turn) for one release as a fallback.
                _legacy_turn = _env("LEGACY_TURN") == "1"
                if _legacy_turn:
                    goal_tree = engine.vgg_decompose(user_input)
                else:
                    goal_tree = (
                        engine.vgg_decompose(user_input)
                        if engine.classify_intent(user_input).use_vgg
                        else None
                    )
                if goal_tree is not None:
                    # Show plan BEFORE execution
                    console.print()
                    console.print(f"  [{TEAL}]>[/] [bold]VGG[/] {goal_tree.goal}")
                    for i, sg in enumerate(goal_tree.sub_goals, 1):
                        dep = f" (after {', '.join(sg.depends_on)})" if sg.depends_on else ""
                        strat = f" [dim]via {sg.strategy}[/]" if sg.strategy else ""
                        console.print(f"  [{TEAL}]>[/]   [{i}/{len(goal_tree.sub_goals)}] {sg.name} — {sg.description}{strat}{dep}")
                    console.print()

                    # Reset step counter for callback
                    _vgg_step_idx[0] = 0
                    _vgg_total[0] = len(goal_tree.sub_goals)
                    # Refresh the verify-predicate map the per-step view renderer
                    # reads (INC8) — keyed by sub_goal name for this plan.
                    _vgg_verify_by_name.clear()
                    _vgg_verify_by_name.update(
                        {sg.name: sg.verify for sg in goal_tree.sub_goals}
                    )

                    # Execute async — CLI remains responsive
                    # `_user_input` freezes the triggering command at def-time
                    # (B023): this closure runs on a BACKGROUND thread after the
                    # REPL has read the NEXT input, so a free capture of the loop
                    # variable `user_input` would record the wrong user turn.
                    def _on_vgg_complete(
                        trace: Any, _user_input: str = user_input
                    ) -> None:
                        n_steps = len(trace.steps)
                        n_ok = sum(1 for s in trace.steps if s.success)
                        dur = trace.total_duration_sec
                        # Evidence gate: a successful run only counts as *verified*
                        # when its steps actually consume a live verify-namespace
                        # oracle (world-agnostic now — the robot bypass is gone).
                        # oracle_names single-sourced from the SAME namespace
                        # GoalVerifier uses. Fail CLOSED (not verified) on any error
                        # so the moat never silently passes.
                        try:
                            from zeno.vcli.cognitive.trace_store import (
                                evidence_passed,
                                verify_oracle_names,
                            )
                            _oracle_names = verify_oracle_names(
                                getattr(engine, "_vgg_agent", None), engine
                            )
                            _evidence = evidence_passed(trace, _oracle_names)
                        except Exception:  # noqa: BLE001
                            _evidence = False
                        if trace.success and _evidence:
                            console.print(f"  [{TEAL}]>[/] [green]all {n_steps} steps done[/] [dim]{dur:.1f}s[/]")
                        elif trace.success:
                            console.print(f"  [{TEAL}]>[/] [yellow]completed without verifiable evidence[/] — {n_steps} steps ran [dim]{dur:.1f}s[/]")
                        elif n_ok > 0:
                            console.print(f"  [{TEAL}]>[/] [yellow]{n_ok}/{n_steps} steps done[/], rest failed [dim]{dur:.1f}s[/]")
                        else:
                            console.print(f"  [{TEAL}]>[/] [red]task failed[/] — 0/{n_steps} steps succeeded [dim]{dur:.1f}s[/]")

                        # Observation surface (INC8): show the full verified loop
                        # — goal tree + per-step PASS/FAIL + any replan notes +
                        # outcome — from the run snapshot (pure EXPORT VIEW; never
                        # re-derived from frozen types). Best-effort display.
                        try:
                            from zeno.vcli.cognitive.observation import (
                                render_run_snapshot,
                            )
                            snapshot = engine.vgg_run_snapshot(trace)
                            for snap_line in render_run_snapshot(snapshot).splitlines():
                                # markup=False: literal [PASS]/[FAIL] markers.
                                console.print(f"  {snap_line}", style="dim", markup=False)
                        except Exception:  # noqa: BLE001 — display only
                            pass

                        # Record in session
                        step_summary = "\n".join(
                            f"  {s.sub_goal_name}: {'ok' if s.success else 'FAILED'}"
                            + (f" ({s.error})" if s.error else "")
                            for s in trace.steps
                        )
                        session.append_user(_user_input)
                        session.append_assistant(
                            f"[VGG executed]\nGoal: {trace.goal_tree.goal}\n"
                            f"Result: {'success' if trace.success else 'partial failure'}\n"
                            f"Steps:\n{step_summary}"
                        )

                    # Runs on a background thread (CLI stays responsive) EXCEPT
                    # when a GUI viewer is live UNDER MJPYTHON (macOS) — only
                    # there GLFW is main-thread-only, so it executes
                    # synchronously on this thread and the prompt returns once
                    # the arm finishes. Linux/Windows keep the background
                    # thread even with a viewer (REPL stays responsive).
                    engine.vgg_execute_async(goal_tree, on_complete=_on_vgg_complete)
                    continue  # next input (immediately when headless)

                # --- Normal tool_use path ---
                # Pause the live region around any interactive permission prompt so
                # the prompt is not drawn into (and duplicated by) the live box.
                def _ask_permission_paused(n: str, p: dict[str, Any]) -> str:
                    with status.paused():
                        return ask_permission(n, p)

                # Suppress ROS2/subprocess log noise during engine turn
                _saved_stderr = sys.stderr
                try:
                    sys.stderr = open(os.devnull, "w")
                except OSError:
                    pass
                # TYPED INTERJECT window around the blocking chat/tool turn: the
                # run_turn loop has no kernel-side boundary check (chat rounds
                # are short); a line typed here queues and runs as the NEXT turn.
                interject_reader.start()
                try:
                    status.start()  # one live region for the whole turn
                    if _legacy_turn:
                        # Legacy fallback (VECTOR_LEGACY_TURN=1): the open ReAct loop
                        # with no closed-loop verify — kept one release.
                        turn_result: TurnResult = engine.run_turn(
                            user_message=user_input,
                            session=session,
                            agent=app_state.get("agent"),
                            on_text=on_text,
                            on_tool_start=on_tool_start,
                            on_tool_end=on_tool_end,
                            ask_permission=_ask_permission_paused,
                            app_state=app_state,
                            on_reasoning=on_reasoning,
                        )
                    else:
                        # Unified controller: the ReAct loop produces the answer
                        # (streaming, permissions, tool hooks, P0 stop all preserved
                        # by run_turn underneath) and the harness wraps it in a
                        # verified answer-only trace — closing the loop for chat too.
                        turn_result = engine.run_turn_unified(
                            user_message=user_input,
                            session=session,
                            agent=app_state.get("agent"),
                            on_text=on_text,
                            on_tool_start=on_tool_start,
                            on_tool_end=on_tool_end,
                            ask_permission=_ask_permission_paused,
                            app_state=app_state,
                            on_reasoning=on_reasoning,
                        )
                except KeyboardInterrupt:
                    _operator_interrupt(app_state)
                    continue  # keep the REPL loop alive
                finally:
                    # Stop/clear the single region BEFORE printing the final answer,
                    # so the box never stacks and the prompt is not duplicated.
                    interject_reader.stop()  # window closes before any prompt
                    status.stop()
                    sys.stderr = _saved_stderr

                # Final response: highlighted panel with braille V title
                global _last_response
                if turn_result.text:
                    _last_response = turn_result.text.strip()
                    console.print()  # spacing before response
                    console.print(render_response(
                        _last_response,
                        width=min(console.width, 80),
                    ))

                # Auto-compact (summarize old context instead of truncating)
                if len(session._entries) > 50:
                    before, after = session.compact(keep_recent=12)
                    console.print(f"[dim]  compacted {before} -> {after} entries (old context summarized)[/dim]")

                # Token usage (show in/out breakdown)
                if turn_result.usage:
                    u = turn_result.usage
                    if u.input_tokens or u.output_tokens:
                        console.print(f"[dim]  in={u.input_tokens:,} out={u.output_tokens:,}[/]")
                console.print()

            except KeyboardInterrupt:
                # One Ctrl-C aborts the running task and returns to the prompt;
                # arm the pending-exit so an immediate second Ctrl-C quits (R2-4).
                interrupt_pending = True
                console.print("\n[yellow]Interrupted.[/yellow] [dim](Ctrl-C again or 'quit' to exit)[/dim]")
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str:
                    current_model = app_state.get("model", "?")
                    console.print(f"[yellow]  Rate limited on {current_model}.[/]")
                    console.print(f"[dim]  Try: /model claude-haiku-4-5 (lower rate limit)[/dim]")
                elif "401" in err_str or "authentication" in err_str.lower():
                    console.print(f"[yellow]  Authentication failed. Use /login to reconfigure.[/]")
                elif "404" in err_str or "not_found" in err_str:
                    console.print(f"[yellow]  Model not found: {app_state.get('model', '?')}[/]")
                    console.print(f"[dim]  Try: /model claude-haiku-4-5[/dim]")
                else:
                    console.print(f"[red]Error:[/] {exc}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()

    finally:
        set_current_reader(None)
        interject_reader.stop()
        session.save()
        console.print(f"[dim]Session saved: {session.session_id}[/dim]")
        # Persist scene graph if agent has one
        _agent_final = app_state.get("agent")
        if _agent_final is not None:
            _sm = getattr(_agent_final, "_spatial_memory", None)
            if _sm is not None and hasattr(_sm, "save") and hasattr(_sm, "stats"):
                try:
                    _sm.save()
                    _sm_stats = _sm.stats()
                    console.print(
                        f"[dim]Scene graph saved: "
                        f"{_sm_stats['rooms']} rooms, {_sm_stats['objects']} objects[/dim]"
                    )
                except Exception as _exc:
                    console.print(f"[yellow]Scene graph save failed: {_exc}[/yellow]")
        # BYO-world lifecycle: release the active world's resources at REPL exit.
        # A mid-session /scenario switch swaps app_state["world"], so tear down the
        # CURRENT world (best-effort; no-op unless the world defines teardown()).
        _world_teardown(app_state.get("world"))


if __name__ == "__main__":
    main()
