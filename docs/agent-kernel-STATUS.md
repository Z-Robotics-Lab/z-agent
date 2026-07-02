# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D182 — harder-NL frontier: NEGATED-DISTRACTOR NL grounds colour-selectively (eyes-confirmed, can-bias confound refuted by a control).
- FRONTIER (past D181's plain-colour floor): bare-REPL fetch on NEGATED-MULTI-DISTRACTOR NL, deepseek-chat, in-process
  VECTOR_NO_ROS2=1 (all launch_explore_seen=False). 3 pickables present throughout (green bottle, blue bottle, red can).
  · neg_red "不要蓝色…不要绿色…只把红色的罐子拿过来" → grasped pickable_can_red, GROUNDED True (1/1); EYES: RED can lifted, green+blue on table.
  · neg_green (CONTROL: negate can, demand bottle) "别拿红色的罐子…别动蓝色…把绿色的瓶子拿给我" → grasped pickable_bottle_green
    (verdict True, CAUSED), then read "拿给我" as HANDOVER→gripper_open→released (2nd verdict False, honestly reporting release).
    EYES: GREEN bottle carried off table to floor; RED+BLUE untouched → can-bias/grab-nearest CONFOUND REFUTED.
- RED-TEAM found a SPINE gap (queued, NOT crossed): holding_object(target) is target-aware (R2-7) BUT the target is
  ACTOR-authored (LLM chooses object AND writes the verify call). So the oracle certifies "held==named", NOT "named==the
  colour the HUMAN demanded". Under adversarial NL, NL-intent→colour fidelity is WITNESS-certified (eyes/VLM), not oracle-
  certified. Both results honest here (DeepSeek right + eyes agree); candidate hardening = a world-owned NL→object grounder.

goal:    PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/CAPABILITY/MODEL; plan·route·verify·recover.
         Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   FRONTIER (find-fetch NL robustness) — negated-distractor NL accepted, eyes-confirmed, red-teamed. D163 CLOSED (D181).
owns:    verify+frontier round — no kernel change. Harness: scratchpad/repl_accept.py + run_neg{,2}.sh. Frames: /tmp/repl_accept/neg_{red,green}.
blocked: NONE for core acceptance (DeepSeek funded). OpenRouter+DashScope credit exhausted → blocks OpenRouter-N≥4
         + the automated VLM vision-judge (the ONLY thing that would drop the manual-eyes dependency). PRE-EXISTING: test_config_deepseek_provider.py 3 fails.
next:
  1. [FRONTIER] keep pushing find-fetch NL: MODE=combo single multi-clause "把红色的拿过来放到架子上"; push N per phrasing to
     first failure; ambiguity ("那个"), quantity, ordinal. DeepSeek funded → runnable now. Eyes remain the NL-intent witness.
  2. [FRONTIER] 2nd embodiment g1 GROUNDED nav — non-gated g1 build; VLN GROUNDED accept stays CEO-gated (near_object).
  3. [BYO-MODEL] N≥4 mistral-small-3.2-24b ready on OpenRouter the moment its credit is restored (external).

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **SPINE (D182): actor-authored verify target** — for adversarial NL, holding_object(target) can't certify NL-intent→colour
  fidelity (actor authors the target). Needs a world-owned NL→object grounder OR keep a mandatory human/VLM witness. Spine-semantics gate.
- **BILLING (external)**: OpenRouter + DashScope credit exhausted. Blocks OpenRouter-N≥4 (mistral-small) + the automated VLM vision-judge only.
- **META: plug-and-play verify-predicates** — `_PREDICATE_ORACLES` hardcoded kernel list (evidence_classifier.py:52) →
  every new predicate is a spine gate → VIOLATES "bring a verify-predicate — no kernel edits". World-declared metadata (stricter-only).
- **D178 near_object VLN predicate** · **D176 cmd_motion driver seam** · **D168 place-oracle harden** · **S8 retire legacy** ·
  **relational near(a,b)** · Stage gates S4/S5/S6/nav-FAR/strategy_params/explore-TARE/VLN-SysNav. New deps/interfaces/hw/sec here.
