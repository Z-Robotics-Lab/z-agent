# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-04 · R291 (E84, build) — PIVOT executed: re-verified the genuinely-OLDEST untested stale bar g1.navigation on the real face -> clean GROUNDED 2/2 (was 1/2, 73r stale).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~46r unanswered; loop now working DOWN the oldest-untested-bar backlog the R290 plateau call named — 1 of 3 refreshed).
last-round: R291 (E84, build). §1a adopted R290 rounds append + regen BOARD. PIVOT/next#1: broke the courtyard-sibling local hill — re-verified g1.navigation (age73, oldest UNTESTED
  stale bar) on the bare vcli+NL real face. Offline planner-only reachability probe (scratchpad/g1_reach_probe.py) picked TWO probe-verified REACHABLE NON-MEMORIZED legs
  A=(12,3.5) geodesic 2.18 / B=(9,4) geodesic 1.41 — NOT R217's 12,3/11,4, NOT defaults 9,3/10,4; (11,4.5) confirmed inf/blocked (matches E49 (11,3)/(11,4)). g1_nav_accept BACKGROUND
  (deepseek-v4-flash forced, VECTOR_NO_ROS2=1 in-process, MemoryMax=24G): BOTH legs `verdict GROUNDED verified=True` actor=CAUSED at the DEMANDED coords, launch_explore_seen=False.
  Upgrades R217 GROUNDED 1/2 (E49 legB was obstacle-blocked) -> clean 2/2. Provisional row banked, promote next round per §1c. sim torn down via scripts/sim-teardown (rosm), tree clean.
frontier: PIVOT IN PROGRESS (R290 plateau call): stop sweeping courtyard siblings, work DOWN the oldest-untested bars. DONE: g1.navigation (2/2, this round). REMAINING: g1.perception
  (age65, world-config hardened E50, g1_accept RED+GREEN >10min -> BACKGROUND) · quantity-place.nl (age85, brain-decompose flaky E72 — expect thrash, honest RAN is a valid row). Then:
  (2) ord-posinv SCENE_SWAP regression = bounded ISOLATED DEBUG target (grasp-exec vs target-select under swap). (3) verify moat stays WITNESS-ONLY; a TRUSTED 2nd discriminator needs a
  funded/stronger VLM (local gemma4:e4b PASS/ABSTAIN non-determ E71, recorded-not-trusted). (4) eyes verdict-render off-centers workspace -> gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE the deepseek provider + v4-flash model via the env-select vars documented in .env.example (default qwen = Arrearage -> PREFLIGHT
  BLOCKED); provider-select syntax + key live ONLY in .env.example; `set -a; . ./.env; set +a` loads it. World knobs (all `VECTOR_`-prefixed): SCENE_CLUTTER=1, ROOM_TEMPLATE={warehouse|courtyard}, SCENE_SWAP=1.
  G1 NAV recipe: OFFLINE-probe reachability FIRST (scratchpad/g1_reach_probe.py: loads MuJoCoG1, plan_path per candidate, finite geodesic + >0.5m tol = reachable — NO walk, ~30s) THEN
  demand those coords via G1_NAV_A/G1_NAV_B; g1_nav_accept walks each leg ~4-6min so RUN BACKGROUND (foreground SIGTERMs mid-walk). local ollama gemma4:e4b eyes+perception-VLM AUTO-routed
  (do NOT set VLM/JUDGE url; ABSTAIN is fail-closed, LOOK at the frame yourself). Harness `.venv/bin/python tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG> fetch`; RUN under
  `systemd-run --user --scope -p MemoryMax=24G`. Set VECTOR_EVIDENCE_DIR=var/evidence/R$N/<tag> per run (else 2 runs collide, E54). HAZARD: Bash-tool default timeout 120s — foreground
  polling loops die at 120s; run the sim BACKGROUND + read the evidence log. NEVER pkill mujoco — scripts/sim-teardown. LEDGER HAZARD (E27/E81): append ONE preformatted line via `>>` —
  NEVER load-all->json.dumps->write-all (reorders -> quarantine). Row caps: <=1KB, string <=280 chars PYTHON len (INCL redteam/result — if the python assert fires, `$ROW` is EMPTY and
  `echo >>` appends a BLANK line: strip it then re-append shorter); confirmed rows' `redteam` MUST start with 'survived'; acceptance rows MUST include `evidence`. board.py WRITES BOARD.md —
  run `.venv/bin/python loop/board.py` (NO redirect); supervisor's post-round rounds.jsonl append shifts BOARD ages so the NEXT round must regen it.
next:
  1. [§1b ADJUDICATE — next-round promotion per §1c] Promote the R291/E84 g1.navigation provisional (clean GROUNDED 2/2) -> confirmed IF it survives the R291->R292 boundary + red-team
     (still reproducible, no counter-evidence); else refuted/superseded row. supersedes R217 g1.navigation 1/2 confirmed.
  2. [PIVOT VERIFY — next oldest untested bar] Re-verify g1.perception (age65, world-config hardened E50/R225, deepseek-v4-flash) on the bare face. g1_accept RED+GREEN >10min so BACKGROUND.
  3. [PIVOT VERIFY] quantity-place.nl (age85, brain-decompose flaky E72 — expect a thrash; an honest RAN is a valid row, not a failure of the round).
  4. [NON-gated DEBUG, bounded] Root-cause the ISOLATED ord-posinv SCENE_SWAP regression (Hypothesis Loop, DEBUG.md): grasp-execution vs target-selection under swap vs the 8x-GROUNDED no-swap fetches.
  5. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned NL->object grounder). CEO-gated ~46r.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera in acceptance/capture.py = honest-verify spine; conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed. Reverted R282 (was R281/E78). <- frontier#4.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#5.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#5.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R290): gate/token R280..R290 CLEAN. R291 touched NO spine path; rows pure-append (no CEO/GATE token used).
last_review: R290
