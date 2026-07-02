<p align="center">
  <img src="images/ascii-art.png" width="800" alt="Vector Robotics">
</p>

<h1 align="center">Vector OS Nano</h1>

<p align="center">
  <b>Cross-embodiment robot OS: natural language controls everything.</b>
  <br>
  <b>No training. No fine-tuning. Just say what you want.</b>
  <br>
  <b>The agent decomposes any NL goal into a verified plan and executes long-chain tasks end-to-end.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/MuJoCo-3.6-green" alt="MuJoCo">
  <img src="https://img.shields.io/badge/Qwen-LLM_Brain-orange?logo=alibabacloud&logoColor=white" alt="Qwen via DashScope">
  <img src="https://img.shields.io/badge/ROS2_Jazzy-Navigation-blue?logo=ros&logoColor=white" alt="ROS2">
</p>

<p align="center">
  <i>Being developed at <b>CMU Robotics Institute</b>.</i>
</p>

---

<h3 align="center">Demo</h3>

<p align="center">
  <a href="https://drive.google.com/file/d/1a0Y46zHZ9VNUqBVCpGbyP9m2getLlIio/view">
    <img src="images/compressed_demo.gif" width="700" alt="Click to watch full demo video">
  </a>
  <br>
  <i>Click to watch full demo video</i>
</p>

---

## Quick Start

**Install** (requires Python 3.10+ and [uv](https://docs.astral.sh/uv/)):

```bash
git clone https://github.com/VectorRobotics/vector-os-nano.git
cd vector-os-nano
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[all]"
```

**Configure API key**:

```bash
cp .env.example .env    # then fill in ONE provider block
```

`.env` is git-ignored. The supported providers and their variables live in **`.env.example`
only** — it is the single canonical template. What is currently accepted on which provider is
recorded in [loop/ledger/BOARD.md](loop/ledger/BOARD.md).

**Run** — bare `vector-cli` + natural language is the whole interface:

```bash
vector-cli                  # interactive AI agent REPL
vector-cli --sim            # SO-101 arm in MuJoCo (natural language: "wave", "pick up the mug")
vector-cli --sim-go2        # Go2 quadruped in MuJoCo
#                             then by NL: "switch to g1" / "切换到 g1" → Unitree G1 humanoid (same room)
```

You can launch a sim, command it, and switch embodiments entirely by NL — no flags needed:
`启动 go2 仿真` · `走到桌子那边` · `切换到 g1`. The honest verdict prints back in the conversation.

**Add a skill** — drop a file in `vector_os_nano/skills/` and decorate it; no routing code to touch:

```python
from vector_os_nano.core.skill import skill, SkillContext
from vector_os_nano.core.types import SkillResult

@skill(aliases=["wave", "挥手"], direct=True)
class WaveSkill:
    name = "wave"
    description = "Wave the arm to greet"
    def execute(self, params: dict, context: SkillContext) -> SkillResult:
        ...
        return SkillResult(success=True)
```

A skill may wrap an external **VLA / VLM** or a classical **grasp / nav** stack — full protocol in
[docs/skill-protocol.md](docs/skill-protocol.md).

**Bring your own robot** — a robot is a **config bundle, not code**. You provide:

```
embodiments/<id>/robot.yaml            # spawn · stance (by joint name) · sensors · root_body · capabilities
embodiments/<id>/<model>.urdf + meshes/
embodiments/<id>/policy.pt + policy spec   # gait/control: observation library, action map, rate
```

Then `> 启动 <id> 仿真` — one generic driver stands it up, no per-robot Python. (`go2` and `g1` ship
as configs today; the generic driver that reads any bundle is landing on `arch/plug-and-play`.)

---

## Vector CLI

AI-powered terminal: control robots, edit code, and diagnose issues from one prompt. Powered by the VGG (Verified Goal Graph) cognitive layer — complex goals are decomposed into verified sub-plans; simple commands skip LLM and execute in <1 ms.

```
vector> explore the house
  > [1/1] explore_goal done 62.3s

vector> the dog hits walls at corners
  file_read("scripts/go2_vnav_bridge.py") ... ok
  file_edit(old="_MAX_SPEED = 0.6", new="_MAX_SPEED = 0.4") ... ok
  skill_reload("walk") ... ok

vector> go to the kitchen
  > [1/1] navigate_goal done 11.3s
```

**Slash commands:** `/help` `/model` `/tools` `/status` `/login` `/compact` `/clear` `/copy` `/export`

<p align="center">
  <img src="images/agent.png" width="700" alt="vector-cli with Go2 simulation">
  <br>
  <i>vector-cli controlling Go2 in MuJoCo: natural language conversation with V (right), live simulation (left).</i>
</p>

---

## Arm Simulation (MuJoCo)

Drive the SO-101 arm by natural language — no hardware required:

```bash
vector-cli --sim
# "wave", "go home", "pick up the mug"
```

<p align="center">
  <img src="images/sim_setup.png" width="700" alt="MuJoCo arm simulation">
  <br>
  <i>MuJoCo simulation: SO-101 arm with graspable objects, CLI conversation with V.</i>
</p>

Manipulation (VLM `detect` → EdgeTAM segment → point-cloud grasp point → IK) is validated in MuJoCo and **on by default** in the arm sim; set `VECTOR_ENABLE_MANIPULATION=0` to disable it.

---

## MCP Server

Let Claude Code control the robot via [Model Context Protocol](https://modelcontextprotocol.io):

```bash
vector-os-mcp --sim --stdio      # MuJoCo sim, stdio transport (add to Claude Code MCP config)
vector-os-mcp --hardware --stdio # real hardware
vector-os-mcp --sim              # SSE on :8100
```

Exposes all skills as MCP tools plus camera and world-state resources (`world://state`, `world://objects`, `camera://live`, …).

<p align="center">
  <img src="images/mcp_claude.png" width="700" alt="Claude Code controlling robot via MCP">
  <br>
  <i>Claude Code operating the robot via MCP: terminal (top) + live camera RGB + depth (bottom).</i>
</p>

<p align="center">
  <img src="images/skillgen.png" width="700" alt="Autonomous skill generation">
  <br>
  <i>Claude Agent autonomously designing, implementing, and executing new robot skills.</i>
</p>

---

## This repo develops itself

Vector OS Nano ships its own self-evolution loop: an agent-driven round protocol
([loop/ROUND.md](loop/ROUND.md)) governed by the constitution ([AGENTS.md](AGENTS.md)),
supervised by a portable runner that works with **any agent CLI and any model** —
Claude Code, Codex, opencode, or your own adapter. Each round plans, builds, real-verifies
on the bare `vector-cli` face, and records results to an append-only ledger.

Start at [loop/README.md](loop/README.md).

---

## Contributing

PRs welcome. By submitting a pull request you agree your contribution is licensed under Apache 2.0 (Section 5). Include the SPDX header on new files:

```python
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
```

---

## License

Copyright 2024-2026 Vector Robotics.

Licensed under the **Apache License, Version 2.0**; you may not use this file except in compliance with the License. You may obtain a copy at

> http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an **"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND**, either express or implied. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for the full terms, including attribution and patent-grant terms, and a list of bundled third-party components.

### Trademarks

"Vector Robotics" and "Vector OS Nano" are trademarks of Vector Robotics. The Apache License does not grant permission to use these names except as required for describing the origin of the Work and reproducing the contents of the NOTICE file.

---

<p align="center">
  <i>CMU Robotics Institute. Star this repo and stay tuned.</i>
</p>
