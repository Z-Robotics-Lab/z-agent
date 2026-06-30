"""PLACE-mode diagnostic: same direct-cli path as measure_qwen.py, but adds --verbose so the
[MOBILE-PLACE]/[PGRASP] dock geometry lines surface, then extracts per trial the dock target,
EE-over/off offset, diag and eyes. Sizes the two place failure modes (nav/dock vs drop roll-off)
AND the miss magnitude. Run with the loop env sourced. Usage: diag_place.py "<cmd>" N TAG"""
import json, os, re, subprocess, sys, time

ROOT = "/home/yusen/Desktop/vector_os_nano"
SP = "/tmp/claude-1000/-home-yusen/de114851-2aa5-4dd2-b3cb-20b2199b9b23/scratchpad"
CMD = sys.argv[1] if len(sys.argv) > 1 else "把绿色的瓶子放到架子上"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 10
TAG = sys.argv[3] if len(sys.argv) > 3 else "place"
TIMEOUT = int(sys.argv[4]) if len(sys.argv) > 4 else 360

base_env = dict(os.environ)
base_env.update({
    "PATH": "/usr/bin:" + os.environ.get("PATH", ""),
    "VECTOR_SIM_WITH_ARM": "1", "MUJOCO_GL": "egl", "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1", "VECTOR_NO_ROS2": "1",
    "VECTOR_PROVIDER": "qwen", "QWEN_MODEL": os.environ.get("QWEN_MODEL", "qwen-max"),
    "VECTOR_MAX_TOKENS": "8000",
})
base_env.pop("VECTOR_MODEL", None)
base_env.pop("VECTOR_FETCH_FAR", None)

sys.path.insert(0, ROOT)
from vector_os_nano.acceptance.vision_judge import judge  # noqa: E402

grounded = accept = 0
modes = {}
for k in range(1, N + 1):
    snap = f"{SP}/{TAG}_{k}"
    os.system(f"rm -rf {snap}; mkdir -p {snap}")
    os.system("pkill -9 -f 'vector_os_nano.vcli.cli' 2>/dev/null; rosm nuke --yes >/dev/null 2>&1")
    time.sleep(1)
    env = dict(base_env); env["VECTOR_SNAPSHOT_DIR"] = snap
    diagf = f"{snap}/place_diag.jsonl"
    env["VECTOR_PLACE_DIAG"] = diagf
    try:
        p = subprocess.run(
            [f"{ROOT}/.venv/bin/python", "-m", "vector_os_nano.vcli.cli", "-p", CMD,
             "--sim-go2", "--headless", "--native-loop", "--json"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=TIMEOUT,
        )
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or "") if isinstance(e.stdout, str) else "") + " TIMEOUT"
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
    # geometry extraction from the env-gated side file (last line = post-dock pose)
    geo = ""
    try:
        with open(diagf) as f:
            lines = [ln for ln in f if ln.strip()]
        if lines:
            d = json.loads(lines[-1])
            geo = (f" dog_d2tgt={d.get('dog_d2tgt')} ee_d2tgt={d.get('ee_d2tgt')}"
                   f" ee_in_region={d.get('ee_in_region')} dog={d.get('dog')} tgt={d.get('tgt')}")
    except Exception:
        pass
    # eyes
    frames = [f for f in os.listdir(snap) if f.startswith("verdict_") and f.endswith(".png")] if os.path.isdir(snap) else []
    wit = "NO_FRAME"
    if frames:
        try:
            wit = judge(os.path.join(snap, sorted(frames)[-1])).witness
        except Exception as ex:
            wit = f"JUDGE_ERR:{ex}"[:40]
    ok = gt and wit == "PASS"
    accept += int(ok)
    mode = "GROUND" if gt else ("dropmiss" if diag == "drop_release" else diag)
    modes[mode] = modes.get(mode, 0) + 1
    print(f"TRIAL {k}/{N}: GT={'GROUNDED' if gt else 'RAN'} diag={diag} eyes={wit} ->{geo}", flush=True)

os.system("pkill -9 -f 'vector_os_nano.vcli.cli' 2>/dev/null; rosm nuke --yes >/dev/null 2>&1")
print(f"RESULT {TAG}: grounded={grounded}/{N} eyes_accept={accept}/{N} modes={modes} cmd={CMD}", flush=True)
