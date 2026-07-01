"""OpenRouter-independent eyes measurement: N direct cli turns (NO PTY — the PTY harness SIGKILLs
the cli) with Qwen routing, each capturing a verdict frame, then Qwen3-VL judges it. Reports
grounded_rate (GT) + eyes_accept (GT grounded AND judge PASS). Run with the loop env sourced."""
import json, os, re, subprocess, sys, time

ROOT = "/home/yusen/Desktop/vector_os_nano"
SP = "/tmp/claude-1000/-home-yusen/de114851-2aa5-4dd2-b3cb-20b2199b9b23/scratchpad"
CMD = sys.argv[1] if len(sys.argv) > 1 else "把绿色的瓶子拿过来"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
TAG = sys.argv[3] if len(sys.argv) > 3 else "m"
FAR = sys.argv[4] == "far" if len(sys.argv) > 4 else False

base_env = dict(os.environ)
base_env.update({
    "PATH": "/usr/bin:" + os.environ.get("PATH", ""),
    "VECTOR_SIM_WITH_ARM": "1", "MUJOCO_GL": "egl", "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1", "VECTOR_NO_ROS2": "1",
    "VECTOR_PROVIDER": "qwen", "QWEN_MODEL": os.environ.get("QWEN_MODEL", "qwen-plus"),
    "VECTOR_MAX_TOKENS": "8000",
})
base_env.pop("VECTOR_MODEL", None)
if FAR:
    base_env["VECTOR_FETCH_FAR"] = "1"
else:
    base_env.pop("VECTOR_FETCH_FAR", None)

sys.path.insert(0, ROOT)
from vector_os_nano.acceptance.vision_judge import judge  # noqa: E402

grounded = accept = 0
for k in range(1, N + 1):
    snap = f"{SP}/{TAG}_{k}"
    os.system(f"rm -rf {snap}; mkdir -p {snap}")
    os.system("pkill -9 -f 'vector_os_nano.vcli.cli' 2>/dev/null; rosm nuke --yes >/dev/null 2>&1")
    time.sleep(1)
    env = dict(base_env); env["VECTOR_SNAPSHOT_DIR"] = snap
    try:
        p = subprocess.run(
            [f"{ROOT}/.venv/bin/python", "-m", "vector_os_nano.vcli.cli", "-p", CMD,
             "--sim-go2", "--headless", "--native-loop", "--json"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=480,  # R11 retry loop can add ~90s to a FAR cli
        )
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + " TIMEOUT"
    m = re.search(r"VECTOR_VERDICT (\{.*\})", out)
    gt = False
    diag = "?"
    if m:
        try:
            vd = json.loads(m.group(1))
            gt = bool(vd.get("verified"))
            ps = vd.get("per_step") or []
            diag = (ps[-1].get("diagnosis") if ps else "?") or "ok"
        except Exception:
            gt = False
    grounded += int(gt)
    # judge the captured verdict frame
    frames = [f for f in os.listdir(snap) if f.startswith("verdict_") and f.endswith(".png")] if os.path.isdir(snap) else []
    wit = "NO_FRAME"
    if frames:
        try:
            wit = judge(os.path.join(snap, sorted(frames)[-1])).witness
        except Exception as ex:
            wit = f"JUDGE_ERR:{ex}"[:40]
    ok = gt and wit == "PASS"
    accept += int(ok)
    print(f"TRIAL {k}/{N}: GT={'GROUNDED' if gt else 'RAN'} diag={diag} eyes={wit} -> {'ACCEPT' if ok else 'flag'}", flush=True)

os.system("pkill -9 -f 'vector_os_nano.vcli.cli' 2>/dev/null; rosm nuke --yes >/dev/null 2>&1")
print(f"RESULT {TAG}: grounded_rate={grounded}/{N} eyes_accept={accept}/{N} cmd={CMD}", flush=True)
