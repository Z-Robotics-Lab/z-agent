# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R280 (E77 REVIEW) — oldest stale bar re-confirmed on the real face; E76 no-regr adjudicated confirmed; janitor pass clean.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182; loop treads hygiene+robustness — the real bar is a CEO gate, ~36r unanswered)
last-round: R280 (E77 REVIEW, non-gated). Skeptic re-ran the oldest non-flaky stale-confirmed bar
  fetch.nl-novel-geometry-purple-box (age64, R215 N=3) on the current v4-flash+local-gemma4:e4b seam → GROUNDED 1/1,
  holding_object(box_purple) actor=CAUSED, eyes purple box aloft / blue+green+yellow bottles + red can remain=discrimination,
  vlm-judge PASS (workspace_in_frame=yes — a rare clean gemma4:e4b PASS, eyes upgraded self-read→vlm-judge). E76 no-regression
  ADJUDICATED confirmed across the R279→R280 boundary: the goal-aware degenerate-spin reset stayed SILENT (0 spin/nudge markers)
  on the healthy fetch = no false-break. Janitor: WIRING native-loop restamped (6834860 R260 → 2406411) + spin-guard/goal-aware
  bullet; LESSONS merged E75/E76 and fixed the _MAX_NATIVE_TURNS 63→24 rot (260/260 cap); evidence pruned <R260; re-red-team of
  R278/E75 'guard fires on a REAL thrash' SURVIVES (nudge>0/break=0, honest RAN, break arm honestly unit-only); gate/token R261..R280 CLEAN.
frontier: (1) The break@12 arm of the degenerate-spin guard has NEVER fired on a REAL sim thrash (unit-only); a MODE=seq/place run whose
  brain dodges via off-goal re-reads would catch it live — opportunistic, non-deterministic to induce. (2) The verify moat stays WITNESS-ONLY
  and the 2nd witness (gemma4:e4b vlm-judge) is NON-DETERMINISTIC (PASS↔ABSTAIN run-to-run) — a TRUSTED discriminator needs a stronger VLM
  (funded qwen3-vl / better local) = billing/owner. (3) The offscreen eyes verdict-render off-centers the shelf on PLACE turns → workspace_in_frame=no/ABSTAIN false-neg; a cheap camera/render-framing fix unblocks eyes-place corroboration.
watch: Real-face recipe: bare vcli + NL; FORCE deepseek provider + deepseek-v4-flash via env (.env defaults qwen, ARREARAGE);
  local ollama gemma4:e4b eyes+judge AUTO-routed by repl_accept (do NOT set VLM/JUDGE url). Interpreter: `.venv/bin/python` (systemd
  scope has NO `python` on PATH — a bare `python` fails 'No such file'). tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG>
  <MODE={fetch|place|combo|seq|quantity}>; RUN under `systemd-run --user --scope -p MemoryMax=24G`; fetch ~5min, place ~10min,
  seq ~20-25min → BACKGROUND+poll (adopt next round if it outlives the deadline). Sim is IN-PROCESS python (pgrep the TAG; NEVER
  pkill mujoco). LEDGER: append <=1KB/row (em-dash=3 bytes, Chinese chars cost — trim to fit), string field <=280 chars (Python len),
  never rewrite a COMMITTED row. board.py WRITES BOARD.md itself — run `python3 loop/board.py` (NO shell redirect; corrupts line 1).
next:
  1. [NON-gated BUILD/harness] Fix the eyes verdict-render framing so the workspace (shelf/bin) is in-frame on PLACE turns →
     the vlm-judge can corroborate a place instead of workspace_in_frame=no/ABSTAIN false-neg. Cheap, unblocks eyes-place.
  2. [NON-gated VERIFY, opportunistic] Catch the E76 goal-aware break@12 FIRING live on a real MODE=seq/place thrash
     (non-deterministic; do NOT force). Else keep re-confirming the no-regression smoke each review.
  3. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment, BYO URDF+manifest, one
     generic driver) OR D182 (world-owned NL→object grounder). CEO-gated ~36r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#3.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#3.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING brain + qwen3-vl JUDGE both Arrearage; a STRONGER local/funded VLM judge would fix R272 non-determ) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R280): gate/token R261..R280 CLEAN (no GATE/CEO-APPROVED crossings; last was R187, audited clean R209).
last_review: R280
