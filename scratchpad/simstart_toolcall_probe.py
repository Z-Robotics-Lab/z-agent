"""OBSERVE probe: does a BYO model emit the start_simulation TOOL CALL for an NL
sim-start command, using the REAL first-turn system prompt + tool schema?

Cheap (1 short completion per model, no sim spin-up, no sim-safety concern). It
reproduces the exact bare-REPL turn-1 conditions: agent=None => DEV persona from
build_system_prompt, the real start_simulation tool schema, and the forceful NL the
g1_accept driver sends. Reports for each model: TOOL (emitted start_simulation) vs
TEXT (chatted/asked) — the load-bearing distinction the D179 diagnosis is about.

Usage: python simstart_toolcall_probe.py [model ...]   (defaults = the failing families)
"""
from __future__ import annotations

import json
import os
import sys

ROOT = "/home/yusen/Desktop/vector_os_nano"
sys.path.insert(0, ROOT)

from openai import OpenAI  # noqa: E402

from vector_os_nano.vcli.backends.openai_compat import convert_system, convert_tools  # noqa: E402
from vector_os_nano.vcli.prompt import build_system_prompt  # noqa: E402
from vector_os_nano.vcli.tools.sim_tool import SimStartTool  # noqa: E402

MODELS = sys.argv[1:] or [
    "google/gemini-2.0-flash-001",
    "mistralai/mistral-medium-3.1",
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini",
    "deepseek/deepseek-chat",
]

NL = "启动 g1 仿真，现在就开始，直接执行不用问我"

# Real turn-1 system prompt (agent=None => DEV persona) + real start_simulation schema.
system_blocks = build_system_prompt(agent=None, cwd=None, world=None)
system_text = convert_system(system_blocks)
tool_schema = [{
    "name": "start_simulation",
    "description": SimStartTool.__doc__ or "Start a robot simulation.",
    "input_schema": SimStartTool.input_schema,
}]
# Use the decorator-provided description if present (matches what the CLI sends).
_desc = getattr(SimStartTool, "__tool_description__", None) or getattr(SimStartTool, "description", None)
if _desc:
    tool_schema[0]["description"] = _desc
oai_tools = convert_tools(tool_schema)

key = os.environ["OPENROUTER_API_KEY"]
client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")

print(f"=== system prompt persona (first 400 chars) ===\n{system_text[:400]}\n", flush=True)
print(f"=== tool desc ===\n{oai_tools[0]['function']['description']}\n", flush=True)
print("=" * 70, flush=True)

for model in MODELS:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": NL},
            ],
            tools=oai_tools,
            max_tokens=400,
        )
        msg = resp.choices[0].message
        tcs = msg.tool_calls or []
        if tcs:
            args = tcs[0].function.arguments
            print(f"[{model}] TOOL  -> {tcs[0].function.name}({args})", flush=True)
        else:
            txt = (msg.content or "").replace("\n", " ")[:180]
            print(f"[{model}] TEXT  -> {txt!r}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[{model}] ERROR -> {type(e).__name__}: {str(e)[:160]}", flush=True)
