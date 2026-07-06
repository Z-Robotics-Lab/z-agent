"""g1 2nd-embodiment GROUNDED-NAV bare-REPL acceptance (KIND escalation past DETECT).

Proves the 2nd embodiment ACTS (not just perceives) on the ONLY acceptance face
(bare `vector-cli --native-loop` + NL, no -p / no --sim flag), IN-PROCESS
(VECTOR_NO_ROS2=1 -> MuJoCoG1; launch_explore.sh must stay EMPTY throughout).

Chain per leg (all planner-reachable, mapped this round):
    启动 g1 仿真                 -> SimStartTool._start_g1 (in-process MuJoCoG1, Agent(base=g1))
    走到坐标 x=<tx>, y=<ty>       -> LLM calls navigate(tx,ty) -> MuJoCoG1.navigate_to
                                    (visibility-graph plan -> set_velocity gait loop, obstacle-aware)
                                 -> verify at_position(tx,ty)

HONEST, NON-GATED GROUNDED: at_position(x,y) (go2_sim_oracle.make_at_position, in the
evidence-classifier _PREDICATE_ORACLES allowlist) reads the base's DETERMINISTIC GT planar
pose (tol 0.5 m) — the actor cannot author it. GROUNDED requires BOTH at_position(tx,ty)==True
(GT arrived) AND actor-causation CAUSED (cmd_motion advanced + base displaced toward target);
a chat-only "已到达" or a no-op grades RAN/UNGROUNDED. This is NOT near_object (the gated
NL->object grounder) — it is a POSITIONAL goal to a coordinate the HUMAN states literally, so
the actor merely transcribes the demanded (tx,ty) (red-teamable: the driver checks navigate()
and at_position() carry the DEMANDED coords, not a self-satisfying one).

Built-in refutation: g1 spawns at (10,3). Target A (9,3) is 1.0 m away > 0.5 m tol, so
at_position(9,3) is FALSE at spawn — the False->True transition is EARNED only by the walk.
Leg B goes to a SECOND distinct target (10,4) -> selectivity: the robot ends up where
demanded (eyes differ), a trivially-green oracle cannot produce two distinct arrivals.

Usage: python g1_nav_accept.py            (defaults: A=(9,3), B=(10,4))
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

import pexpect

ROOT = "/home/yusen/Desktop/vector_os_nano"
# (tx, ty) legs — demanded literal coordinates the human states in NL.
# Overridable via env (G1_NAV_A / G1_NAV_B, "x,y") so a re-verify round can demand DIFFERENT
# coords than a prior run — non-memorized selectivity (a resolver that walks to arbitrary
# demanded coords, not a lucky fixed pair). Defaults preserve the R183/R216 legs.
def _leg(env_key: str, default: "tuple[float, float]") -> "tuple[float, float]":
    raw = os.environ.get(env_key)
    if not raw:
        return default
    x, y = (float(v) for v in raw.split(","))
    return (x, y)


LEG_A = _leg("G1_NAV_A", (9.0, 3.0))
LEG_B = _leg("G1_NAV_B", (10.0, 4.0))
TAG = sys.argv[1] if len(sys.argv) > 1 else "g1nav_r183"
SNAP = f"/tmp/g1_nav_accept/{TAG}"
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


def _clean_log(snap: str) -> str:
    try:
        raw = open(f"{snap}/repl.raw.log", encoding="utf-8", errors="replace").read()
    except OSError:
        return ""
    clean = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][0-9;]*|\x1b", "", raw)
    return re.sub(r"[⠀-⣿]", "", clean)


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


def parse_verdicts(snap: str) -> list[tuple[str, bool]]:
    clean = _clean_log(snap)
    out: list[tuple[str, bool]] = []
    for m in re.finditer(r"verdict\s+(GROUNDED|RAN|FAILED|NO_TRACE)\s+verified=(True|False)", clean):
        out.append((m.group(1), m.group(2) == "True"))
    return out


def nav_calls(snap: str) -> list[tuple[str, str]]:
    """Extract navigate(...) and at_position(...) arg strings for the red-team check."""
    clean = _clean_log(snap)
    navs = re.findall(r"navigate\(([^)]*)\)", clean)
    ats = re.findall(r"at_position\(([^)]*)\)", clean)
    return [("navigate", n) for n in navs] + [("at_position", a) for a in ats]


_llm_preflight()
print(f"[driver] spawning BARE vector-cli REPL (no -p/--sim); A={LEG_A} B={LEG_B} provider={PROVIDER}", flush=True)
child = pexpect.spawn(
    f"{ROOT}/.venv/bin/python", ["-m", "zeno.vcli.cli", "--native-loop"],
    env=env, cwd=ROOT, encoding="utf-8", codec_errors="replace",
    timeout=120, dimensions=(50, 200),
)
child.logfile_read = open(f"{SNAP}/repl.raw.log", "w")
result = {"launch_explore_seen": False}


def nav_turn(child, tx, ty, tag):
    msg = f"走到坐标 x={tx}, y={ty} 的位置，直接执行不用问我"
    print(f"\n[driver] NAV turn {tag}: -> ({tx},{ty})", flush=True)
    child.sendline(msg)
    child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=420)
    _eyes_frame(SNAP, tag)
    drain_until_quiet(child, quiet=3.0, max_wait=120)
    print(f"[driver] nav turn {tag} done", flush=True)


try:
    child.expect(r"vector>", timeout=60)
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
        print(f"\n[driver] g1 sim not started on attempt {attempt}; re-issuing", flush=True)
    if not started:
        print("\n[driver] g1 SIM NEVER STARTED via NL — aborting (no fake verdict)", flush=True)
        raise SystemExit("g1-sim-never-started")
    drain_until_quiet(child, quiet=3.0, max_wait=120)
    if launch_explore_running():
        result["launch_explore_seen"] = True
    print(f"\n[driver] g1 sim ready. launch_explore_seen={result['launch_explore_seen']}", flush=True)

    nav_turn(child, LEG_A[0], LEG_A[1], "legA")
    nav_turn(child, LEG_B[0], LEG_B[1], "legB")

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
calls = nav_calls(SNAP)
print("\n" + "=" * 64, flush=True)
print(f"[driver] provider={PROVIDER}  launch_explore_seen={result['launch_explore_seen']}", flush=True)
print(f"[driver] verdicts (in order) = {verdicts}", flush=True)
print(f"[driver] tool-call args (red-team: must carry DEMANDED coords) = {calls}", flush=True)
print(f"[driver] eyes: {SNAP}/eyes_legA.png , {SNAP}/eyes_legB.png", flush=True)
print("=" * 64, flush=True)
