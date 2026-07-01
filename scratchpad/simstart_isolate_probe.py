"""Isolate D179's over-caution claim from routing/balance failures.
Uses the EXACT ids STATUS/D179 named + tiny max_tokens to fit residual credit.
TOOL => over-caution DISPROVEN (model tool-calls when the request fits budget)."""
import os, sys
sys.path.insert(0, "/home/yusen/Desktop/vector_os_nano")
from openai import OpenAI
from vector_os_nano.vcli.backends.openai_compat import convert_system, convert_tools
from vector_os_nano.vcli.prompt import build_system_prompt
from vector_os_nano.vcli.tools.sim_tool import SimStartTool

NL = "启动 g1 仿真，现在就开始，直接执行不用问我"
system_text = convert_system(build_system_prompt(agent=None, cwd=None, world=None))
desc = getattr(SimStartTool,"__tool_description__",None) or SimStartTool.__doc__ or "Start a robot simulation."
oai_tools = convert_tools([{"name":"start_simulation","description":desc,"input_schema":SimStartTool.input_schema}])
client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1")
for model, mt in [("google/gemini-3.5-flash",40),("mistralai/mistral-medium-3-5",50),("mistralai/mistral-small-3.2-24b-instruct",60)]:
    try:
        r = client.chat.completions.create(model=model,
            messages=[{"role":"system","content":system_text},{"role":"user","content":NL}],
            tools=oai_tools, max_tokens=mt)
        m = r.choices[0].message; tcs = m.tool_calls or []
        if tcs: print(f"[{model}] TOOL -> {tcs[0].function.name}({tcs[0].function.arguments})", flush=True)
        else: print(f"[{model}] TEXT -> {(m.content or '')[:120]!r}", flush=True)
    except Exception as e:
        print(f"[{model}] ERROR -> {type(e).__name__}: {str(e)[:140]}", flush=True)
