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

    # ---- FETCH ----
    print("\n[driver] FETCH turn...", flush=True)
    child.sendline(FETCH)
    idx = child.expect([r"verified=(True|False)", pexpect.TIMEOUT], timeout=300)
    if idx == 0:
        result["fetch_verified"] = child.match.group(1) == "True"
    wait_prompt(child, timeout=60)
    print(f"\n[driver] fetch_verified={result['fetch_verified']}", flush=True)

    # ---- PLACE ----
    print("\n[driver] PLACE turn...", flush=True)
    child.sendline(PLACE)
    idx = child.expect([r"verified=(True|False)", pexpect.TIMEOUT], timeout=300)
    if idx == 0:
        result["place_verified"] = child.match.group(1) == "True"
    wait_prompt(child, timeout=60)
    print(f"\n[driver] place_verified={result['place_verified']}", flush=True)

    # Screenshot the viewer window (best-effort) while it is still up.
    os.system(f"scrot -o {SNAP}/window.png 2>/dev/null || import -window root {SNAP}/window.png 2>/dev/null || true")

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

frames = sorted(f for f in os.listdir(SNAP) if f.endswith(".png"))
print(f"\n[RESULT {TAG}] launch_explore_seen={result['launch_explore_seen']} "
      f"fetch_verified={result['fetch_verified']} place_verified={result['place_verified']} "
      f"frames={frames}", flush=True)
