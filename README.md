<h1 align="center">Z Agent</h1>

<p align="center">
  <b>Z-Robotics-Lab's agent runtime for physical AI: natural language in, verified robot behavior out.</b>
  <br>
  <b>Open the CLI, say "explore" — the agent brings up the sim, the nav stack, RViz, and drives the robot.</b>
  <br>
  <b>Same CLI, same tools on real hardware. Sim-to-real symmetry is the product requirement.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Isaac_Sim-5.1-76b900" alt="Isaac Sim">
  <img src="https://img.shields.io/badge/ROS2_Jazzy-Navigation-blue?logo=ros&logoColor=white" alt="ROS2">
  <img src="https://img.shields.io/badge/License-Apache_2.0-green" alt="Apache 2.0">
</p>

<p align="center">
  <i>Forked from <a href="https://github.com/VectorRobotics/vector-os-nano">VectorRobotics/vector-os-nano</a>
  (Apache-2.0) and slimmed into a product runtime. The honest-verify spine — every agent step is graded
  against ground truth the actor cannot author — is inherited intact.</i>
</p>

---

## What this is

An agent-orchestration runtime: **plan · route · verify · recover**. The agent decomposes a
natural-language goal, routes each step to the best tool (big model, small model, classical
nav/manip stack, atomic action), and grades every step on deterministic predicates reading
ground truth — so "done" means *verified done*, never *the model said so*.

Flagship world: **Unitree Go2W** (wheeled quadruped + Livox Mid-360 + PiPER arm) —
an Isaac Sim digital twin driven through the CMU autonomy stack
([go2W_Sim](https://github.com/Z-Robotics-Lab/go2W_Sim)), with the identical CLI targeting
the real robot.

Status: under active development (fork bootstrap in progress — see [progress.md](progress.md)).
The quickstart below will change as the runtime is slimmed and renamed (`vector-cli` → `za`).

## Quick Start (inherited; being reworked)

```bash
git clone https://github.com/Z-Robotics-Lab/z-agent.git
cd z-agent
uv venv .venv && source .venv/bin/activate
uv pip install -e .
cp .env.example .env    # fill in ONE provider block
vector-cli              # interactive agent REPL
```

Go2W world (requires the [go2W_Sim](https://github.com/Z-Robotics-Lab/go2W_Sim) digital twin
on the same host — the agent will bring the sim + nav stack + RViz up itself):

```
vector> 去 (2, 0)          # navigate: agent brings up the chain, drives, verifies arrival
vector> explore            # TARE autonomous exploration, verified by explored-volume growth
```

## Architecture (the parts that matter)

- **Honest-verify spine** (`vector_os_nano/vcli/cognitive/`): evidence classifier +
  actor-causation grading + goal verifier. A step counts only if its predicate reads
  world ground truth AND the robot actually caused the change.
- **World Protocol** (`vector_os_nano/vcli/worlds/`): a robot is a plugin + manifest —
  tools, verify predicates, persona, vocab. No kernel edits to bring a robot.
- **Robot backend contract**: a small HTTP bridge (pose / waypoint / ground-truth / health)
  is the seam between the runtime and any backend — Isaac Sim today, the real Go2W next,
  with the agent layer unchanged.

## License

Apache License 2.0. Copyright 2024-2026 Vector Robotics (upstream) and Z-Robotics-Lab
(fork changes). See [LICENSE](LICENSE) and [NOTICE](NOTICE); upstream attribution preserved.
"Vector Robotics" and "Vector OS Nano" are trademarks of Vector Robotics — this fork is
renamed to Z Agent accordingly.
