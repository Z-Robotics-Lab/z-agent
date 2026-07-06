"""g1 TWO-LEG ORCHESTRATION bare-REPL acceptance driver (plan · route · verify chain).

Climbs off the single-leg g1 bars (g1.navigation = at_position, g1.perception =
detection_matches_gt) by CHAINING them in ONE natural-language turn whose goal-tree
carries TWO sub-goals, each graded by its OWN independent unforgeable GT oracle:

    导航到坐标(11,3)，然后找前面的红色的东西
      leg 1 (route)   -> navigate_to((11,3))  -> verify at_position(11,3)         [go2_sim_oracle GT]
      leg 2 (perceive)-> detect on head cam   -> verify detection_matches_gt('红') [segmentation GT]

Why this is a REAL orchestration win, not two stitched turns:
  - ONE utterance; the planner must self-decompose route THEN perceive.
  - evidence_passed requires ALL checked steps GROUNDED (trace_store), so verified=True
    is only reachable if BOTH the coordinate move AND the perception match ground in the
    SAME trace -> `(2/2 grounded)`.
  - Both oracles are actor-uncopyable: at_position reads the live base pose (STEP-15
    coordinate-goal gate forces the commanded coord to be ASSERTED, not faked with
    facing()); detection_matches_gt reads a MuJoCo SEGMENTATION render the detector never
    sees. Neither leg can be laundered past the moat by the LLM.
  - NO spine edit: VerdictReport.from_trace already grades per-sub-goal against the live
    verify namespace; this only exercises a 2-sub-goal tree the moat already composes.

Geometry (mujoco_g1.py): g1 spawns at (10,3) facing +x; the red panel is dead-ahead at
~(12.9,3.35). Navigating forward to (11,3) is a real >=0.7 m coordinate move that keeps the
red panel in the head-cam view, so the perceive leg still has its GT in frame after routing.

Mirrors g1_accept.py's proven PTY plumbing; the ONLY acceptance face (bare vector-cli REPL +
NL, no -p / no --sim flag). Reads the per-step `verify <expr> ok (actor=...)` lines + the
turn `verdict <EV> verified=<bool> (n/m grounded)` as the moat-oracle GT.

Usage: python g1_chain_accept.py [chain_nl] [tag]
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

import pexpect

ROOT = "/home/yusen/Desktop/zeno"
CHAIN = sys.argv[1] if len(sys.argv) > 1 else "导航到坐标(11,3)，然后找前面的红色的东西"
TAG = sys.argv[2] if len(sys.argv) > 2 else "g1chain"
SNAP = f"/tmp/g1_chain_accept/{TAG}"
os.system(f"rm -rf {SNAP}; mkdir -p {SNAP}")

PROVIDER = os.environ.get("VECTOR_PROVIDER", "deepseek").lower()
_PLANNER = {
    "qwen": {"QWEN_MODEL": os.environ.get("QWEN_MODEL", "qwen-max")},
    "deepseek": {"DEEPSEEK_MODEL": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")},
    "openrouter": {"VECTOR_MODEL": os.environ.get("VECTOR_MODEL", "openai/gpt-4o-mini")},
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
env.pop("DISPLAY", None)
env.pop("WAYLAND_DISPLAY", None)

G1_START_MARKER = "sim start g1 ok"


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
        from zeno.vcli.config import resolve_credentials  # noqa: PLC0415
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


def parse_verdicts(snap: str) -> list[tuple[str, bool, int, int]]:
    """Parse every `verdict <EV> verified=<bool> (n/m grounded)` from the clean log.

    Returns [(evidence, verified, n_grounded, n_steps), ...] in turn order — the
    moat-oracle GT for each turn.
    """
    clean = _clean_log(snap)
    out: list[tuple[str, bool, int, int]] = []
    pat = re.compile(
        r"verdict\s+(GROUNDED|RAN|FAILED|NO_TRACE)\s+verified=(True|False)\s*"
        r"\((\d+)/(\d+)\s*grounded\)"
    )
    for m in pat.finditer(clean):
        out.append((m.group(1), m.group(2) == "True", int(m.group(3)), int(m.group(4))))
    return out


def parse_step_verifies(snap: str) -> list[tuple[str, bool]]:
    """Parse every per-step `verify <expr> <mark> (actor=...)` line from the clean log.

    Returns [(verify_expr, grounded_check_ok), ...]. The mark is the unicode ✓ (ok) or
    · (not ok). Proves WHICH oracle each leg consumed (at_position vs detection_matches_gt).
    """
    clean = _clean_log(snap)
    out: list[tuple[str, bool]] = []
    for m in re.finditer(r"verify\s+(.+?)\s+([✓·])\s*\(actor=", clean):
        out.append((m.group(1).strip(), m.group(2) == "✓"))
    return out


_llm_preflight()
print(f"[driver] spawning BARE vector-cli REPL (no -p/--sim); CHAIN={CHAIN!r} provider={PROVIDER}", flush=True)
child = pexpect.spawn(
    f"{ROOT}/.venv/bin/python", ["-m", "zeno.vcli.cli", "--native-loop"],
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
    drain_until_quiet(child, quiet=3.0, max_wait=120)
    if launch_explore_running():
        result["launch_explore_seen"] = True
        print("\n[driver] !!! launch_explore RUNNING — NOT in-process (unexpected for g1)", flush=True)
    print(f"\n[driver] g1 sim ready. launch_explore_seen={result['launch_explore_seen']}", flush=True)

    # THE CHAINED TURN — one NL utterance, expect a 2-sub-goal trace: nav THEN perceive.
    # A route leg can take longer than a bare detect, so allow a generous per-turn budget.
    print("\n[driver] CHAINED orchestration turn (route THEN perceive)...", flush=True)
    child.sendline(CHAIN)
    child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=420)
    _eyes_frame(SNAP, "chain")
    drain_until_quiet(child, quiet=3.0, max_wait=120)
    print("\n[driver] chained turn done", flush=True)

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
steps = parse_step_verifies(SNAP)
print("\n" + "=" * 64, flush=True)
print(f"[driver] provider={PROVIDER}  launch_explore_seen={result['launch_explore_seen']}", flush=True)
print(f"[driver] step verifies (in order) = {steps}", flush=True)
print(f"[driver] turn verdicts (ev, verified, n_grounded, n_steps) = {verdicts}", flush=True)

# Orchestration acceptance: ONE chained turn, verified=True, n_grounded>=2, and BOTH oracles
# consumed with a ✓ leg — an at_position(...) route leg AND a detection_matches_gt(...) perceive leg.
has_nav = any("at_position" in v and ok for v, ok in steps)
has_perc = any("detection_matches_gt" in v and ok for v, ok in steps)
chain_ok = bool(verdicts) and verdicts[0][1] and verdicts[0][2] >= 2 and has_nav and has_perc
print(f"[driver] at_position leg grounded = {has_nav}", flush=True)
print(f"[driver] detection_matches_gt leg grounded = {has_perc}", flush=True)
print(f"[driver] CHAIN GROUNDED (2-leg orchestration) = {chain_ok}", flush=True)
print(f"[driver] eyes: {SNAP}/eyes_chain.png", flush=True)
print("=" * 64, flush=True)
