# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D175 — g1 2ND EMBODIMENT ACCEPTED on the bare REPL by NL via DeepSeek (cross-embodiment ×
cross-model on the true face). Root-caused + fixed the RAN-False: an armless g1 was offered the full manipulation
surface (pick/place/…) because get_default_skills() registers them on every Agent — a frontier model chained a
doomed pick ('No arm connected'), dragging an otherwise-GROUNDED detect turn to False. Fix = gate manipulation
skills on has_arm in _build_motor_tools (Rule-11 single-source resolver, same as the has_base/navigate gate); go2+arm
keeps the full surface. Plus a convergence steer (detect→verify→finish) + gate describe on armless (its scan
auto-step needs an arm). NO spine change — evidence_passed stays strict (ALL checked steps GROUNDED).
- REAL-VERIFY (bare vcli+NL, VECTOR_PROVIDER=deepseek→deepseek-v4-flash, VECTOR_NO_ROS2=1 in-process, sim BY NL,
  nuke between): RED "找前面的红色的东西" → `detect → verify detection_matches_gt('红色的东西') == True ✓` →
  verdict GROUNDED verified=True (1/1, clean trace). GREEN "找前面的绿色的东西" → 0/14 grounded → RAN False
  (model hunted green hard; NOTHING grounded = honest refutation). launch_explore_seen=False throughout.
- EYES (independent, g1_eyes.py fresh MuJoCoG1 + segmentation GT + head_rgb.png I read): red=920 seg px in g1's
  head-cam view centroid≈(337,285); green=0 seg px (not in view). RGB shows a red cushion on the stool, no green.
  Oracle + detector + eyes ALL agree: red present→GROUNDED, green absent→refuted.
- RED-TEAM: bare REPL (pexpect `python -m vector_os_nano.vcli.cli --native-loop`, no -p/--sim, sim by NL GT marker
  `▸ sim start g1 ok`); in-process (launch_explore empty); oracle = MuJoCo SEGMENTATION GT, detector sees RGB-only
  (firewall) — not a self-read; refutation holds (green 0/14). RESIDUALS (flagged): actor=NOT_GRADED for perception
  (armless has no displacement — honest weaker grade, grounding is the GT spatial-match); N=1 grounded (RED) + N=1
  refuted (GREEN); driver's verdict_*.png eyes-copy did NOT fire on the g1 path (used g1_eyes.py instead — driver gap).

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/CAPABILITY/MODEL; plan·route·
         verify·recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   FETCH+PLACE firm 3 colours via DeepSeek (D172-174, go2+arm). g1 2ND EMBODIMENT (armless, camera-only)
         accepted for perception on the bare face via DeepSeek (D175). BYO-robot × BYO-model both proven on the true face.
owns:    vector_os_nano/vcli/native_loop.py (arm-gate + detect steer). scratchpad/g1_accept.py + g1_eyes.py (g1 driver).
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (I substitute by reading the offscreen render). NOT loop-blocking.
         PRE-EXISTING: tests/unit/vcli/test_config_deepseek_provider.py 3 fails (provider naming openai_compat vs
         openrouter) — predate this round, separate config drift, not touched.
next:
  1. [FRONTIER] g1 richer tasks: a 2nd present colour for GROUNDED (add a green/blue in the head-cam view for N≥2),
     then g1 NAVIGATION/VLN (it has a base) — walk-to + at_position on the true face.
  2. [FRONTIER] arm-free `describe` path (caption via head-cam VLM, no scan auto-step) so a camera-only body can
     describe — restores the gated capability honestly instead of just hiding it.
  3. [SPINE, high-value] D168 place-oracle identity+delta — LOAD-BEARING (D174 place leans on object-blind
     resting_on_receptacle). Top spine gate; queue for Yusen (spine-semantics gate).
  4. [FRONTIER] OpenRouter 3rd brain (model-id 404) → 3-model plug-and-play on one face.
tooling: scratchpad/g1_accept.py (BARE-REPL g1 driver: RED grounds / GREEN refutes; args red_nl green_nl tag;
  VECTOR_PROVIDER=deepseek). scratchpad/g1_eyes.py (independent eyes: head-cam RGB + seg GT, run AFTER REPL exits).
  scratchpad/repl_accept.py (go2 fetch/place driver, MODE=fetch|place|both|combo). GOTCHAS: `rosm nuke --yes` between
  sims, NEVER pkill mujoco; NEVER kill supervisor/sibling; g1 run ~6min; DeepSeek verdict = post-hoc parse of the
  ANSI-stripped log (live pexpect misses the ANSI-split `verified=`).

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only
  spine change). NOW LOAD-BEARING (D174 place leans on it). → go/no-go (spine-semantics gate).
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg → should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go (D171 refuted → dead-code removal).
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate.
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
