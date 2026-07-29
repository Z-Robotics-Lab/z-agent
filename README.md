<h1 align="center">Zeno</h1>

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
The quickstart below reflects the ground-up rename to Zeno (`vector-cli` → `zeno`).

## Quick Start (inherited; being reworked)

```bash
git clone https://github.com/Z-Robotics-Lab/z-agent.git
cd z-agent
uv venv .venv && source .venv/bin/activate
uv pip install -e .
cp .env.example .env    # fill in ONE provider block
zeno                    # interactive agent REPL
```

Go2W world (requires the [go2W_Sim](https://github.com/Z-Robotics-Lab/go2W_Sim) digital twin
on the same host — the agent will bring the sim + nav stack + RViz up itself):

```
zeno> 去 (2, 0)            # navigate: agent brings up the chain, drives, verifies arrival
zeno> explore              # TARE autonomous exploration, verified by explored-volume growth
```

## 4090 workstation deployment (real Go2W)

The main controller is the 4090 workstation: it runs the `zeno` CLI, the perception
client (encodes D435i frames for the RynnBrain VLM), and drives the real robot over a
subscribe-only cross-machine DDS link to the NUC. Deployment lives in a **git worktree**
so the production checkout is a first-class, reproducible tree (not a machine's manual
leftovers):

```bash
# 1. Worktree for the real world (branch hw-go2w-manip), Python 3.12 venv.
#    The venv is no-system-site-packages; rclpy enters PYTHONPATH from system ROS,
#    which the launcher (below) sources — do NOT pip-install ROS.
python3.12 -m venv .venv && source .venv/bin/activate
pip install -U pip

# 2. Kernel + test deps + the perception CLIENT (pillow for frame encoding).
#    perception-client carries pillow WITHOUT torch — the RynnBrain model runs in
#    its own venv (~/envs/rynnbrain), so the zeno venv never needs the torch stack.
pip install -e '.[dev,perception-client]'

# 3. Credentials (DeepSeek etc.) — .env is gitignored; copy from the NUC.
scp go2w-nuc:z-agent/.env .env && chmod 600 .env

# 4. Install the workstation launcher (sets ROS + DDS + world env, see below).
scripts/install-launcher-workstation.sh   # installs ~/.local/bin/zeno

# 5. Launch. The launcher exports ZENO_WORLD=go2w_real, so bare `zeno` enters the
#    real-robot world directly.
zeno
```

`scripts/install-launcher-workstation.sh` bakes the 4090 startup recipe into
`~/.local/bin/zeno`: it sources `/opt/ros/jazzy`, points `CYCLONEDDS_URI` at the
workstation DDS profile (subscribe-only, domain 20), and sets
`ZENO_WORLD=go2w_real` + the SSH nav transport to the NUC. `which zeno` should then
resolve to `~/.local/bin/zeno`. (The NUC has a sibling variant,
`scripts/install-launcher.sh`.)

The RynnBrain perception oracle (its own venv + weights + systemd service) is set up
separately — see [scripts/rynnbrain/README.md](scripts/rynnbrain/README.md).

## Architecture (the parts that matter)

- **Honest-verify spine** (`zeno/vcli/cognitive/`): evidence classifier +
  actor-causation grading + goal verifier. A step counts only if its predicate reads
  world ground truth AND the robot actually caused the change.
- **World Protocol** (`zeno/vcli/worlds/`): a robot is a plugin + manifest —
  tools, verify predicates, persona, vocab. No kernel edits to bring a robot.
- **Robot backend contract**: a small HTTP bridge (pose / waypoint / ground-truth / health)
  is the seam between the runtime and any backend — Isaac Sim today, the real Go2W next,
  with the agent layer unchanged.

## License

Apache License 2.0. Copyright 2024-2026 Vector Robotics (upstream) and Z-Robotics-Lab
(fork changes). See [LICENSE](LICENSE) and [NOTICE](NOTICE); upstream attribution preserved.
"Vector Robotics" and "Vector OS Nano" are trademarks of Vector Robotics — this fork is
renamed to Zeno accordingly.
