"""OBSERVE probe #2: run sim-start NL through the REAL OpenAICompatBackend (STREAMING),
exactly as the CLI tool_use path does. Isolates whether the streaming tool-call
accumulation (openai_compat._call_streaming) — not model disposition — is what drops
gemini/mistral sim-start tool calls in the real REPL.

Reports per model: TOOL(name,args) vs TEXT vs the finish/stop reason.
Usage: python simstart_stream_probe.py [model ...]
"""
from __future__ import annotations

import os
import sys

ROOT = "/home/yusen/Desktop/vector_os_nano"
sys.path.insert(0, ROOT)

from vector_os_nano.vcli.backends.openai_compat import OpenAICompatBackend  # noqa: E402
from vector_os_nano.vcli.prompt import build_system_prompt  # noqa: E402
from vector_os_nano.vcli.tools.sim_tool import SimStartTool  # noqa: E402

MODELS = sys.argv[1:] or [
    "google/gemini-3.5-flash",
    "mistralai/mistral-medium-3-5",
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini",
]
NL = "启动 g1 仿真，现在就开始，直接执行不用问我"

system_blocks = build_system_prompt(agent=None, cwd=None, world=None)
tools = [{
    "name": "start_simulation",
    "description": getattr(SimStartTool, "__tool_description__", "Start a robot simulation."),
    "input_schema": SimStartTool.input_schema,
}]
messages = [{"role": "user", "content": NL}]
key = os.environ["OPENROUTER_API_KEY"]

for model in MODELS:
    backend = OpenAICompatBackend(api_key=key, model=model, base_url="https://openrouter.ai/api/v1")
    try:
        resp = backend.call(messages=messages, tools=tools, system=system_blocks, max_tokens=8000)
        if resp.tool_calls:
            tc = resp.tool_calls[0]
            print(f"[{model}] TOOL stop={resp.stop_reason} -> {tc.name}({tc.input})", flush=True)
        else:
            print(f"[{model}] TEXT stop={resp.stop_reason} -> {resp.text[:160]!r}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[{model}] ERROR -> {type(e).__name__}: {str(e)[:160]}", flush=True)
