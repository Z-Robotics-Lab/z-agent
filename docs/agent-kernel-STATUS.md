# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D177 — BYO-MODEL to a THIRD model family: OpenAI GPT-4o-mini via OpenRouter ACCEPTED on the
bare REPL by NL (g1 perception RED grounds / GREEN refutes). The "3rd-brain 404" was a STALE default model id, not a
key/network fault: config's forced-openrouter branch defaulted to `anthropic/claude-sonnet-4-6` (no endpoints on this
key). FIX (config only, spine/interface UNCHANGED): default → `openai/gpt-4o-mini` (broadly-available, strong tool-caller),
VECTOR_MODEL/openrouter_model override; fully-qualified ids never re-prefixed. Preflight also proved meta-llama/llama-3.3-70b OK.
- REAL-VERIFY (bare vcli+NL via g1_accept.py, VECTOR_PROVIDER=openrouter VECTOR_MODEL=openai/gpt-4o-mini, VECTOR_NO_ROS2=1
  in-process, sim BY NL, nuke after). REPL banner: `Model: openai/gpt-4o-mini | Provider: OpenRouter` (re-checked via
  resolve_credentials — NOT a deepseek/qwen fallback). RED "找前面的红色的东西" → detect→verify detection_matches_gt ✓ →
  GROUNDED verified=True (1/1, clean detect→verify→finish). GREEN "找前面的绿色的东西" → 12 hunt steps, green NEVER grounds →
  RAN verified=False (4/12; the 4 are incidental at_position passes, not the green task). launch_explore count=0.
- RED-TEAM: brain genuinely OpenAI GPT-4o-mini (banner + resolve_credentials); frozen seg-GT moat (D175) unchanged — RED
  grounds/GREEN refutes with the SAME oracle. RESIDUALS (flagged): N=1 RED + N=1 GREEN; gpt-4o-mini's refutation discipline
  WEAKER than deepseek (wandered to made-up coords vs cleanly concluding "not found") — model-quality note, moat held;
  perception actor=NOT_GRADED (camera-only); no verdict PNG on the g1 perception path (seg-GT oracle is the witness).
- FRONTIER RESEARCH (recorded, NOT shipped): a scene probe (scratchpad/g1_scene_probe.py) proved honest perception-LOAD-BEARING
  g1 VLN is MULTI-ROUND-blocked: (1) projection gap (detect→no world coord), (2) visible-red≠navigable-red, (3) pickable xy
  inside table-obstacle inflation (planner 1.36-1.74m, res=False); reachable coloured targets are floor rugs. Forcing VLN → a
  hollow compound (perception decorative). NEXT-FRONTIER DESIGN in D177: visual-servo approach skill + a new near_object predicate.

goal:    PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/CAPABILITY/MODEL; plan·route·verify·recover.
         Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   BYO-MODEL now proven across 3 model families on the true face — Qwen (D≤171) · DeepSeek (D172-176) · OpenAI GPT-4o-mini
         via OpenRouter (D177). BYO-ROBOT: go2 (fetch/place) + g1 (perception D175 + locomotion D176). Breadth compounds.
owns:    vector_os_nano/vcli/config.py (openrouter default). tests/unit/vcli/test_config_env_credentials.py (+2).
         scratchpad/g1_accept.py (+openrouter default), scratchpad/g1_scene_probe.py (VLN research).
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (substitute: seg-GT oracle / deterministic probe). NOT loop-blocking.
         PRE-EXISTING: tests/unit/vcli/test_config_deepseek_provider.py 3 fails (provider naming drift) — untouched.
next:
  1. [FRONTIER] g1 VLN — execute D177's honest design: visual-servo `approach(query)` skill (detect→horizontal-bearing→step→
     re-detect) + NEW world-side `near_object(colour,radius)` verify predicate (object GT pos + robot GT pos; spine-untouched,
     FLAG for async review). OR scene-curate a perceivable-AND-reachable coloured target. A proper leap-in-kind next round.
  2. [FRONTIER] 4th model family — meta-llama/llama-3.3-70b via OpenRouter (preflighted OK) → N=4 plug-and-play; cheap add.
  3. [FRONTIER] arm-free `describe` path (caption via head-cam VLM, no scan auto-step) — D175 next#ii, still open.
  4. [SPINE, high-value] D168 place-oracle identity+delta — LOAD-BEARING (D174 place leans on it). CEO gate, queue for Yusen.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **D177 near_object VLN predicate** (FUTURE, flagged): the next-round g1 VLN needs a new world-side `near_object` verify
  predicate + a visual-servo approach skill. Spine grade() would stay byte-unchanged (state-oracle-vs-constant, like
  detection_matches_gt). → treat as plug-and-play world registration, but flag for Yusen async review (verify-adjacent).
- **D176 cmd_motion driver seam** (flagged, likely non-gate): enables g1 nav GROUNDED; grade() spine byte-unchanged.
  → Yusen async review — confirm it's a driver enrichment, not a spine-semantics change.
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only
  spine change). NOW LOAD-BEARING (D174 place leans on it). → go/no-go (spine-semantics gate).
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg → should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go (D171 refuted → dead-code removal).
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
