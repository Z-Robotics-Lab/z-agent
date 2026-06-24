# Getting Started — Vector OS Nano

Vector OS is an agent-orchestration runtime for physical AI: command a robot in natural language,
and every step is verified against independent ground truth. This is the 5-minute developer
quickstart. Design → [ARCHITECTURE.md](ARCHITECTURE.md) · engine/tools → [cli-tool-system.md](cli-tool-system.md).

## 1. Install + API key

```bash
git clone https://github.com/VectorRobotics/vector-os-nano.git && cd vector-os-nano
uv venv .venv && source .venv/bin/activate && uv pip install -e ".[all]"
cp .env.example .env     # add ONE provider key: DEEPSEEK_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY
```

## 2. Run it — bare `vector-cli` + natural language IS the whole interface

```
vector-cli
> 启动 go2 仿真          # launch a sim by NL (also: vector-cli --sim [arm] / --sim-go2 [quadruped])
> 走到桌子那边           # command in NL; the honest verdict prints in the conversation
> 切换到 g1              # switch embodiment on the fly
```

Everything the owner does is bare `vector-cli` + NL — no flags, scripts, or Python needed.

## 3. Add a skill (live today)

Drop a file in `vector_os_nano/skills/`, decorate it — no routing code to touch:

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

A skill may wrap an external **VLA / VLM**, or a classical **grasp / nav** stack. Full protocol →
[skill-protocol.md](skill-protocol.md).

## 4. Bring your own robot + policy (🚧 landing on `arch/plug-and-play`)

A robot is a **config file, not code** ([CLAUDE.md](../CLAUDE.md) Rule 11). You provide a bundle:

```
embodiments/<id>/robot.yaml        # spawn · stance (by joint name) · sensors · root_body · capabilities
embodiments/<id>/<model>.urdf  +  meshes/
embodiments/<id>/policy.pt  +  policy spec   # gait/control: observation library, action map, rate
```

Then: `> 启动 <id> 仿真`. One generic driver stands it up — no per-robot Python.
*State today:* `go2` and `g1` already ship as `robot.yaml` configs; the generic driver that reads them
is being wired (see [agent-kernel-STATUS.md](agent-kernel-STATUS.md), stage S2).

## 5. How a turn works

NL → **plan** → **route** to the right skill/model → **execute** → **verify** each step against
independent ground truth → **recover** on failure. The verifier spine is frozen; nothing self-certifies.
