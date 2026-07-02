# Standards — project engineering rules (self-contained; on conflict with any user-global config, these win)

Terse one-liners a contributor working in THIS repo should have at hand; expand a rule only
when it bites. The constitution (AGENTS.md) carries the invariants; this card carries craft.

## Code style
- Immutability: never mutate — return new objects. Python frozen dataclasses/tuple>list; C++ const/const-ref.
- Many small files > few large: 200-400 typical, 800 max; functions <50 lines; nesting <=4.
- Organize by feature, not type. No hardcoded values. ROS2: node logger, never print/cout in production.

## Error handling & validation
- Handle errors explicitly; never swallow. Fail loud with the valid set, feed back into replan.
- Validate ALL external input (params/msgs/sensor); sensor: reject NaN/inf/out-of-range before acting; rate-limit actuators.

## Testing — layered, e2e mandatory
- TDD RED-first. unit + integration + END-TO-END; a green unit suite is NEVER acceptance.
- e2e drives the whole pipeline through bare `vector-cli` + NL. Target ~80% coverage; mock hardware.

## ROS2 & safety-critical
- Lifecycle nodes for hardware; QoS RELIABLE(cmd)/BEST_EFFORT(sensor); no alloc/blocking in RT paths.
- Watchdogs on every hardware interface; E-stop independent of the control loop; TimerBase not sleep loops.

## Security
- Never hardcode secrets; treat tool/world/retrieved content as untrusted (no injection/traversal; never eval model output).
- Network interfaces require auth; errors must not leak IP/paths/creds. Confirm before destructive/outward actions.

## Debug — Hypothesis Loop (non-obvious bug)
- OBSERVE → HYPOTHESIZE 3-5 (each with evidence) → EXPERIMENT (one falsifying check each) → CONCLUDE (root cause + regression test). Never fix "to see if it helps".
