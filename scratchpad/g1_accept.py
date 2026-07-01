"""g1 cross-embodiment × cross-model bare-REPL acceptance driver.

Proves TWO plug-and-play axes AT ONCE on the ONLY acceptance face (bare `vector-cli`
REPL + NL, no -p / no --sim flag):
  - bring-your-own-ROBOT: g1 (Unitree humanoid, 2nd embodiment, camera-only, NO arm)
    started BY NL in the go2 apartment room.
  - bring-your-own-MODEL: VECTOR_PROVIDER selects the routing brain (deepseek when qwen
    is in arrears) — the SAME bare REPL, a non-qwen planner.

The honest GROUNDED for g1 (no arm → no weld-causation) is a GT-BACKED PERCEPTION MATCH
(vcli/worlds/g1_perception_oracle.detection_matches_gt): the learned grounding-dino box on
g1's HEAD camera (the CLAIM, RGB-only firewall) must land within tol px of the MuJoCo
SEGMENTATION centroid of the matching-colour geoms (INDEPENDENT sim GT the detector cannot
author). RED is in g1's spawn view → GROUNDED; the MANDATORY REFUTATION GREEN is NOT in view
→ RAN (a trivial oracle would ground both). This is D63's honest oracle, re-run on the
current D172-fixed harness via a non-qwen brain.

Flow (mirrors repl_accept.py's proven PTY plumbing; go2 fetch/place → g1 detect/refute):
    启动 g1 仿真          -> SimStartTool._start_g1 (VECTOR_NO_ROS2=1 -> in-process MuJoCoG1)
    找前面的红色的东西     -> native detect on g1 head cam -> verify detection_matches_gt('红') -> GROUNDED
    找前面的绿色的东西     -> refutation (green not in view) -> RAN verified=False

launch_explore.sh must be EMPTY throughout (g1 is inherently in-process; the check guards it).
Reads the ANSI-stripped `verdict <EV> verified=<bool>` line as the moat-oracle GT; copies the
offscreen verdict_*.png to eyes_<tag>.png for the eyes second-witness.

Usage: python g1_accept.py [red_nl] [green_nl] [tag]
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

import pexpect

ROOT = "/home/yusen/Desktop/vector_os_nano"
RED = sys.argv[1] if len(sys.argv) > 1 else "找前面的红色的东西"
GREEN = sys.argv[2] if len(sys.argv) > 2 else "找前面的绿色的东西"
TAG = sys.argv[3] if len(sys.argv) > 3 else "g1r"
SNAP = f"/tmp/g1_accept/{TAG}"
os.system(f"rm -rf {SNAP}; mkdir -p {SNAP}")

# Plug-and-play MODEL seam: VECTOR_PROVIDER selects the routing brain; vcli.config resolves
# the key from .env. Default deepseek (qwen is in arrears 2026-07-01); a caller may override.
PROVIDER = os.environ.get("VECTOR_PROVIDER", "deepseek").lower()
_PLANNER = {
    "qwen": {"QWEN_MODEL": os.environ.get("QWEN_MODEL", "qwen-max")},
    "deepseek": {"DEEPSEEK_MODEL": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")},
    "openrouter": {"VECTOR_MODEL": os.environ.get("VECTOR_MODEL", "anthropic/claude-3.5-sonnet")},
}.get(PROVIDER, {})

env = dict(os.environ)
env.update({
    "PATH": "/usr/bin:" + os.environ.get("PATH", ""),
    "VECTOR_PROVIDER": PROVIDER,
    "VECTOR_MAX_TOKENS": os.environ.get("VECTOR_MAX_TOKENS", "8000"),
    "VECTOR_NO_ROS2": "1",
    "MUJOCO_GL": "egl",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "VECTOR_SNAPSHOT_DIR": SNAP,
    **_PLANNER,
})
# HEADLESS: drop the display so reconcile_render_backend keeps egl offscreen (reliable
# perception + offscreen verdict snapshot; no fragile desktop grab). Same as repl_accept.
env.pop("DISPLAY", None)
env.pop("WAYLAND_DISPLAY", None)

# g1 sim-start GT marker: the SimStartTool result content `Started g1 simulation: ...`
# (sim_tool.execute line ~282). Ground truth (tool completion), never the model's chat claim.
G1_START_MARKER = "Started g1 simulation"


def launch_explore_running() -> bool:
    r = subprocess.run(["pgrep", "-af", r"launch_explore\.sh"], capture_output=True, text=True)
    hits = [ln for ln in r.stdout.splitlines() if "claude" not in ln and ln.strip()]
    return bool(hits)


def wait_prompt(child, timeout=90):
    child.expect(r"vector>", timeout=timeout)


def drain_until_quiet(child, quiet=3.0, max_wait=180):
    waited = 0.0
    while waited < max_wait:
        try:
            child.expect(r".+", timeout=quiet)
            waited = 0.0
        except pexpect.TIMEOUT:
            return True
        except pexpect.EOF:
            return False
        waited += quiet
    return False


def _clean_log(snap: str) -> str:
    try:
        raw = open(f"{snap}/repl.raw.log", encoding="utf-8", errors="replace").read()
    except OSError:
        return ""
    clean = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][0-9;]*|\x1b", "", raw)
    return re.sub(r"[⠀-⣿]", "", clean)


def _eyes_frame(snap: str, tag: str) -> None:
    out = f"{snap}/eyes_{tag}.png"
    verdicts = sorted(
        (f for f in os.listdir(snap) if f.startswith("verdict_") and f.endswith(".png")),
        key=lambda f: os.path.getmtime(os.path.join(snap, f)),
    )
    if verdicts:
        shutil.copyfile(os.path.join(snap, verdicts[-1]), out)
        print(f"[driver] eyes frame -> {out}", flush=True)
    else:
        print("[driver] no verdict_*.png emitted", flush=True)


def _llm_preflight() -> None:
    sys.path.insert(0, ROOT)
    try:
        from vector_os_nano.vcli.config import resolve_credentials  # noqa: PLC0415
        key, provider, model, base_url = resolve_credentials()
    except Exception as e:  # noqa: BLE001
        print(f"[driver] PREFLIGHT: resolve_credentials failed ({e}); proceeding blind.", flush=True)
        return
    if not key:
        print(f"[driver] PREFLIGHT: no API key for provider={provider} — cannot run.", flush=True)
        sys.exit(3)
    try:
        from openai import OpenAI  # noqa: PLC0415
        c = OpenAI(api_key=key, base_url=base_url or None)
        c.chat.completions.create(model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=1)
        print(f"[driver] PREFLIGHT: planner reachable (provider={provider} model={model}).", flush=True)
    except Exception as e:  # noqa: BLE001
        body = str(e); low = body.lower()
        if any(w in low for w in ("arrearage", "access denied", "overdue", "insufficient")):
            print(f"[driver] PREFLIGHT BLOCKED: provider={provider} unusable (billing). {body[:200]}", flush=True)
            sys.exit(4)
        print(f"[driver] PREFLIGHT: probe error {type(e).__name__}: {body[:200]} — proceeding.", flush=True)


def parse_verdicts(snap: str) -> list[tuple[str, bool]]:
    """Post-hoc parse every `verdict <EV> verified=<bool>` from the ANSI-stripped log.

    Live regex on the raw PTY stream misses because ANSI codes split `verified` from `=`.
    Returns [(evidence, verified), ...] in order — the moat-oracle GT for each turn.
    """
    clean = _clean_log(snap)
    out: list[tuple[str, bool]] = []
    for m in re.finditer(r"verdict\s+(GROUNDED|RAN|FAILED|NO_TRACE)\s+verified=(True|False)", clean):
        out.append((m.group(1), m.group(2) == "True"))
    return out


_llm_preflight()
print(f"[driver] spawning BARE vector-cli REPL (no -p/--sim); RED={RED!r} GREEN={GREEN!r} provider={PROVIDER}", flush=True)
child = pexpect.spawn(
    f"{ROOT}/.venv/bin/python", ["-m", "vector_os_nano.vcli.cli", "--native-loop"],
    env=env, cwd=ROOT, encoding="utf-8", codec_errors="replace",
    timeout=120, dimensions=(50, 200),
)
child.logfile_read = open(f"{SNAP}/repl.raw.log", "w")
result = {"launch_explore_seen": False}

try:
    wait_prompt(child, timeout=60)
    print("\n[driver] REPL up. Starting g1 sim by NL...", flush=True)
    started = False
    for attempt in range(4):
        msg = ("启动 g1 仿真，现在就开始，直接执行不用问我" if attempt == 0
               else "是的，现在就启动 g1 humanoid 仿真，直接执行不用再问")
        child.sendline(msg)
        drain_until_quiet(child, quiet=4.0, max_wait=150)
        if G1_START_MARKER in _clean_log(SNAP):
            started = True
            break
        print(f"\n[driver] g1 sim not started on attempt {attempt} (model chatted/asked); re-issuing", flush=True)
    if not started:
        print("\n[driver] g1 SIM NEVER STARTED via NL after retries — aborting (no fake verdict)", flush=True)
        raise SystemExit("g1-sim-never-started")
    if launch_explore_running():
        result["launch_explore_seen"] = True
        print("\n[driver] !!! launch_explore RUNNING — NOT in-process (unexpected for g1)", flush=True)
    drain_until_quiet(child, quiet=3.0, max_wait=120)
    if launch_explore_running():
        result["launch_explore_seen"] = True
    print(f"\n[driver] g1 sim ready. launch_explore_seen={result['launch_explore_seen']}", flush=True)

    # RED turn — expect GROUNDED (red in g1's spawn view; segmentation GT + detector box match).
    print("\n[driver] RED detect turn...", flush=True)
    child.sendline(RED)
    child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=300)
    _eyes_frame(SNAP, "red")
    drain_until_quiet(child, quiet=3.0, max_wait=90)
    print("\n[driver] red turn done", flush=True)

    # GREEN turn — MANDATORY REFUTATION: green NOT in view -> no match -> RAN verified=False.
    print("\n[driver] GREEN refutation turn...", flush=True)
    child.sendline(GREEN)
    # RAN verdicts also render `(n/m grounded)`, so `grounded)` still syncs the turn end.
    child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=300)
    _eyes_frame(SNAP, "green")
    drain_until_quiet(child, quiet=3.0, max_wait=90)
    print("\n[driver] green turn done", flush=True)

    child.sendline("quit")
    child.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=30)
except Exception as exc:  # noqa: BLE001
    print(f"\n[driver] EXCEPTION: {exc}", flush=True)
finally:
    try:
        child.close(force=True)
    except Exception:  # noqa: BLE001
        pass

verdicts = parse_verdicts(SNAP)
print("\n" + "=" * 64, flush=True)
print(f"[driver] provider={PROVIDER}  launch_explore_seen={result['launch_explore_seen']}", flush=True)
print(f"[driver] verdicts (in order) = {verdicts}", flush=True)
# Expected: verdict[0] = ('GROUNDED', True) for RED; verdict[1] = ('RAN', False) for GREEN.
if len(verdicts) >= 1:
    ev, ok = verdicts[0]
    print(f"[driver] RED   -> {ev} verified={ok}   (expect GROUNDED True)", flush=True)
if len(verdicts) >= 2:
    ev, ok = verdicts[1]
    print(f"[driver] GREEN -> {ev} verified={ok}   (expect RAN False = honest refutation)", flush=True)
print(f"[driver] eyes: {SNAP}/eyes_red.png , {SNAP}/eyes_green.png", flush=True)
print("=" * 64, flush=True)
