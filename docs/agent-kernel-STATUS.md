# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D176 — g1 NAVIGATION (locomotion, g1's 2ND capability) ACCEPTED on the bare REPL by NL via
DeepSeek — a leap in KIND from perception (D175). g1 already had a base + full in-process locomotion stack
(navigate_to→g1_vgraph→_walk_to_waypoint→set_velocity) + get_position/heading (at_position binds). The ONE gap:
MuJoCoG1 didn't expose cmd_motion() → actor_causation._capture_base read base_cmd_motion=None → nav fail-closed to
UNCAUSED → could only reach RAN. FIX (DRIVER enrichment, spine grade() BYTE-UNCHANGED): set_velocity now accumulates
|vx|+|vy|+|vyaw| into _cmd_motion + exposes cmd_motion() — the SAME honest signal go2 exposes. A no-op/teleport/
blocked nav still grades UNCAUSED (proven by the GREEN refutation). g1 single-threaded → no _skill_ctrl_tid gate needed.
- REAL-VERIFY (bare vcli+NL via generic g1_accept.py, VECTOR_PROVIDER=deepseek→deepseek-v4-flash, VECTOR_NO_ROS2=1
  in-process, sim BY NL, nuke between): RED "走到坐标 x=9, y=3 的位置" → navigate→verify at_position(9,3) → verdict
  GROUNDED verified=True (1/1). GREEN "走到坐标 x=15, y=3" (boxed-in/unreachable) → can't arrive → at_position False →
  verdict RAN verified=False (honest refutation). launch_explore_seen=False throughout.
- PROBE (scratchpad/g1_nav_probe.py, deterministic skill-direct 2nd witness — NOT acceptance): reachable
  (9,3)/(10,4)/(8.5,2.5)/(3,3 @6.75m) → reached, z=0.77, dcmd_motion 36-113, at_position=True, actor=CAUSED → GROUNDED;
  blocked (15,3)/(10,10) → planner None, robot still, at_position=False → RAN. Oracle discriminates by ARRIVAL, not distance.
- RED-TEAM: DECISIVE anti-trivial — RED at_position(9,3,tol=0.5) is FALSE at spawn (10,3) (dist=1.0>0.5), so GROUNDED
  REQUIRED real displacement; far-reachable grounds/blocked refutes → oracle reads true GT, not the model's claim;
  in-process proven; actor=CAUSED = unchanged go2 signal. RESIDUALS (flagged): N=1 REPL RED + N=1 REPL GREEN (probe
  corroborates 4/4+2/2); no verdict PNG for a nav turn (2nd witness = GT pos read + probe, not a frame); cmd_motion
  driver change flagged for Yusen async review (enables a new GROUNDED capability; grade() spine byte-unchanged →
  defensible as driver enrichment, NOT a spine gate — but flagged in case he deems it spine-adjacent).

goal:    PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/CAPABILITY/MODEL; plan·route·verify·recover.
         Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   FETCH+PLACE 3 colours via DeepSeek (D172-174, go2+arm). g1 2ND EMBODIMENT: PERCEPTION (D175) + LOCOMOTION
         (D176) both accepted on the true face. BYO-robot × BYO-model × 2 capability dimensions on g1, all in-process.
owns:    vector_os_nano/hardware/sim/mujoco_g1.py (cmd_motion seam). scratchpad/g1_nav_probe.py + g1_accept.py (drivers).
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (substitute: read offscreen render / deterministic probe). NOT loop-blocking.
         PRE-EXISTING: tests/unit/vcli/test_config_deepseek_provider.py 3 fails (provider naming drift) — untouched.
next:
  1. [FRONTIER] g1 VLN/SysNav — chain detect→navigate ("走到红色的东西那里": perceive target, then walk to it) =
     perception+locomotion COMPOUND on the true face. + firm nav N≥2 (2nd coord) + free-form NL ("往前走两米").
  2. [FRONTIER] arm-free `describe` path (caption via head-cam VLM, no scan auto-step) — D175 next#ii, still open.
  3. [SPINE, high-value] D168 place-oracle identity+delta — LOAD-BEARING (D174 place leans on it). CEO gate, queue for Yusen.
  4. [FRONTIER] OpenRouter 3rd brain (model-id 404) → 3-model plug-and-play on one face.
tooling: scratchpad/g1_accept.py (BARE-REPL driver; generic [red_nl] [green_nl] [tag]; reused for nav — RED grounds/
  GREEN refutes; VECTOR_PROVIDER=deepseek). scratchpad/g1_nav_probe.py (deterministic nav reach/refute + CAUSED grade).
  GOTCHAS: `rosm nuke --yes` between sims, NEVER pkill mujoco; NEVER kill supervisor/sibling; g1 run ~4-6min; PYTHONPATH=ROOT
  for scratchpad scripts; DeepSeek verdict = post-hoc parse of the ANSI-stripped log (live pexpect misses ANSI-split `verified=`).

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **D176 cmd_motion driver seam** (flagged, likely non-gate): enables g1 nav GROUNDED; grade() spine byte-unchanged.
  → Yusen async review — confirm it's a driver enrichment, not a spine-semantics change.
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only
  spine change). NOW LOAD-BEARING (D174 place leans on it). → go/no-go (spine-semantics gate).
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg → should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go (D171 refuted → dead-code removal).
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate.
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
