# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-04 · R292 (E85, build) — §1b promoted g1.navigation R291/E84 provisional -> confirmed 2/2; then PIVOT next#2: re-verified stale g1.perception (age66) on the real face -> GROUNDED 1/1.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~47r unanswered; loop working DOWN the R290-named oldest-untested-bar backlog — 2 of 3 refreshed: g1.nav R291 ✓, g1.perception R292 ✓; quantity-place remains).
last-round: R292 (E85, build). §1a adopted R291 rounds append + regen BOARD. §1b promoted g1.navigation R291/E84 (clean 2/2 at probe-verified reachable non-memorized coords) -> confirmed, survived boundary + red-team,
  no counter-evidence (supersedes R217 1/2 lineage). Then next#2: re-verified the age66 stale g1.perception bar (R225/E50 confirmed N=3) on the bare vcli+NL real face, forced deepseek-v4-flash, VECTOR_NO_ROS2=1
  in-process, systemd-run MemoryMax=24G, BACKGROUND. RED 找红色 GROUNDED verified=True 1/1 vs seg-GT centroid oracle (RGB-firewalled, unauthorable); GREEN 找绿色 RAN False = honest-negative (not in head-cam view)
  -> discriminates; launch_explore_seen=False. Stale bar REFRESHED not rotted. Provisional row banked (promote R293 per §1c). sim torn down via scripts/sim-teardown (killed 1 residual child), tree clean.
frontier: PIVOT (R290 plateau call) nearly DONE — worked DOWN the oldest-untested bars: g1.navigation (2/2 R291) ✓ · g1.perception (1/1 R292) ✓ · REMAINING: quantity-place.nl (age87, brain-decompose flaky E72 — expect
  thrash, honest RAN is a valid row). AFTER that the backlog is exhausted and R290's conclusion re-asserts: only owner S4/D182 advances NEW capability; more colours/worlds is a LOCAL HILL. Then: (2) ord-posinv
  SCENE_SWAP regression = bounded ISOLATED DEBUG. (3) verify moat stays WITNESS-ONLY (gemma4:e4b PASS/ABSTAIN non-determ E71, recorded-not-trusted; a TRUSTED 2nd discriminator needs a funded/stronger VLM). (4) eyes verdict-render off-centers workspace -> gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE the deepseek provider + v4-flash model via the env-select vars documented in .env.example (default qwen = Arrearage -> PREFLIGHT BLOCKED); provider-select syntax +
  keys live ONLY in .env.example / .env (`set -a; . ./.env; set +a` loads it). World knobs (all `VECTOR_`-prefixed): SCENE_CLUTTER=1, ROOM_TEMPLATE={warehouse|courtyard}, SCENE_SWAP=1.
  G1 recipe: g1_accept.py = PERCEPTION axis (RED detect vs seg-GT oracle, GREEN honest-negative; emits NO png -> eyes=seg-GT self-read; ~8-9min so BACKGROUND). g1_nav_accept.py = NAV axis (OFFLINE-probe reachability
  FIRST via scratchpad/g1_reach_probe.py, then demand coords via G1_NAV_A/G1_NAV_B; walks 4-6min/leg BACKGROUND). Both: VECTOR_NO_ROS2=1 in-process, launch_explore MUST stay empty. RUN under
  `systemd-run --user --scope -p MemoryMax=24G`; stdout -> var/evidence/R$N/. local ollama gemma4:e4b eyes AUTO-routed (do NOT set VLM/JUDGE url; ABSTAIN=fail-closed, LOOK at the frame yourself).
  HAZARD: Bash-tool default timeout 120s — foreground polling dies at 120s; run sim BACKGROUND + read the evidence log. NEVER pkill mujoco — scripts/sim-teardown. LEDGER HAZARD (E27/E81): append ONE preformatted
  line via `>>` — NEVER load-all->json.dumps->write-all (reorders -> quarantine). Row caps: <=1KB (JSON bytes), string <=280 chars PYTHON len (INCL redteam/result — if the python assert fires, NOTHING is appended,
  trim `note` and re-run); confirmed rows' `redteam` MUST start with 'survived'; acceptance rows MUST include `evidence`. board.py WRITES BOARD.md — run `.venv/bin/python loop/board.py` (NO redirect); the supervisor's
  post-round rounds.jsonl append shifts BOARD ages so the NEXT round MUST regen it.
next:
  1. [§1b ADJUDICATE — next-round promotion per §1c] Promote the R292/E85 g1.perception provisional (GROUNDED 1/1, RED vs seg-GT + GREEN honest-negative) -> confirmed IF it survives the R292->R293 boundary +
     red-team (RED still grounds, GREEN still refuses, no counter-evidence); else refuted/superseded. supersedes R225 g1.perception confirmed (E50).
  2. [PIVOT VERIFY — LAST oldest-untested bar] quantity-place.nl (age87, brain-decompose flaky E72 — expect a thrash; an honest RAN is a valid row, not a failure). deepseek-v4-flash, MODE=seq/quantity, BACKGROUND.
     After this the R290-named backlog is EXHAUSTED — re-assert R290's plateau: only owner S4/D182 advances NEW capability.
  3. [NON-gated DEBUG, bounded] Root-cause the ISOLATED ord-posinv SCENE_SWAP regression (Hypothesis Loop, DEBUG.md): grasp-execution vs target-selection under swap vs the 8x-GROUNDED no-swap fetches.
  4. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned NL->object grounder). CEO-gated ~47r.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera in acceptance/capture.py = honest-verify spine; conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed. Reverted R282 (was R281/E78). <- frontier#4.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#4.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R290): gate/token R280..R290 CLEAN. R291+R292 touched NO spine path; rows pure-append (no CEO/GATE token used).
last_review: R290
