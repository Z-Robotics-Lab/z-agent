# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-04 · R289 (E82, build) — promoted R288 courtyard-blue provisional + swept the next stale courtyard sibling (red, hue-adjacent) on the real face.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~44r unanswered; loop treads stale-bar sweep hygiene — 6/6 fetch bars re-confirmed, only SCENE_SWAP ord-posinv rotted).
last-round: R289 (E82, build). §1c PROMOTE R288 courtyard-blue prov -> confirmed (supersedes R288). §2 SWEEP next#2: re-verified next stale sibling
  fetch.nl-new-world-courtyard-red (age~43, R245 2/2, hue-adjacent) on the bare face -> GROUNDED 1/1 holding_object('pickable_can_red') actor=CAUSED; eyes vlm-judge
  PASS (NOT the abstain blue hit R288); FRAME: RED can aloft, purple/yellow/green distractors remain=discrimination. 6th sweep bar re-confirmed; ord-posinv stays SWAP-isolated.
frontier: (1) Continue the sweep of remaining stale bars: courtyard-purple (age~43) cheap fetch re-verify is the LAST cheap courtyard sibling; then the harder/older
  g1.navigation (age~72, reachable-coords hazard E49) + g1.perception (age~64) + quantity-place.nl (age~84, flaky place campaign E36) each get a dedicated round.
  (2) ord-posinv SCENE_SWAP regression = bounded ISOLATED DEBUG target (grasp-exec vs target-select under swap). (3) verify moat stays WITNESS-ONLY; a TRUSTED 2nd
  discriminator needs a funded/stronger VLM (billing/owner) — local gemma4:e4b judge is PASS/ABSTAIN non-determ (E71/E71), recorded-not-trusted. (4) eyes verdict-render
  off-centers workspace on some turns -> spine gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE the deepseek provider via env (default qwen = Arrearage ->
  PREFLIGHT BLOCKED; provider select syntax + key live ONLY in .env.example); `set -a; . ./.env; set +a` loads the key. World knobs (all `VECTOR_`-prefixed): SCENE_CLUTTER=1,
  ROOM_TEMPLATE={warehouse|courtyard}, SCENE_SWAP=1. local ollama gemma4:e4b eyes+perception-VLM AUTO-routed (do NOT set VLM/JUDGE url; ABSTAIN is fail-closed, LOOK at
  the frame yourself). Interpreter `.venv/bin/python tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG> fetch`; RUN under `systemd-run --user --scope -p MemoryMax=24G`;
  fetch ~4min. Set VECTOR_EVIDENCE_DIR=var/evidence/R$N/<tag> per run (else 2 runs collide, E54). HAZARD: the Bash-tool's OWN default timeout is 120s — set the tool
  `timeout` to ~600000 or the fetch is SIGTERM'd mid-run (kills the whole pgroup incl the scope; verified clean, no orphan). NEVER pkill mujoco — use scripts/sim-teardown.
  LEDGER HAZARD (E27/E81): edit a ledger ONLY by appending ONE preformatted line via `>>` — NEVER load-all->json.dumps->write-all (reorders -> quarantine). Row caps:
  <=1KB, string <=280 chars PYTHON len; confirmed rows' `redteam` MUST start with 'survived'; acceptance rows MUST include `evidence` (R289: a promotion row shipped
  w/o it, caught by check.sh; soft-reset the WIP + re-append pure vs last clean ledger). GUARD-CHAIN HAZARD (R288): chain `python3 check && echo "$ROW" >>` (&&). board.py
  WRITES BOARD.md — run `.venv/bin/python loop/board.py` (NO redirect); the supervisor's post-round rounds.jsonl append shifts BOARD ages so the NEXT round must regen it.
next:
  1. [ORIENT §1b, next-round promotion] Adjudicate the R289 courtyard-red provisional -> `confirmed` (supersedes R245) if still standing. Do NOT do it the same
     round it was measured.
  2. [NON-gated VERIFY] CONTINUE the sweep of remaining stale bars in age order: courtyard-purple (age~43) is the LAST cheap courtyard fetch re-verify;
     THEN the harder/older g1.navigation (age~72, reachable-coords hazard E49) + g1.perception (age~64) + quantity-place.nl (age~84, flaky place campaign E36) each
     get a dedicated round. 6/6 fetch bars re-confirmed so far -> a stale-green is worse than a known red; refute/re-confirm each.
  3. [NON-gated DEBUG, bounded] Root-cause the ISOLATED ord-posinv SCENE_SWAP regression (Hypothesis Loop, DEBUG.md): grasp-execution vs target-selection
     under swap — compare a swap run vs the now-6x-GROUNDED no-swap fetches (clutter/warehouse/courtyard green/blue/red all clean).
  4. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned NL->object
     grounder). CEO-gated ~44r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera in acceptance/capture.py = honest-verify spine; conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed. Reverted R282 (was R281/E78). <- frontier#4.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#4.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R280): gate/token R261..R280 CLEAN; R281 spine touch had NO token → reverted R282, audit-clean. R284..R289 touched NO spine path; rows are pure-append (no CEO/GATE token used).
last_review: R280
