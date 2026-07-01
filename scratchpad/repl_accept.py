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

Usage: python repl_accept.py <fetch_nl> <place_nl> <tag>
Env must carry QWEN_API_KEY etc. (the loop env). Runs ONE sim, one colour.
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
SNAP = f"/tmp/repl_accept/{TAG}"
os.system(f"rm -rf {SNAP}; mkdir -p {SNAP}")

env = dict(os.environ)
env.update({
    "PATH": "/usr/bin:" + os.environ.get("PATH", ""),
    "VECTOR_PROVIDER": "qwen",
    "QWEN_MODEL": os.environ.get("QWEN_MODEL", "qwen-max"),
    "VECTOR_MAX_TOKENS": "8000",
    "VECTOR_JUDGE_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "VECTOR_JUDGE_MODEL": "qwen3-vl-plus",
    "VECTOR_JUDGE_API_KEY": os.environ.get("QWEN_API_KEY", ""),
    "VECTOR_SIM_WITH_ARM": "1",
    "VECTOR_NO_ROS2": "1",
    "MUJOCO_GL": "egl",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "VECTOR_SNAPSHOT_DIR": SNAP,
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
    """Fail FAST if the DashScope/Qwen account is unusable (arrears / access denied), instead of
    spawning the sim and burning an 8-min per-verdict timeout against a dead LLM (the whole
    acceptance face — planner qwen-max AND eyes qwen3-vl — routes through this one key). A 400
    'Arrearage'/'Access denied' means BILLING is down: a Yusen-only fix, not a code fault.
    """
    import json as _json
    import urllib.error
    import urllib.request
    key = os.environ.get("QWEN_API_KEY", "")
    if not key:
        print("[driver] PREFLIGHT: no QWEN_API_KEY in env — cannot run the acceptance face.", flush=True)
        sys.exit(3)
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=_json.dumps({"model": os.environ.get("QWEN_MODEL", "qwen-max"),
                          "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
        print("[driver] PREFLIGHT: DashScope LLM reachable.", flush=True)
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode(errors="replace")
        if "Arrearage" in body or "Access denied" in body or "overdue" in body:
            print(f"[driver] PREFLIGHT BLOCKED: DashScope account in ARREARS/denied ({e.code}). "
                  f"Acceptance face is DOWN until billing is restored (Yusen-only). Body: {body}", flush=True)
            sys.exit(4)
        print(f"[driver] PREFLIGHT: DashScope HTTP {e.code} (non-arrears): {body} — proceeding.", flush=True)
    except Exception as e:  # noqa: BLE001 — network flake shouldn't hard-block; let the run try
        print(f"[driver] PREFLIGHT: probe error {type(e).__name__}: {e} — proceeding.", flush=True)


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
    child.sendline("启动带手臂的 go2 仿真")
    # Sim build: MuJoCoGo2 connect + arm + perception + scene graph. Wait for prompt.
    time.sleep(8)
    if launch_explore_running():
        result["launch_explore_seen"] = True
        print("\n[driver] !!! launch_explore RUNNING — ROS2 stack path took (FIX FAILED)", flush=True)
    wait_prompt(child, timeout=120)
    # Double-check after ready.
    if launch_explore_running():
        result["launch_explore_seen"] = True
    print(f"\n[driver] sim ready. launch_explore_seen={result['launch_explore_seen']}", flush=True)

    # Turns sync on the stable `grounded)` marker; booleans are parsed post-hoc from
    # the ANSI-stripped raw log (the live `verified=` regex fails because ANSI codes
    # split the `=` from the value).
    if MODE in ("both", "fetch"):
        print("\n[driver] FETCH turn...", flush=True)
        child.sendline(FETCH)
        child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=300)
        _eyes_frame(SNAP, "fetch")
        wait_prompt(child, timeout=60)
        print("\n[driver] fetch turn done", flush=True)

    if MODE in ("both", "place"):
        print("\n[driver] PLACE turn...", flush=True)
        child.sendline(PLACE)
        child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=300)
        _eyes_frame(SNAP, "place")
        wait_prompt(child, timeout=60)
        print("\n[driver] place turn done", flush=True)

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
    if MODE == "combo":
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
if MODE == "combo":
    print(f"\n[RESULT {TAG}] launch_explore_seen={result['launch_explore_seen']} "
          f"combo_all_true={result.get('combo_all_true')} "
          f"verdicts={result.get('combo_verdicts')} frames={frames}", flush=True)
else:
    print(f"\n[RESULT {TAG}] launch_explore_seen={result['launch_explore_seen']} "
          f"fetch_verified={result['fetch_verified']} ({result.get('fetch_grounded')}) "
          f"place_verified={result['place_verified']} ({result.get('place_grounded')}) "
          f"frames={frames}", flush=True)
