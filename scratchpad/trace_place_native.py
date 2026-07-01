"""DEBUG OBSERVE (D171 place flounder): capture the EXACT native tool-call sequence
DeepSeek emits on the PLACE compound "把绿色的瓶子放到架子上", in-process, one sim.

Builds the same in-process go2+arm agent the bare REPL builds (VECTOR_NO_ROS2=1),
wires the DeepSeek backend via resolve_credentials, then calls engine.run_turn_native
directly with an on_progress recorder so every (tool, args) the model chose is printed.
NOT the acceptance face — a diagnostic. rosm nuke at the end.
"""
from __future__ import annotations

import os
import sys

ROOT = "/home/yusen/Desktop/vector_os_nano"
sys.path.insert(0, ROOT)

# Faithful to D171: deepseek-chat (repl_accept.py default), headless egl in-process.
os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-chat")
os.environ["VECTOR_PROVIDER"] = "deepseek"
os.environ["VECTOR_NO_ROS2"] = "1"
os.environ["VECTOR_SIM_WITH_ARM"] = "1"
os.environ["MUJOCO_GL"] = "egl"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ.pop("DISPLAY", None)
os.environ.pop("WAYLAND_DISPLAY", None)

UTTER = sys.argv[1] if len(sys.argv) > 1 else "把绿色的瓶子放到架子上"


def main() -> None:
    from vector_os_nano.vcli.config import resolve_credentials
    from vector_os_nano.vcli.backends import create_backend
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.tools import CategorizedToolRegistry
    from vector_os_nano.hardware.sim.go2_inprocess import build_inprocess_go2_agent
    from vector_os_nano.vcli.worlds import resolve_world

    key, provider, model, base_url = resolve_credentials()
    print(f"[obs] provider={provider} model={model} base_url={base_url} key?={bool(key)}", flush=True)

    print("[obs] building in-process go2+arm agent (headless egl)...", flush=True)
    agent = build_inprocess_go2_agent(
        gui=False, with_arm=True, api_key=key, status=lambda m: print("  [build]", m, flush=True)
    )

    backend = create_backend(provider=provider, api_key=key, model=model, base_url=base_url)
    registry = CategorizedToolRegistry()
    engine = VectorEngine(backend=backend, registry=registry)
    world = resolve_world(agent)
    print(f"[obs] world={getattr(world,'world_id',world)!r}", flush=True)
    engine.init_vgg(agent=agent, world=world, persist_dir=None)

    # Recorder: capture every progress emission (tool dispatches + verify + finish).
    events: list[str] = []

    def on_progress(msg: str) -> None:
        events.append(msg)

    print(f"\n[obs] === run_turn_native({UTTER!r}) via {model} ===", flush=True)
    from vector_os_nano.vcli.session import create_session
    session = create_session(metadata={"native_scratch": True})
    trace = engine.run_turn_native(UTTER, agent=agent, session=session, on_progress=on_progress)

    print("\n[obs] --- PROGRESS EVENTS (raw tool stream) ---", flush=True)
    for i, e in enumerate(events):
        print(f"  [{i}] {e}", flush=True)

    print("\n[obs] --- TRACE STEPS ---", flush=True)
    steps = getattr(trace, "steps", None) or []
    for i, st in enumerate(steps):
        print(f"  step[{i}]: {st}", flush=True)

    # Verdict from the honest spine (never self-computed).
    try:
        from vector_os_nano.vcli.cognitive.trace_store import verify_oracle_names
        from vector_os_nano.vcli.verdict import VerdictReport
        names = verify_oracle_names(agent, engine)
        report = VerdictReport.from_trace(trace, names)
        print(f"\n[obs] VERDICT verified={report.verified} n_grounded={getattr(report,'n_grounded',None)}", flush=True)
        print(f"[obs] oracle_names={sorted(names)}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[obs] verdict build failed: {type(e).__name__}: {e}", flush=True)

    # Full assistant messages (what the model actually said / tool_use it emitted).
    print("\n[obs] --- SESSION MESSAGES (assistant text + tool_use) ---", flush=True)
    try:
        for m in session.to_messages():
            role = m.get("role")
            content = m.get("content")
            if isinstance(content, list):
                for block in content:
                    bt = block.get("type")
                    if bt == "text":
                        print(f"  [{role}/text] {block.get('text','')[:300]}", flush=True)
                    elif bt == "tool_use":
                        print(f"  [{role}/tool_use] {block.get('name')}({block.get('input')})", flush=True)
                    elif bt == "tool_result":
                        c = block.get("content")
                        print(f"  [{role}/tool_result] {str(c)[:200]}", flush=True)
            else:
                print(f"  [{role}] {str(content)[:300]}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[obs] session dump failed: {e}", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        import subprocess
        subprocess.run(["rosm", "nuke", "--yes"], capture_output=True)
        print("\n[obs] rosm nuke done", flush=True)
