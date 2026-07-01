"""D163 bare-REPL acceptance driver.

Drives the ACTUAL bare `vector-cli` REPL under a PTY (NO -p, NO --sim-go2 flag)
with natural-language commands, exactly as a user would:

    启动带手臂的 go2 仿真   -> SimStartTool._start_go2 (VECTOR_NO_ROS2=1 -> in-process)
    <fetch NL>            -> native producer, renders `verdict ... verified=...`
    <place NL>            -> native producer, renders `verdict ... verified=...`

Proves the D163 fix: launch_explore.sh must be EMPTY throughout (in-process path).
Captures verdict frames via VECTOR_SNAPSHOT_DIR + a viewer window screenshot for
the Qwen3-VL eyes. Reads the console `verified=True/False` as the moat-oracle GT.

Usage: python repl_accept.py <fetch_nl> <place_nl> <tag>
Env must carry QWEN_API_KEY etc. (the loop env). Runs ONE sim, one colour.
"""
from __future__ import annotations

import os
import re
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


def _grab_sim_window(snap: str, tag: str) -> None:
    """Screenshot the ACTUAL MuJoCo viewer window (not the whole desktop).

    The passive viewer titles its window "MuJoCo : <model>". Find its X id via
    xdotool and grab just that window; fall back to a root scrot only if the
    lookup fails (a desktop capture is NOT eyes-on-sim, so we prefer the window).
    """
    out = f"{snap}/sim_{tag}.png"
    # ImageMagick `import -window <name>` grabs a window by NAME (no xdotool needed).
    # The passive viewer's window name contains "MuJoCo".
    r = subprocess.run(["import", "-window", "MuJoCo", out], capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
        print(f"[driver] grabbed MuJoCo window -> {out}", flush=True)
        return
    subprocess.run(["import", "-window", "root", f"{snap}/desktop_{tag}.png"], capture_output=True)
    print(f"[driver] MuJoCo window grab failed ({r.stderr.strip()[:60]}); desktop fallback", flush=True)


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
        _grab_sim_window(SNAP, "fetch")
        wait_prompt(child, timeout=60)
        print("\n[driver] fetch turn done", flush=True)

    if MODE in ("both", "place"):
        print("\n[driver] PLACE turn...", flush=True)
        child.sendline(PLACE)
        child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=300)
        _grab_sim_window(SNAP, "place")
        wait_prompt(child, timeout=60)
        print("\n[driver] place turn done", flush=True)

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
    verds = re.findall(r"verified\s*=\s*(True|False)\s*\((\d+)/(\d+)\s*grounded\)", clean)
    if len(verds) >= 1:
        result["fetch_verified"] = verds[0][0] == "True"
        result["fetch_grounded"] = f"{verds[0][1]}/{verds[0][2]}"
    if len(verds) >= 2:
        result["place_verified"] = verds[1][0] == "True"
        result["place_grounded"] = f"{verds[1][1]}/{verds[1][2]}"
except Exception as exc:  # noqa: BLE001
    print(f"[driver] verdict parse failed: {exc}", flush=True)

frames = sorted(f for f in os.listdir(SNAP) if f.endswith(".png"))
print(f"\n[RESULT {TAG}] launch_explore_seen={result['launch_explore_seen']} "
      f"fetch_verified={result['fetch_verified']} ({result.get('fetch_grounded')}) "
      f"place_verified={result['place_verified']} ({result.get('place_grounded')}) "
      f"frames={frames}", flush=True)
