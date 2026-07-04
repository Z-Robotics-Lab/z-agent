# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R282 (E78) — QUARANTINE FIX: reverted R281's unapproved+unverified spine change; requeued eyes-place framing as a SPINE gate; corrected STATUS mislabel.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182; loop treads hygiene+robustness — the real bar is a CEO gate, ~38r unanswered)
last-round: R282 (E78, quarantine-fix). R281 built place-aware verdict-render framing IN vector_os_nano/acceptance/capture.py —
  which loop/check.sh's SPINE regex matches (`acceptance/`), so it is honest-verify-spine semantics = a CEO gate (Inv.1). R281
  crossed it with NO GATE-APPROVED token AND left it "real-face verify pending" → R282's post-check quarantined. Reverted 811c5c8 to
  the blessed baseline (capture.py blob 5dfa1a7; place-aware symbols gone, new test removed); revert is a WIP floor, the RECORD commit
  touches NO spine path so the post-check HEAD~1..HEAD range stays spine-clean. Verified: 0 place-aware symbols remain, capture unit
  32 passed (MemPeak 129M), wake smoke emits VECTOR_VERDICT, quarantine cleared. ROOT: STATUS next#1 had MISLABELED this task
  "NON-gated BUILD/harness" — all of acceptance/ is spine, so any change to WHAT THE VERDICT FRAME SHOWS is CEO-gated. Requeued as gate
  G-282-1 (SPINE); LESSONS Refuted line added (E78). Extra honesty risk in the reverted design: camera-aim was conditioned on the place
  GT oracle → a deliberate CEO review is owed before it can ship, and it was never verified on the real face.
frontier: (1) The break@12 arm of the degenerate-spin guard has NEVER fired on a REAL sim thrash (unit-only); a MODE=seq/place run whose
  brain dodges via off-goal re-reads would catch it live — opportunistic, non-deterministic to induce. (2) The verify moat stays WITNESS-ONLY
  and the 2nd witness (gemma4:e4b vlm-judge) is NON-DETERMINISTIC (PASS↔ABSTAIN run-to-run) — a TRUSTED discriminator needs a stronger VLM
  (funded qwen3-vl / better local) = billing/owner. (3) eyes verdict-render off-centers the shelf on PLACE turns → workspace_in_frame=no/ABSTAIN
  false-neg; a framing fix would unblock eyes-place corroboration BUT lives in acceptance/=spine → now a CEO gate (G-282-1), not a build.
watch: Real-face recipe: bare vcli + NL; FORCE deepseek provider + deepseek-v4-flash via env (.env defaults qwen, ARREARAGE);
  local ollama gemma4:e4b eyes+judge AUTO-routed by repl_accept (do NOT set VLM/JUDGE url). Interpreter: `.venv/bin/python` (systemd
  scope has NO `python` on PATH — a bare `python` fails 'No such file'). tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG>
  <MODE={fetch|place|combo|seq|quantity}>; RUN under `systemd-run --user --scope -p MemoryMax=24G`; fetch ~5min, place ~10min,
  seq ~20-25min → BACKGROUND+poll (adopt next round if it outlives the deadline). Sim is IN-PROCESS python (pgrep the TAG; NEVER
  pkill mujoco). LEDGER: append <=1KB/row (em-dash=3 bytes, Chinese chars cost — trim to fit), string field <=280 chars (Python len),
  never rewrite a COMMITTED row. board.py WRITES BOARD.md itself — run `python3 loop/board.py` (NO shell redirect; corrupts line 1).
next:
  1. [NON-gated VERIFY] Re-confirm the OLDEST ⚠STALE BOARD bar on the real face (fetch.nl-ordinal-position-invariance age71, or the
     warehouse family age41-43) — a stale green is worse than a known red; keeps the moat honest between reviews. Real-face, deepseek forced.
  2. [NON-gated VERIFY, opportunistic] Catch the E76 goal-aware break@12 FIRING live on a real MODE=seq/place thrash
     (non-deterministic; do NOT force). Else keep re-confirming the no-regression smoke each review.
  3. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment, BYO URDF+manifest, one
     generic driver) OR D182 (world-owned NL→object grounder). CEO-gated ~38r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera (frame robot+receptacle on a place) lives in acceptance/capture.py = honest-verify spine; also conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed before it ships. Reverted R282 (was R281/E78). <- frontier#3.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#3.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#3.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING brain + qwen3-vl JUDGE both Arrearage; a STRONGER local/funded VLM judge would fix R272 non-determ) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R280): gate/token R261..R280 CLEAN; R281 spine touch had NO token → NOT an approval (reverted R282), audit-clean.
last_review: R280
