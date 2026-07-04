# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-04 · R287 (E82, VERIFY) — cleared preflight breach + promoted 2 R285 provisionals + 3rd sweep bar re-confirms on the real face.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~42r unanswered; loop treads stale-bar sweep hygiene — 3/3 fetch bars HOLD this round, only SCENE_SWAP ord-posinv rotted).
last-round: R287 (E82, VERIFY). §1b BREACH: preflight failed on R284 ord-posinv provisional rows (age3) — the R285 refutation was banked (row 133) but its
  `supersedes` named only R210, never R284, so the (cap,R284) age-gate linkage was never satisfied. FIX: appended a `superseded` row naming R284 (no re-run,
  refutation already stands). §1c PROMOTE: R285/E80 provisionals fetch.nl-scene-clutter + fetch.nl-new-world-warehouse (both GROUNDED 1/1 vlm-judge, survived
  R285->R287 boundary, red-team recorded) -> confirmed. §2 SWEEP next#2: re-verified the OLDEST courtyard stale bar fetch.nl-new-world-courtyard (age43,
  R243 GROUNDED 2/2) on the bare vcli+NL real face -> GROUNDED 1/1, holding_object(green) actor=CAUSED, eyes vlm-judge PASS, FRAME(looked) green held aloft +
  pink/blue/yellow distractors REMAIN=discrimination. Stale-green HOLDS. 3rd consecutive sweep bar to re-confirm -> grasp EXECUTION is healthy across worlds;
  the R284 ord-posinv fail stays SCENE_SWAP-isolated (target-select/hold under swap), NOT a systemic rot.
frontier: (1) Continue the sweep of remaining stale bars: courtyard siblings blue/purple/red (age~40-42) cheap; g1.navigation (age71)/g1.perception (age63) +
  quantity-place.nl (age83) harder (embodiment/place-campaign) -> un-pressured rounds. (2) ord-posinv SCENE_SWAP regression = bounded ISOLATED DEBUG target
  (grasp-exec vs target-select under swap). (3) verify moat stays WITNESS-ONLY; a TRUSTED 2nd discriminator needs a funded/stronger VLM (billing/owner).
  (4) eyes verdict-render off-centers workspace on some turns -> spine gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE the deepseek provider+model via env (default qwen = Arrearage -> PREFLIGHT BLOCKED; see .env.example / repl_accept
  header); `set -a; . ./.env; set +a` loads the key. World knobs (all `VECTOR_`-prefixed): SCENE_CLUTTER=1, ROOM_TEMPLATE={warehouse|courtyard}, SCENE_SWAP=1.
  local ollama gemma4:e4b eyes+perception-VLM AUTO-routed (do NOT set VLM/JUDGE url). Interpreter `.venv/bin/python tools/acceptance/repl_accept.py <FETCH>
  <PLACE> <TAG> fetch`; RUN under `systemd-run --user --scope -p MemoryMax=24G`; fetch ~4min. HAZARD: the Bash-tool's OWN default timeout is 120s — set the tool
  `timeout` to ~600000 or the fetch is SIGTERM'd mid-run (kills the whole pgroup incl the scope; verified clean, no orphan). NEVER pkill mujoco. LEDGER HAZARD
  (E27/E81): edit a ledger ONLY by appending ONE preformatted line via `>>` — NEVER load-all->json.dumps->write-all (reorders -> append-only quarantine); if a
  reorder shipped, LEAVE it + pure-append. Row caps: <=1KB, string <=280 chars PYTHON len. confirmed rows: `redteam` MUST start with 'survived'. board.py WRITES
  BOARD.md itself — run `.venv/bin/python loop/board.py` (NO redirect).
next:
  1. [ORIENT §1b, next-round promotion] Adjudicate the R287/E82 courtyard provisional -> `confirmed` (supersedes R243) if still standing. Do NOT do it the same
     round it was measured.
  2. [NON-gated VERIFY] CONTINUE the sweep of remaining stale bars in age order: courtyard siblings (blue/purple/red, age~40-42) are cheap fetch re-verifies;
     THEN the harder/older g1.navigation (age71, reachable-coords hazard E49) + quantity-place.nl (age83, flaky place campaign E36) each get a dedicated round.
     4/4 fetch bars re-confirmed so far (scene-clutter, warehouse, courtyard, + R285x2) -> a stale-green is worse than a known red; refute/re-confirm each.
  3. [NON-gated DEBUG, bounded] Root-cause the ISOLATED ord-posinv SCENE_SWAP regression (Hypothesis Loop, DEBUG.md): grasp-execution vs target-selection
     under swap — compare a swap run vs the now-3x-GROUNDED no-swap fetches (courtyard/clutter/warehouse all clean).
  4. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned NL->object
     grounder). CEO-gated ~42r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera in acceptance/capture.py = honest-verify spine; conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed. Reverted R282 (was R281/E78). <- frontier#4.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#4.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R280): gate/token R261..R280 CLEAN; R281 spine touch had NO token → reverted R282, audit-clean. R284..R287 touched NO spine path; R286 fix + R287 rows are pure-append (no CEO/GATE token used).
last_review: R280
