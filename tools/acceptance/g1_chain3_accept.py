"""g1 THREE-LEG ORCHESTRATION bare-REPL acceptance driver (route · perceive · ACT chain).

Raises the R713/E236 two-leg bar (nav→perceive, GROUNDED 2/2) by CHAINING THREE sub-goals in
ONE natural-language turn — route THEN perceive THEN a terminal ACT leg — each graded by its
OWN independent unforgeable GT oracle:

    导航到坐标(12,3.5)，然后找前面的红色的东西，最后再导航到坐标(9.5,4)
      leg 1 (route)   -> navigate_to((12,3.5)) -> verify at_position(12,3.5)         [go2_sim_oracle GT]
      leg 2 (perceive)-> detect on head cam    -> verify detection_matches_gt('红')  [segmentation GT]
      leg 3 (ACT)     -> navigate_to((9.5,4))  -> verify at_position(9.5,4)          [go2_sim_oracle GT]

Why a 2nd at_position waypoint is the ACT leg (not place / not grasp):
  - g1 declares has_arm:false, so a manipulation terminal (holding_object) is off the table
    on THIS embodiment; the frontier (b) note names an at_position waypoint act as the g1
    option, and place-leg causation was refuted E64 (single-session NOT_GRADED). A 2nd
    coordinate move is a moat-graded terminal predicate the actor cannot author (STEP-15
    coordinate-goal gate forces the commanded coord ASSERTED, not faked with facing()).

Why this is a REAL 3-leg orchestration win, not three stitched turns:
  - ONE utterance; the planner must self-decompose route THEN perceive THEN route.
  - evidence_passed requires ALL checked steps GROUNDED (trace_store), so verified=True is
    only reachable if ALL THREE legs ground in the SAME trace -> `(3/3 grounded)`.
  - leg 1 and leg 3 are DISTINCT coordinates (12,3.5) vs (9.5,4): a 2.55 m back-hop, a real
    >=2 m coordinate move that must settle within the DEFAULT 0.5 m tol (actor=CAUSED, not the
    E235 no-op-retry that grades UNCAUSED). Both coords are confirmed g1.navigation targets
    (R291 12,3.5 ; R710 9.5,4).
  - NO spine edit: VerdictReport.from_trace already grades per-sub-goal against the live verify
    namespace; this only exercises a 3-sub-goal tree the moat already composes.

Geometry (hardware/sim/mujoco_g1.py): g1 spawns (10,3) facing +x; red panel ~(12.9,3.35).
leg1 (12,3.5) keeps red ~0.9 m dead-ahead (perceive GT stays in head-cam); leg3 (9.5,4) is a
turn-around back-hop over open floor (red may leave view — irrelevant, perceive already
grounded).

Mirrors g1_chain_accept.py's proven PTY plumbing; the ONLY acceptance face (bare vector-cli
REPL + NL, no -p / no --sim flag). Reads per-step `verify <expr> ok (actor=...)` lines + the
turn `verdict <EV> verified=<bool> (n/m grounded)` as the moat-oracle GT.

Usage: python g1_chain3_accept.py [chain_nl] [tag]
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

import pexpect

ROOT = "/home/yusen/Desktop/vector_os_nano"
CHAIN = sys.argv[1] if len(sys.argv) > 1 else "导航到坐标(12,3.5)，然后找前面的红色的东西，最后再导航到坐标(9.5,4)"
TAG = sys.argv[2] if len(sys.argv) > 2 else "g1chain3"
SNAP = f"/tmp/g1_chain3_accept/{TAG}"
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


def parse_verdicts(snap: str) -> list[tuple[str, bool, int, int]]:
    """Parse every `verdict <EV> verified=<bool> (n/m grounded)` — the moat-oracle GT per turn."""
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
    """Parse every per-step `verify <expr> <mark> (actor=...)` line. Proves WHICH oracle each leg used."""
    clean = _clean_log(snap)
    out: list[tuple[str, bool]] = []
    for m in re.finditer(r"verify\s+(.+?)\s+([✓·])\s*\(actor=", clean):
        out.append((m.group(1).strip(), m.group(2) == "✓"))
    return out


_llm_preflight()
print(f"[driver] spawning BARE vector-cli REPL (no -p/--sim); CHAIN={CHAIN!r} provider={PROVIDER}", flush=True)
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
    drain_until_quiet(child, quiet=3.0, max_wait=120)
    if launch_explore_running():
        result["launch_explore_seen"] = True
        print("\n[driver] !!! launch_explore RUNNING — NOT in-process (unexpected for g1)", flush=True)
    print(f"\n[driver] g1 sim ready. launch_explore_seen={result['launch_explore_seen']}", flush=True)

    # THE CHAINED TURN — one NL utterance, expect a 3-sub-goal trace: nav THEN perceive THEN nav.
    # Two route legs walk the gait, so allow a generous per-turn budget.
    print("\n[driver] CHAINED 3-leg orchestration turn (route THEN perceive THEN route)...", flush=True)
    child.sendline(CHAIN)
    child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=600)
    _eyes_frame(SNAP, "chain3")
    drain_until_quiet(child, quiet=3.0, max_wait=150)
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

# 3-leg orchestration acceptance: ONE chained turn, verified=True, n_grounded>=3, and ALL THREE
# oracle legs consumed with a ✓ — TWO DISTINCT at_position(...) route/act legs AND a
# detection_matches_gt(...) perceive leg. Distinct coords prove leg1 != leg3 (a real move, not
# the same waypoint scored twice).
grounded_navs = sorted({v for v, ok in steps if "at_position" in v and ok})
has_perc = any("detection_matches_gt" in v and ok for v, ok in steps)
chain_ok = (
    bool(verdicts) and verdicts[0][1] and verdicts[0][2] >= 3
    and len(grounded_navs) >= 2 and has_perc
)
print(f"[driver] distinct at_position legs grounded ({len(grounded_navs)}) = {grounded_navs}", flush=True)
print(f"[driver] detection_matches_gt leg grounded = {has_perc}", flush=True)
print(f"[driver] CHAIN3 GROUNDED (3-leg orchestration) = {chain_ok}", flush=True)
print(f"[driver] eyes: {SNAP}/eyes_chain3.png", flush=True)
print("=" * 64, flush=True)
