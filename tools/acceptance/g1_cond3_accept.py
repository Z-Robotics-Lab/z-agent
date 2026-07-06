"""g1 DATA-DEPENDENT CONDITIONAL bare-REPL acceptance driver (route · perceive · BRANCH chain).

Raises the R714/E237 THREE-leg sequential bar (route→perceive→ACT, GROUNDED 3/3) by making the
terminal leg's TARGET be CHOSEN by a PRIOR leg's runtime result — the real orchestration test
PAST mere sequencing (frontier d). ONE natural-language turn:

    导航到坐标(12,3.5)，看看前面有没有红色的东西；
    如果没有红色物体就导航到坐标(8,3)，如果看到了红色物体就导航到坐标(9.5,4)
      leg 1 (route)   -> navigate_to((12,3.5)) -> verify at_position(12,3.5)         [go2_sim_oracle GT]
      leg 2 (perceive)-> detect on head cam    -> verify detection_matches_gt('红')  [segmentation GT]
      leg 3 (BRANCH)  -> IF red seen: navigate_to((9.5,4)) ELSE navigate_to((8,3))
                         -> verify at_position(<chosen>)                             [go2_sim_oracle GT]

Why this is DATA-DEPENDENT, not the E237 fixed sequence:
  - leg 3's commanded coordinate is NOT in the utterance as a single target — it is a FUNCTION
    of leg 2's detection RESULT. The planner must READ leg2's runtime outcome and pick a branch.
  - The GROUND TRUTH is: red IS present at leg1's pose (12,3.5) (red panel ~(12.9,3.35), dead
    ahead, R291/R714). So the CORRECT branch is (9.5,4); the WRONG branch is (8,3).

Why the "always take the first-listed branch" confound is DEFEATED:
  - The CORRECT branch (red seen -> (9.5,4)) is listed SECOND in the NL. A planner that ignores
    the detection and blindly takes the first branch would navigate to (8,3) and
    at_position(9.5,4) would NEVER ground. So a GROUNDED at_position(9.5,4) — AND the ABSENCE of
    a grounded at_position(8,3) — proves the planner evaluated the condition against leg2's
    actual detection outcome. That is the data-dependency, unforgeable by the actor.

Acceptance (cond3_ok) — ALL of:
  - the turn verdict is verified=True with n_grounded >= 3 (moat composed all sub-goals same-trace);
  - at_position(12.0, 3.5) grounded  (leg1 route);
  - detection_matches_gt('...') grounded  (leg2 perceive, seg-GT);
  - at_position(9.5, 4.0) grounded  (leg3 CORRECT red-seen branch, a >=2 m move => actor=CAUSED);
  - at_position(8.0, 3.0) NOT grounded  (the WRONG no-red branch was NOT taken).

NO spine edit: VerdictReport.from_trace already grades per-sub-goal against the live verify
namespace; at_position + detection_matches_gt already grade every leg. This only exercises a
data-dependent sub-goal tree the moat already composes. The ONLY acceptance face is the bare
vector-cli REPL + NL (no -p / no --sim). Mirrors g1_chain3_accept.py's PTY plumbing.

Usage: python g1_cond3_accept.py [chain_nl] [tag]
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

import pexpect

ROOT = "/home/yusen/Desktop/vector_os_nano"
CHAIN = sys.argv[1] if len(sys.argv) > 1 else (
    "导航到坐标(12,3.5)，看看前面有没有红色的东西；"
    "如果没有红色物体就导航到坐标(8,3)，如果看到了红色物体就导航到坐标(9.5,4)"
)
TAG = sys.argv[2] if len(sys.argv) > 2 else "g1cond3"
SNAP = f"/tmp/g1_cond3_accept/{TAG}"
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


def _has_at_position(steps, x: float, y: float) -> bool:
    """True iff a GROUNDED at_position(x, y[, ...]) step verify appears (coord within 0.05 m)."""
    pat = re.compile(r"at_position\(\s*([\-0-9.]+)\s*,\s*([\-0-9.]+)")
    for expr, ok in steps:
        if not ok:
            continue
        m = pat.search(expr)
        if m and abs(float(m.group(1)) - x) < 0.05 and abs(float(m.group(2)) - y) < 0.05:
            return True
    return False


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

    # THE CONDITIONAL TURN — one NL utterance; expect route -> perceive -> BRANCH-on-detection.
    print("\n[driver] DATA-DEPENDENT conditional turn (route THEN perceive THEN branch)...", flush=True)
    child.sendline(CHAIN)
    child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=600)
    _eyes_frame(SNAP, "cond3")
    drain_until_quiet(child, quiet=3.0, max_wait=150)
    print("\n[driver] conditional turn done", flush=True)

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

# Data-dependent conditional acceptance: ONE chained turn, verified=True, n_grounded>=3, with
# leg1 (12,3.5) route + perceive leg grounded + the CORRECT red-seen branch (9.5,4) grounded AND
# the WRONG no-red branch (8,3) NOT grounded — proving leg3 was CHOSEN by leg2's detection.
leg1_ok = _has_at_position(steps, 12.0, 3.5)
correct_branch = _has_at_position(steps, 9.5, 4.0)   # red WAS seen -> (9.5,4)
wrong_branch = _has_at_position(steps, 8.0, 3.0)     # would mean detection ignored
has_perc = any("detection_matches_gt" in v and ok for v, ok in steps)
cond3_ok = (
    bool(verdicts) and verdicts[0][1] and verdicts[0][2] >= 3
    and leg1_ok and has_perc and correct_branch and not wrong_branch
)
print(f"[driver] leg1 at_position(12,3.5) grounded = {leg1_ok}", flush=True)
print(f"[driver] detection_matches_gt leg grounded = {has_perc}", flush=True)
print(f"[driver] CORRECT branch at_position(9.5,4) grounded = {correct_branch}", flush=True)
print(f"[driver] WRONG branch at_position(8,3) grounded (must be False) = {wrong_branch}", flush=True)
print(f"[driver] COND3 DATA-DEPENDENT GROUNDED = {cond3_ok}", flush=True)
print(f"[driver] eyes: {SNAP}/eyes_cond3.png", flush=True)
print("=" * 64, flush=True)
