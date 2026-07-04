# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R286 (E81, DEBUG) — cleared R285 quarantine: acceptance+experiments.jsonl append-only breach was a REORDER, not data loss (0 rows lost); fixed by pure-append per the E27 lesson (leave reordered files, do NOT restore).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~41r unanswered; loop treads hygiene+robustness — R285 sweep de-risking the board after R284's real rot).
last-round: R286 (E81, DEBUG — breach fix). Preflight FAILED on loop/.state/quarantine: R285/605281a flagged append-only deletions in acceptance.jsonl
  + experiments.jsonl. OBSERVE: git status clean bar a rounds.jsonl append; line-counts GREW (132→135, 103→104) so no net truncation. HYP: erased vs
  reordered. EXPERIMENT: normalized-JSON set-diff R284(f44140c) vs HEAD(605281a) → 0 rows missing both files, 3 acc + 1 exp rows legitimately R285-added.
  CONCLUDE: R285 rewrote the ledgers in place (json.dumps load-all→write-all) instead of `>>` append, breaking the byte-prefix the numstat append-only gate
  needs — an EXACT recurrence of the E27 lesson (LESSONS:59). FIX per E27 ("do NOT restore, a 2nd rewrite compounds; leave + document"): kept R285's
  reordered files as the new baseline, appended only the E81 row + regen BOARD + cleared quarantine → this commit is PURE APPEND (0 ledger deletions vs
  HEAD~1), no CEO token needed. No verdict was lost; the round did no new acceptance work (breach fix owns the round).
frontier: (1) R285 sweep de-risking board: courtyard fetch (age38-41), g1.* (age58-67), quantity-place (age75-79) stale bars still owed before full board
  trust — expect holds (4/4 re-confirmed so far). (2) ord-posinv SCENE_SWAP regression = bounded ISOLATED DEBUG target (grasp-exec vs target-select under
  swap), worth a Hypothesis Loop. (3) verify moat stays WITNESS-ONLY; a TRUSTED 2nd discriminator needs a funded/stronger VLM (billing/owner). (4) eyes
  verdict-render off-centers workspace on some turns → spine gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE deepseek provider+model via env (default qwen = Arrearage → PREFLIGHT BLOCKED; see .env.example /
  repl_accept.py header); `set -a; . ./.env; set +a` loads DEEPSEEK_API_KEY. World knobs (all `VECTOR_`-prefixed): SCENE_CLUTTER=1, ROOM_TEMPLATE=
  {warehouse|courtyard}, SCENE_SWAP=1. local ollama gemma4:e4b eyes+perception-VLM AUTO-routed (do NOT set VLM/JUDGE url). Interpreter `.venv/bin/python`.
  repl_accept.py <FETCH> <PLACE> <TAG> <MODE>; RUN under `systemd-run --user --scope -p MemoryMax=24G`; fetch ~4min. NEVER pkill mujoco. LEDGER HAZARD
  (E27/E81): edit a ledger ONLY by appending ONE preformatted line via `>>` — NEVER load-all→json.dumps→write-all (reorders → append-only gate quarantine);
  if a reorder already shipped, LEAVE it + pure-append fix, do NOT restore. Row caps: <=1KB, string field <=280 chars PYTHON len. board.py WRITES BOARD.md
  itself — run `.venv/bin/python loop/board.py` (NO redirect).
next:
  1. [ORIENT §1b, next-round promotion] Adjudicate the 2 R285/E80 provisionals → `confirmed` rows for fetch.nl-scene-clutter (supersedes R228) and
     fetch.nl-new-world-warehouse (supersedes R238) if still reproducible. Do NOT do it the same round they were measured.
  2. [NON-gated VERIFY] CONTINUE the sweep of remaining stale bars: courtyard fetch family (age38-41), g1.navigation/g1.perception (age58-67),
     quantity-place.nl (age75-79). 4/4 re-confirmed so far → expect holds, but a stale-green is worse than a known red. Refute/re-confirm each.
  3. [NON-gated DEBUG, bounded] Root-cause the ISOLATED ord-posinv SCENE_SWAP regression (Hypothesis Loop, DEBUG.md): grasp-execution vs
     target-selection under swap — compare a swap run vs a still-GROUNDED no-swap fetch (scene-clutter/warehouse both clean R285).
  4. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned
     NL→object grounder). CEO-gated ~41r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera in acceptance/capture.py = honest-verify spine; conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed. Reverted R282 (was R281/E78). <- frontier#4.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#4.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R280): gate/token R261..R280 CLEAN; R281 spine touch had NO token → reverted R282, audit-clean. R284/R285/R286 touched NO spine path; R286 fix is pure-append (no CEO/GATE token used).
last_review: R280
