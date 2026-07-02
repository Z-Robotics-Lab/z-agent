"""D163 bare-REPL acceptance driver.

Drives the ACTUAL bare `vector-cli` REPL under a PTY (NO -p, NO --sim-go2 flag)
with natural-language commands, exactly as a user would:

    启动带手臂的 go2 仿真   -> SimStartTool._start_go2 (VECTOR_NO_ROS2=1 -> in-process)
    <fetch NL>            -> native producer, renders `verdict ... verified=...`
    <place NL>            -> native producer, renders `verdict ... verified=...`

Proves the D163 fix: launch_explore.sh must be EMPTY throughout (in-process path).
Runs HEADLESS (no X display) so the sim uses egl offscreen rendering: perception grounds
AND the honest same-process verdict snapshot (VECTOR_SNAPSHOT_DIR/verdict_*.png) renders —
that offscreen 3rd-person frame is the Qwen3-VL eyes (no fragile desktop-window grab).
Reads the console `verified=True/False` as the moat-oracle GT.

Usage: python repl_accept.py <fetch_nl> <place_nl> <tag> [mode]
Provider-agnostic: VECTOR_PROVIDER selects the routing brain (qwen|deepseek|openrouter),
resolved by vcli.config from the .env keys. Default qwen (byte-compatible with history);
set VECTOR_PROVIDER=deepseek to drive the SAME bare REPL when qwen is in arrears. Runs ONE
sim, one colour.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time

import pexpect

ROOT = "/home/yusen/Desktop/vector_os_nano"
FETCH = sys.argv[1] if len(sys.argv) > 1 else "把绿色的瓶子拿过来"
PLACE = sys.argv[2] if len(sys.argv) > 2 else "把绿色的瓶子放到架子上"
TAG = sys.argv[3] if len(sys.argv) > 3 else "r"
# MODE: "both" (fetch then place — legacy), "fetch" (fetch only), "place" (place only,
# fresh session so the bottle starts on the table, not pre-held by a prior fetch turn —
# a pre-held bottle makes place-turn grasp UNCAUSED, corrupting the place verdict).
MODE = sys.argv[4] if len(sys.argv) > 4 else "both"
# Fail LOUD on a bad invocation. A wrong arg-order (e.g. passing a colour where MODE goes)
# silently no-ops every action turn and quits immediately — wasting a full ~6-min sim with
# no verdict (observed 2026-07-01: `... <tag> green place` set MODE="green", ran nothing).
_VALID_MODES = ("both", "fetch", "place", "combo", "quantity")
if MODE not in _VALID_MODES:
    sys.exit(f"[driver] FATAL: MODE={MODE!r} not in {_VALID_MODES}. "
             f"Usage: repl_accept.py <fetch_nl> <place_nl> <tag> [mode]. Refusing to burn a sim.")
SNAP = f"/tmp/repl_accept/{TAG}"
os.system(f"rm -rf {SNAP}; mkdir -p {SNAP}")

# Provider-agnostic acceptance (plug-and-play model seam — North Star: bring your own
# model, no kernel edits). VECTOR_PROVIDER selects the routing brain; vcli.config already
# supports qwen / deepseek / openrouter (all OpenAI-compatible). Defaults reproduce the
# historical qwen wiring EXACTLY when nothing is overridden (byte-compatible). When qwen is
# in arrears, drive the SAME bare REPL through a reachable provider (e.g. deepseek-chat).
PROVIDER = os.environ.get("VECTOR_PROVIDER", "qwen").lower()
# Per-provider planner model env (only the selected provider's var is injected; a caller may
# still override via the real env var, which os.environ.get picks up as the default here).
_PLANNER = {
    "qwen": {"QWEN_MODEL": os.environ.get("QWEN_MODEL", "qwen-max")},
    "deepseek": {"DEEPSEEK_MODEL": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")},
    "openrouter": {"VECTOR_MODEL": os.environ.get("VECTOR_MODEL", "anthropic/claude-3.5-sonnet")},
}.get(PROVIDER, {})
# Eyes second-witness (vision judge). Default: qwen3-vl on DashScope (historical). Override
# via VECTOR_JUDGE_* to any OpenAI-compatible VLM whose credit is NOT exhausted (e.g. an
# OpenRouter VLM). NOTE: the AUTHORITATIVE acceptance is the GT moat oracle + the offscreen
# eyes_*.png this driver reads back — the judge is a secondary witness, never the moat.
_JUDGE = {
    "VECTOR_JUDGE_BASE_URL": os.environ.get(
        "VECTOR_JUDGE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "VECTOR_JUDGE_MODEL": os.environ.get("VECTOR_JUDGE_MODEL", "qwen3-vl-plus"),
    "VECTOR_JUDGE_API_KEY": os.environ.get(
        "VECTOR_JUDGE_API_KEY", os.environ.get("QWEN_API_KEY", "")),
}
env = dict(os.environ)
env.update({
    "PATH": "/usr/bin:" + os.environ.get("PATH", ""),
    "VECTOR_PROVIDER": PROVIDER,
    "VECTOR_MAX_TOKENS": os.environ.get("VECTOR_MAX_TOKENS", "8000"),
    "VECTOR_SIM_WITH_ARM": "1",
    "VECTOR_NO_ROS2": "1",
    "MUJOCO_GL": "egl",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "VECTOR_SNAPSHOT_DIR": SNAP,
    **_PLANNER,
    **_JUDGE,
})
# HEADLESS acceptance (verified 2026-07-01): drop the X display so reconcile_render_backend
# keeps egl (viewer suppressed). egl+headless is the reliable render path — perception grounds
# (5/5 vs glfw+viewer 2/2, D166 DEBUG) AND the honest same-process verdict snapshot
# (snapshot_on_verdict -> verdict_*.png) renders offscreen without main-thread GLFW context
# contention. This is what makes the eyes frame the real 3rd-person sim render instead of a
# fragile `import -window` desktop grab (which mis-grabbed the terminal AND hung the campaign
# ~13 min in interactive click-to-select mode). A human on a desktop still gets glfw+viewer.
env.pop("DISPLAY", None)
env.pop("WAYLAND_DISPLAY", None)

LOG = open(f"{SNAP}/session.log", "wb")


def launch_explore_running() -> bool:
    # Match the ACTUAL launch_explore.sh subprocess — NOT the loop supervisor's
    # claude -p argv, whose goal text literally contains the string
    # "launch_explore" (that false-positive bit the first run). Exclude claude.
    r = subprocess.run(["pgrep", "-af", r"launch_explore\.sh"], capture_output=True, text=True)
    hits = [ln for ln in r.stdout.splitlines() if "claude" not in ln and ln.strip()]
    return bool(hits)


def wait_prompt(child, timeout=90):
    # prompt_toolkit repaints; match the stable "vector>" marker.
    child.expect(r"vector>", timeout=timeout)


def drain_until_quiet(child, quiet=3.0, max_wait=180):
    """Block until the REPL output goes SILENT for ``quiet`` seconds (turn fully done).

    The `vector>` prompt is echoed AND repainted constantly by prompt_toolkit, so
    ``wait_prompt`` matches the just-typed command line instantly and returns BEFORE the
    turn finishes — injecting the next command mid-turn, where prompt_toolkit eats/garbles
    it (root cause of the D171 place-turn no-op; DEBUG.md H4). Instead of matching a
    prompt, we wait for a quiet gap: keep reading with a short timeout; each chunk resets
    the clock; when no output arrives for ``quiet`` s the turn has settled and it is safe
    to send the next line. Bounded by ``max_wait``."""
    waited = 0.0
    while waited < max_wait:
        try:
            child.expect(r".+", timeout=quiet)  # any output resets the quiet window
            waited = 0.0
        except pexpect.TIMEOUT:
            return True  # no output for `quiet` s -> settled
        except pexpect.EOF:
            return False
        waited += quiet
    return False


def _clean_log(snap: str) -> str:
    """ANSI+spinner-stripped view of the raw REPL log (for ground-truth marker checks).

    prompt_toolkit repaints the screen with cursor/colour escapes and a braille spinner that
    interleave INTO marker text, so a LIVE ``child.expect(r"sim start go2 ok")`` on the raw PTY
    stream never matches even when the marker really printed (observed 2026-07-01: the sim
    genuinely started — ``▸ sim start go2 ok 4.2s`` was in the log — yet 4 live-expects timed
    out and the driver falsely reported SIM NEVER STARTED). So sync GT markers the SAME way the
    verdict parser does: strip escapes + spinner glyphs, then substring-check."""
    try:
        raw = open(f"{snap}/repl.raw.log", encoding="utf-8", errors="replace").read()
    except OSError:
        return ""
    clean = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][0-9;]*|\x1b", "", raw)
    return re.sub(r"[⠀-⣿]", "", clean)


def _eyes_frame(snap: str, tag: str) -> None:
    """Record the honest eyes-on-sim frame for turn ``tag``.

    The frame is the SAME-PROCESS offscreen 3rd-person render the verdict hook already
    writes (``capture.snapshot_on_verdict`` -> ``$VECTOR_SNAPSHOT_DIR/verdict_<stamp>.png``)
    — the actual ``MjModel``/``MjData`` the turn ran on, NOT a desktop screenshot. Because we
    run headless (egl, no viewer), that offscreen render is reliable and needs no X server.
    Here we simply COPY the newest verdict_*.png to a stable ``eyes_<tag>.png`` so each turn's
    frame survives (the verdict hook reuses the dir). No `import -window` (it grabbed the wrong
    window and hung the campaign in interactive select mode).
    """
    out = f"{snap}/eyes_{tag}.png"
    verdicts = sorted(
        (f for f in os.listdir(snap) if f.startswith("verdict_") and f.endswith(".png")),
        key=lambda f: os.path.getmtime(os.path.join(snap, f)),
    )
    if verdicts:
        src = os.path.join(snap, verdicts[-1])
        shutil.copyfile(src, out)
        print(f"[driver] eyes frame (offscreen verdict render) -> {out}", flush=True)
    else:
        print("[driver] no verdict_*.png emitted (snapshot_on_verdict yielded nothing)", flush=True)


def _llm_preflight() -> None:
    """Fail FAST if the RESOLVED planner provider is unusable (arrears/denied/no key), instead of
    spawning the sim and burning an 8-min per-verdict timeout against a dead LLM. Provider-agnostic:
    it probes EXACTLY what the bare REPL will resolve via vcli.config (qwen / deepseek / openrouter —
    the plug-and-play model seam), NOT a hardcoded DashScope endpoint. A billing/'Arrearage' error
    means that provider is down (Yusen-only fix) — pick another provider (VECTOR_PROVIDER=…)."""
    sys.path.insert(0, ROOT)
    try:
        from vector_os_nano.vcli.config import resolve_credentials  # noqa: PLC0415
        key, provider, model, base_url = resolve_credentials()
    except Exception as e:  # noqa: BLE001
        print(f"[driver] PREFLIGHT: resolve_credentials failed ({e}); proceeding blind.", flush=True)
        return
    if not key:
        print(f"[driver] PREFLIGHT: no API key resolved for provider={provider} — cannot run.", flush=True)
        sys.exit(3)
    try:
        from openai import OpenAI  # noqa: PLC0415
        c = OpenAI(api_key=key, base_url=base_url or None)
        c.chat.completions.create(model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=1)
        print(f"[driver] PREFLIGHT: planner reachable (provider={provider} model={model}).", flush=True)
    except Exception as e:  # noqa: BLE001
        body = str(e)
        low = body.lower()
        if "arrearage" in low or "access denied" in low or "overdue" in low or "insufficient" in low:
            print(f"[driver] PREFLIGHT BLOCKED: provider={provider} model={model} account unusable "
                  f"(billing). Try another VECTOR_PROVIDER. {body[:220]}", flush=True)
            sys.exit(4)
        print(f"[driver] PREFLIGHT: probe error {type(e).__name__}: {body[:220]} — proceeding.", flush=True)


_llm_preflight()
print(f"[driver] spawning BARE vector-cli REPL (no -p/--sim-go2); FETCH={FETCH!r} PLACE={PLACE!r}", flush=True)
# Bare module invocation with --native-loop only (mirrors the wrapper, sans flags).
child = pexpect.spawn(
    f"{ROOT}/.venv/bin/python", ["-m", "vector_os_nano.vcli.cli", "--native-loop"],
    env=env, cwd=ROOT, encoding="utf-8", codec_errors="replace",
    timeout=120, dimensions=(50, 200),
)
# Log the raw REPL stream to a file (ANSI-heavy); keep stdout for [driver] lines.
child.logfile_read = open(f"{SNAP}/repl.raw.log", "w")
result = {"launch_explore_seen": False, "fetch_verified": None, "place_verified": None}

try:
    wait_prompt(child, timeout=60)
    print("\n[driver] REPL up. Starting sim by NL...", flush=True)
    # Sim build: MuJoCoGo2 connect + arm + perception + scene graph. Sync on the sim
    # tool-completion marker "sim start go2 ok", NOT the echoed `vector>` prompt (which
    # matches instantly and made us inject the next command mid-turn — DEBUG.md H4).
    # The sim-start NL is MODEL-routed and non-deterministic: some brains invoke the
    # SimStartTool directly, some reply with a clarifying question (deepseek-chat asked
    # "你要用带臂模式对吗?" instead of starting). So: send an imperative start, and if the
    # tool marker doesn't appear, ANSWER the model's question with NL (acceptance-face-legal
    # — still bare cli + NL) and retry, up to a few rounds. Once the marker appears, drain
    # until the whole sim-start turn (tool + chat tail) goes quiet before the action.
    started = False
    for attempt in range(4):
        msg = ("启动带手臂的 go2 仿真，现在就开始，直接执行不用问我" if attempt == 0
               else "是的，用带手臂模式，现在就启动仿真，直接执行")
        child.sendline(msg)
        # Let the WHOLE sim-start turn settle (tool call + chat tail), THEN check ground
        # truth in the ANSI-stripped log. A live expect on the raw PTY stream misses the
        # marker because prompt_toolkit's repaint/spinner splits it (see _clean_log). GT is
        # the SimStartTool completion line "sim start go2 ok", NEVER the model's chat claim.
        drain_until_quiet(child, quiet=4.0, max_wait=150)
        if "sim start go2 ok" in _clean_log(SNAP):
            started = True
            break
        print(f"\n[driver] sim not started on attempt {attempt} (model chatted/asked); re-issuing", flush=True)
    if not started:
        # Ground truth: we only set started=True on the "sim start go2 ok" tool-completion
        # marker — NEVER on the model's chat CLAIM ("已经启动完毕了"), which it can author
        # without invoking the tool (Invariant 1: sync on GT the actor can't fake). No sim ->
        # sending actions just times out 300s each against a dead prompt; abort honestly.
        print("\n[driver] SIM NEVER STARTED via NL after retries — aborting turn (no fake verdict)", flush=True)
        raise SystemExit("sim-never-started")
    if launch_explore_running():
        result["launch_explore_seen"] = True
        print("\n[driver] !!! launch_explore RUNNING — ROS2 stack path took (FIX FAILED)", flush=True)
    drain_until_quiet(child, quiet=3.0, max_wait=120)
    # Double-check after ready.
    if launch_explore_running():
        result["launch_explore_seen"] = True
    print(f"\n[driver] sim ready={started} (drained to idle). launch_explore_seen={result['launch_explore_seen']}", flush=True)

    # Turns sync on the stable `grounded)` marker; booleans are parsed post-hoc from
    # the ANSI-stripped raw log (the live `verified=` regex fails because ANSI codes
    # split the `=` from the value).
    if MODE in ("both", "fetch"):
        print("\n[driver] FETCH turn...", flush=True)
        child.sendline(FETCH)
        child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=300)
        _eyes_frame(SNAP, "fetch")
        drain_until_quiet(child, quiet=3.0, max_wait=90)
        print("\n[driver] fetch turn done", flush=True)

    if MODE in ("both", "place"):
        print("\n[driver] PLACE turn...", flush=True)
        child.sendline(PLACE)
        child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=300)
        _eyes_frame(SNAP, "place")
        drain_until_quiet(child, quiet=3.0, max_wait=90)
        print("\n[driver] place turn done", flush=True)

    if MODE == "quantity":
        # Frontier probe (R198/E35): ONE quantity-place utterance, e.g.
        # "把两个瓶子放到架子上" (put two bottles on the shelf). The producer must decompose
        # it into N sequential grasp->place cycles, then verify the QUANTITY with
        # resting_on_receptacle() >= N. That is up to 2N+1 verdicts (grasp+place per object,
        # plus the final count check) — collect them all; the acceptance predicate is the
        # FINAL count verdict (resting_on_receptacle() >= N -> True), read from the moat GT.
        print("\n[driver] QUANTITY turn (single N-object place utterance)...", flush=True)
        child.sendline(FETCH)
        n_verdicts = 0
        if child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=600) == 0:
            n_verdicts += 1
            while n_verdicts < 6:
                idx = child.expect([r"grounded\)", r"vector>", pexpect.TIMEOUT], timeout=600)
                if idx == 0:
                    n_verdicts += 1
                else:
                    break  # prompt returned (turn complete) or timed out
        _eyes_frame(SNAP, "quantity")
        wait_prompt(child, timeout=60)
        print(f"\n[driver] quantity turn done — saw {n_verdicts} verdict(s)", flush=True)

    if MODE == "combo":
        # Frontier probe: ONE multi-clause utterance (fetch AND place in a single
        # command, e.g. "把红色的罐子拿过来放到架子上"). The producer must decompose it
        # into grasp->place; both step verdicts render before the prompt returns. We
        # send FETCH as the whole utterance, wait a long time for the compound plan to
        # finish, then the post-hoc parser below collects EVERY verdict emitted.
        print("\n[driver] COMBO turn (single multi-clause utterance)...", flush=True)
        child.sendline(FETCH)
        # Sync on each `grounded)` verdict, NOT the prompt. wait_prompt matches `vector>`,
        # which the just-ECHOED command line ("vector> 把红色…") matches INSTANTLY — that
        # early-return aborted the turn mid-grasp (both prior combo runs). A compound plan
        # emits one verdict per checked step (grasp, then place), with NO prompt between
        # tool calls. So: wait ONLY for the first (grasp) verdict — do not offer vector>
        # here or the echo matches it — then accept further verdicts until the prompt
        # (turn finished) returns. Grasp+place pipelines are slow (perception+MPC+walk+
        # grasp, then walk+place+12s settle), hence the long per-verdict timeouts.
        n_verdicts = 0
        if child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=480) == 0:
            n_verdicts += 1
            while n_verdicts < 4:
                idx = child.expect([r"grounded\)", r"vector>", pexpect.TIMEOUT], timeout=480)
                if idx == 0:
                    n_verdicts += 1
                else:
                    break  # prompt returned (turn complete) or timed out
        _eyes_frame(SNAP, "combo")
        wait_prompt(child, timeout=60)
        print(f"\n[driver] combo turn done — saw {n_verdicts} verdict(s)", flush=True)

    child.sendline("quit")
    child.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=30)
except Exception as exc:  # noqa: BLE001
    print(f"\n[driver] EXCEPTION: {exc}", flush=True)
finally:
    try:
        child.close(force=True)
    except Exception:
        pass
    subprocess.run(["rosm", "nuke", "--yes"], capture_output=True)

# Parse the two turn verdicts from the ANSI-stripped raw log (fetch then place).
try:
    raw = open(f"{SNAP}/repl.raw.log", encoding="utf-8", errors="replace").read()
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\][0-9;]*|\x1b", "", raw)
    # The braille spinner (U+2800-U+28FF) interleaves INTO the verdict text and breaks
    # the regex (verified⠋=⠙True...); strip the glyphs so the verdict reads cleanly.
    clean = re.sub(r"[⠀-⣿]", "", clean)
    verds = re.findall(r"verified\s*=\s*(True|False)\s*\((\d+)/(\d+)\s*grounded\)", clean)
    # Map emitted verdicts to the turns that ACTUALLY ran (mode-aware). In place-only
    # mode a single verdict is emitted — it is the PLACE verdict, NOT the fetch one
    # (the old positional parse mislabeled it fetch_verified, leaving place_verified=None).
    if MODE == "quantity":
        # A single N-object place utterance emits up to 2N+1 verdicts (grasp+place per
        # object, then the final resting_on_receptacle() >= N count check). The QUANTITY
        # acceptance is the FINAL verdict (the count predicate), read from the moat GT.
        result["quantity_verdicts"] = [f"{v[0]}({v[1]}/{v[2]})" for v in verds]
        result["quantity_final_true"] = bool(verds) and verds[-1][0] == "True"
    elif MODE == "combo":
        # A single compound utterance emits N verdicts (typically grasp then place).
        # Report EVERY verdict verbatim — the frontier claim is "all steps grounded".
        result["combo_verdicts"] = [f"{v[0]}({v[1]}/{v[2]})" for v in verds]
        result["combo_all_true"] = bool(verds) and all(v[0] == "True" for v in verds)
    else:
        # Map emitted verdicts to the turns that ACTUALLY ran (mode-aware). In place-only
        # mode a single verdict is emitted — it is the PLACE verdict, NOT the fetch one
        # (the old positional parse mislabeled it fetch_verified, leaving place_verified=None).
        turns = []
        if MODE in ("both", "fetch"):
            turns.append("fetch")
        if MODE in ("both", "place"):
            turns.append("place")
        for turn, verd in zip(turns, verds):
            result[f"{turn}_verified"] = verd[0] == "True"
            result[f"{turn}_grounded"] = f"{verd[1]}/{verd[2]}"
except Exception as exc:  # noqa: BLE001
    print(f"[driver] verdict parse failed: {exc}", flush=True)

frames = sorted(f for f in os.listdir(SNAP) if f.endswith(".png"))
if MODE == "quantity":
    print(f"\n[RESULT {TAG}] launch_explore_seen={result['launch_explore_seen']} "
          f"quantity_final_true={result.get('quantity_final_true')} "
          f"verdicts={result.get('quantity_verdicts')} frames={frames}", flush=True)
elif MODE == "combo":
    print(f"\n[RESULT {TAG}] launch_explore_seen={result['launch_explore_seen']} "
          f"combo_all_true={result.get('combo_all_true')} "
          f"verdicts={result.get('combo_verdicts')} frames={frames}", flush=True)
else:
    print(f"\n[RESULT {TAG}] launch_explore_seen={result['launch_explore_seen']} "
          f"fetch_verified={result['fetch_verified']} ({result.get('fetch_grounded')}) "
          f"place_verified={result['place_verified']} ({result.get('place_grounded')}) "
          f"frames={frames}", flush=True)
