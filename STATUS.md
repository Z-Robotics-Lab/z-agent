# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-04 · R290 (E83, REVIEW) — skeptic re-confirmed the last stale courtyard sibling + promoted R289 red; PLATEAU call: courtyard sweep exhausted, pivot owed.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~45r unanswered; loop treads stale-bar hygiene — courtyard fetch sweep now EXHAUSTED green/blue/red/purple all re-confirmed).
last-round: R290 (E83, review). §1b PROMOTE R289 courtyard-red prov -> confirmed. §7 SKEPTIC: re-ran the last stale courtyard sibling fetch.nl-new-world-courtyard-purple
  (age44, R246 N=2, novel BOX geom) on the bare face -> GROUNDED 1/1 holding_object(pickable_box_purple) actor=CAUSED, eyes vlm-judge PASS; FRAME: purple box aloft,
  green/yellow/blue/red REMAIN=colour+geometry discrimination. 7th sweep bar re-confirmed. Gate/token R280-R290 CLEAN; WIRING all <=20r fresh; Casebook 14/15; LESSONS at 260 cap.
frontier: PIVOT (R290 plateau call, LESSONS AMBITION CRITIC): courtyard fetch sweep EXHAUSTED — a 7th sibling adds ZERO capability. Aim remaining hygiene at the genuinely-oldest
  UNTESTED bars: g1.navigation (age73, reachable-coords hazard E49, run BACKGROUND >10min) · g1.perception (age65) · quantity-place.nl (age85, brain-decompose flaky E72). Each a
  dedicated round. (2) ord-posinv SCENE_SWAP regression = bounded ISOLATED DEBUG target (grasp-exec vs target-select under swap). (3) verify moat stays WITNESS-ONLY; a TRUSTED
  2nd discriminator needs a funded/stronger VLM (local gemma4:e4b PASS/ABSTAIN non-determ E71, recorded-not-trusted). (4) eyes verdict-render off-centers workspace -> gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE the deepseek provider + v4-flash model via the env-select vars documented in .env.example (default qwen = Arrearage -> PREFLIGHT
  BLOCKED); provider-select syntax + key live ONLY in .env.example; `set -a; . ./.env; set +a` loads it. World knobs (all `VECTOR_`-prefixed): SCENE_CLUTTER=1, ROOM_TEMPLATE={warehouse|courtyard}, SCENE_SWAP=1. local
  ollama gemma4:e4b eyes+perception-VLM AUTO-routed (do NOT set VLM/JUDGE url; ABSTAIN is fail-closed, LOOK at the frame yourself). Harness `.venv/bin/python tools/acceptance/
  repl_accept.py <FETCH> <PLACE> <TAG> fetch`; RUN under `systemd-run --user --scope -p MemoryMax=24G`; fetch ~4min. Set VECTOR_EVIDENCE_DIR=var/evidence/R$N/<tag> per run
  (else 2 runs collide, E54). HAZARD: the Bash-tool default timeout is 120s — set the tool `timeout` ~600000 or the fetch is SIGTERM'd mid-run. NEVER pkill mujoco — scripts/
  sim-teardown. LEDGER HAZARD (E27/E81): append ONE preformatted line via `>>` — NEVER load-all->json.dumps->write-all (reorders -> quarantine). Row caps: <=1KB, string <=280 chars
  PYTHON len (INCL redteam/result — if the python assert fires, `$ROW` is EMPTY and `echo >>` appends a BLANK line: strip it then re-append shorter); confirmed rows' `redteam` MUST
  start with 'survived'; acceptance rows MUST include `evidence`. board.py WRITES BOARD.md — run `.venv/bin/python loop/board.py` (NO redirect); supervisor's post-round rounds.jsonl
  append shifts BOARD ages so the NEXT round must regen it.
next:
  1. [PIVOT — NON-gated VERIFY, break the local hill] Re-verify the genuinely-oldest UNTESTED stale bar, NOT another courtyard sibling: g1.navigation (age73, deepseek-v4-flash,
     REACHABLE probe-checked coords per E49, g1_accept RED+GREEN >10min so run BACKGROUND — foreground SIGTERMs mid-GREEN + orphans the g1 sim). Refute or re-confirm with a fresh row.
  2. [NON-gated VERIFY, after #1] Then g1.perception (age65, world-config hardened E50) and quantity-place.nl (age85, brain-decompose flaky — expect a thrash, an honest RAN is a valid row).
  3. [NON-gated DEBUG, bounded] Root-cause the ISOLATED ord-posinv SCENE_SWAP regression (Hypothesis Loop, DEBUG.md): grasp-execution vs target-selection under swap — compare a
     swap run vs the now-7x-GROUNDED no-swap fetches (clutter/warehouse/courtyard green/blue/red/purple all clean).
  4. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned NL->object grounder). CEO-gated ~45r.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera in acceptance/capture.py = honest-verify spine; conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed. Reverted R282 (was R281/E78). <- frontier#4.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#4.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R290): gate/token R280..R290 CLEAN — R281 spine touch had NO token -> reverted R282 (audit-clean); R284..R290 touched NO spine path, rows pure-append (no CEO/GATE token used).
last_review: R290
