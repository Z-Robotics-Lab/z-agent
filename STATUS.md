# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R285 (E80) — §1b promoted R284's ord-posinv rot to REFUTED; SWEPT 2 stale fetch bars on the real face → BOTH re-confirm → rot is SCENE_SWAP-specific, not a systemic grasp regression.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~40r unanswered; loop treads hygiene+robustness — skeptic sweep de-risking the board after R284's real rot).
last-round: R285 (E80, VERIFY). (1) §1b promotion: appended a `refuted` acceptance row for fetch.nl-ordinal-position-invariance (supersedes:R210)
  + one LESSONS refuted line (R284/E79 N=2 both verified=False, already boundary-survived). (2) SWEEP (next#2) of the stale fetch bars R284's rot
  made SUSPECT: re-verified fetch.nl-scene-clutter (age56, HOUSE, plain green, no swap) AND fetch.nl-new-world-warehouse (age46, world-transfer)
  on the bare vcli face, deepseek forced, local-ollama eyes. BOTH GROUNDED 1/1, holding_object(green) actor=CAUSED, eyes vlm-judge PASS. Warehouse
  frame UNAMBIGUOUS: green bottle held aloft, magenta/yellow/blue REMAIN = discrimination. FINDING: plain green grasp GROUNDS clean in 2 worlds →
  grasp EXECUTION is NOT generally regressed; R284's ord-posinv 0/2 is SCENE_SWAP-specific (target-select / stable-hold under swap). Banked 2
  provisional GROUNDED rows (supersedes R228/R238) + E80. Board: ord-posinv→refuted; scene-clutter+warehouse stale flags cleared (age0 provisional).
frontier: (1) Sweep is de-risking the board, 2/2 re-confirm → R284's systemic-rot fear easing; finish the remaining stale fetch/g1 bars (courtyard
  age38-41, g1.* age58-67, quantity age75-79) before fully trusting the board, but expect holds. (2) ord-posinv SCENE_SWAP regression is now a
  bounded ISOLATED DEBUG target (grasp-exec/target-select under swap) — worth a Hypothesis Loop. (3) verify moat stays WITNESS-ONLY; a TRUSTED 2nd
  discriminator needs a funded/stronger VLM (billing/owner). (4) eyes verdict-render off-centers workspace on some turns → spine gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE the deepseek provider+model via env (default is qwen = Arrearage → PREFLIGHT BLOCKED; see .env.example
  / repl_accept.py header); `set -a; . ./.env; set +a` loads DEEPSEEK_API_KEY. World knobs: SCENE_CLUTTER=1 (house+distractors), ROOM_TEMPLATE=
  {warehouse|courtyard}, SCENE_SWAP=1 (ordinal swap) — all `VECTOR_`-prefixed. local ollama gemma4:e4b eyes+perception-VLM AUTO-routed (do NOT set
  VLM/JUDGE url). Interpreter `.venv/bin/python` (systemd scope has NO bare `python`). repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo|
  seq|quantity}>; RUN under `systemd-run --user --scope -p MemoryMax=24G`; fetch ~4min. Sim IN-PROCESS python (tears down on exit; pgrep the TAG;
  NEVER pkill mujoco). LEDGER: <=1KB/row, string field <=280 chars PYTHON len (Chinese char = 1 char/3 bytes; redteam is the usual over-run). board.py
  WRITES BOARD.md itself — run `.venv/bin/python loop/board.py` (NO redirect).
next:
  1. [ORIENT §1b, next-round promotion] Adjudicate the 2 R285/E80 provisionals → `confirmed` rows for fetch.nl-scene-clutter (supersedes R228) and
     fetch.nl-new-world-warehouse (supersedes R238) if still reproducible. Do NOT do it the same round.
  2. [NON-gated VERIFY] CONTINUE the sweep of remaining stale bars: courtyard fetch family (age38-41), g1.navigation/g1.perception (age58-67),
     quantity-place.nl (age75-79). 2/2 re-confirmed so far → expect holds, but a stale-green is worse than a known red. Refute/re-confirm each.
  3. [NON-gated DEBUG, bounded] Root-cause the ISOLATED ord-posinv SCENE_SWAP regression (Hypothesis Loop, DEBUG.md): grasp-execution vs
     target-selection under swap — compare a swap run vs a still-GROUNDED no-swap fetch (scene-clutter/warehouse both clean this round).
  4. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned
     NL→object grounder). CEO-gated ~40r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera in acceptance/capture.py = honest-verify spine; conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed. Reverted R282 (was R281/E78). <- frontier#4.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#4.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R280): gate/token R261..R280 CLEAN; R281 spine touch had NO token → reverted R282, audit-clean. R284/R285 touched NO spine path.
last_review: R280
