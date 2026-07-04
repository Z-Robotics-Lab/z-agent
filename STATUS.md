# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-04 · R288 (E82, build) — promoted R287 courtyard provisional + swept the oldest stale courtyard sibling (blue) on the real face.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~43r unanswered; loop treads stale-bar sweep hygiene — 5/5 fetch bars re-confirmed, only SCENE_SWAP ord-posinv rotted).
last-round: R288 (E82, build). §1c PROMOTE: R287/E82 courtyard fetch.nl-new-world-courtyard provisional (GROUNDED 1/1 vlm-judge, survived R287->R288 boundary,
  red-team recorded, no counter-evidence) -> confirmed (supersedes R287 prov). §2 SWEEP next#2: re-verified the OLDEST stale courtyard sibling
  fetch.nl-new-world-courtyard-blue (age44, R244 GROUNDED 2/2) on the bare vcli+NL real face -> GROUNDED 1/1, brain routed perception_grasp(blue) ->
  holding_object('pickable_bottle_blue') actor=CAUSED verified=True. Judge ABSTAINed (gemma4:e4b non-determ E71, fail-closed -> eyes recorded self-read). LOOKED at
  the frame: BLUE bottle held aloft, green/purple/yellow/pink distractors REMAIN on the courtyard table = discrimination. Stale-green HOLDS. 5th consecutive sweep bar
  re-confirmed -> grasp EXECUTION healthy across worlds AND colours; the R284 ord-posinv fail stays SCENE_SWAP-isolated (target-select/hold under swap), NOT a rot.
frontier: (1) Continue the sweep of remaining stale bars: courtyard siblings red (age~43)/purple (age~42) cheap fetch re-verifies; g1.navigation (age71)/g1.perception
  (age63) + quantity-place.nl (age83) harder (embodiment/place-campaign) -> un-pressured rounds. (2) ord-posinv SCENE_SWAP regression = bounded ISOLATED DEBUG target
  (grasp-exec vs target-select under swap). (3) verify moat stays WITNESS-ONLY; a TRUSTED 2nd discriminator needs a funded/stronger VLM (billing/owner).
  (4) eyes verdict-render off-centers workspace on some turns -> spine gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE the deepseek provider via env (default qwen = Arrearage -> PREFLIGHT BLOCKED; provider select syntax + key live ONLY in
  .env.example); `set -a; . ./.env; set +a` loads the key. World knobs (all `VECTOR_`-prefixed): SCENE_CLUTTER=1, ROOM_TEMPLATE={warehouse|courtyard}, SCENE_SWAP=1.
  local ollama gemma4:e4b eyes+perception-VLM AUTO-routed (do NOT set VLM/JUDGE url; ABSTAIN is fail-closed, LOOK at the frame yourself). Interpreter `.venv/bin/python
  tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG> fetch`; RUN under `systemd-run --user --scope -p MemoryMax=24G`; fetch ~4min. HAZARD: the Bash-tool's OWN
  default timeout is 120s — set the tool `timeout` to ~600000 or the fetch is SIGTERM'd mid-run (kills the whole pgroup incl the scope; verified clean, no orphan).
  NEVER pkill mujoco — use scripts/sim-teardown. LEDGER HAZARD (E27/E81): edit a ledger ONLY by appending ONE preformatted line via `>>` — NEVER
  load-all->json.dumps->write-all (reorders -> quarantine). Row caps: <=1KB, string <=280 chars PYTHON len; confirmed rows' `redteam` MUST start with 'survived'.
  GUARD-CHAIN HAZARD (R288): a length-guard heredoc that AssertionErrors does NOT stop a following `echo >> ledger` — chain `python3 check && echo "$ROW" >>` (&&) or a
  malformed over-cap line ships + fails check.sh. board.py WRITES BOARD.md — run `.venv/bin/python loop/board.py` (NO redirect).
next:
  1. [ORIENT §1b, next-round promotion] Adjudicate the R288 courtyard-blue provisional -> `confirmed` (supersedes R244) if still standing. Do NOT do it the same
     round it was measured.
  2. [NON-gated VERIFY] CONTINUE the sweep of remaining stale bars in age order: courtyard siblings red (age~43) + purple (age~42) are cheap fetch re-verifies;
     THEN the harder/older g1.navigation (age71, reachable-coords hazard E49) + quantity-place.nl (age83, flaky place campaign E36) each get a dedicated round.
     5/5 fetch bars re-confirmed so far -> a stale-green is worse than a known red; refute/re-confirm each.
  3. [NON-gated DEBUG, bounded] Root-cause the ISOLATED ord-posinv SCENE_SWAP regression (Hypothesis Loop, DEBUG.md): grasp-execution vs target-selection
     under swap — compare a swap run vs the now-5x-GROUNDED no-swap fetches (clutter/warehouse/courtyard-green/blue all clean).
  4. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned NL->object
     grounder). CEO-gated ~43r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera in acceptance/capture.py = honest-verify spine; conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed. Reverted R282 (was R281/E78). <- frontier#4.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#4.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R280): gate/token R261..R280 CLEAN; R281 spine touch had NO token → reverted R282, audit-clean. R284..R288 touched NO spine path; rows are pure-append (no CEO/GATE token used).
last_review: R280
