# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R284 (E79) — oldest ⚠STALE bar REFUTED-provisional on the real face: fetch.nl-ordinal-position-invariance (age73) did NOT reproduce, N=2 both verified=False.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182 ~39r unanswered; loop treads hygiene+robustness — a skeptic re-verify just caught a REAL rot).
last-round: R284 (E79, VERIFY). Closed R283's dead ord-posinv inflight (died mid-FETCH, no verdict). Re-verified the OLDEST stale BOARD bar
  fetch.nl-ordinal-position-invariance (confirmed R210/E44 GROUNDED 2/2, age73) on the real face, deepseek forced, SCENE_SWAP=1. Result: N=2,
  BOTH verified=False. run1 RAN 0/10, holding_object UNCAUSED every probe, verdict frame = arm raised EMPTY gripper, bottles still on box. run2
  RAN 0/3: target holding_object('pickable_bottle_blue') showed actor=CAUSED but no ✓ (grasped-then-not-held/transient); robot ended holding a
  YELLOW bottle aloft = WRONG object. Deterministic, not flaky. Brain routed perception_grasp(最左边的瓶子) correctly BOTH runs → the ordinal
  RESOLUTION is intact (blue=leftmost-under-swap momentarily CAUSED); the grasp EXECUTION / stable-hold / target-selection is the failure.
  Eyes vlm-judge FAIL (workspace_in_frame=no) both runs but that is RECORDED-only (repl_accept L232: witness never alters verified=), so it did
  NOT cause the 0/N — the GT verdict line + two verdict frames are the proof. A stale green is worse than a known red: the "confirmed" board status
  was misleading. Banked provisional acceptance row (RAN 0/2) → BOARD flipped off the stale-green + E79 experiments row. This validates the
  skeptic re-verify cadence: the OTHER stale fetch bars (courtyard/warehouse families age38-46) may have silently rotted the same way.
frontier: (1) The stale-green re-verify caught a REAL regression on the FIRST bar tried → the confirmed-⚠STALE fetch families
  (courtyard/warehouse, 8 bars age38-46) are now SUSPECT; sweep them before trusting the board. (2) verify moat stays WITNESS-ONLY; 2nd
  witness gemma4:e4b is NON-DETERMINISTIC — a TRUSTED discriminator needs a funded/stronger VLM (billing/owner). (3) eyes verdict-render
  off-centers the workspace on some turns → workspace_in_frame=no ABSTAIN/FAIL false-neg; framing fix lives in acceptance/=spine → gate G-282-1.
watch: Real-face recipe: bare vcli + NL; FORCE deepseek + deepseek-v4-flash via env (.env defaults qwen ARREARAGE; `set -a; . ./.env; set +a`
  to load DEEPSEEK_API_KEY); export VECTOR_SCENE_SWAP=1 for the ordinal swap. local ollama gemma4:e4b eyes+judge AUTO-routed (do NOT set
  VLM/JUDGE url). Interpreter `.venv/bin/python` (systemd scope has NO bare `python`). tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG>
  <MODE={fetch|place|combo|seq|quantity}>; RUN under `systemd-run --user --scope -p MemoryMax=24G`; fetch ~5min. Sim is IN-PROCESS python
  (repl_accept tears down on exit; pgrep the TAG; NEVER pkill mujoco). LEDGER: <=1KB/row, string field <=280 chars (Python len; Chinese chars
  cost 1 char but 3 bytes — trim to fit BOTH). board.py WRITES BOARD.md itself — run `python3 loop/board.py` (NO shell redirect).
next:
  1. [ORIENT §1b, next-round promotion] Adjudicate R284/E79 provisional → append a `refuted` acceptance row for
     fetch.nl-ordinal-position-invariance with `supersedes: R210`, and add ONE docs/LESSONS.md refuted line (E79). Do NOT do it the same round.
  2. [NON-gated VERIFY, high value] SWEEP the other confirmed-⚠STALE fetch bars (courtyard/warehouse families age38-46, fetch.nl-scene-clutter
     age56, g1.* age58-67) on the real face — the ord-posinv rot means the board is untrustworthy. Refute/re-confirm each with a fresh row.
  3. [NON-gated DEBUG, optional] Root-cause the ord grasp-execution regress via Hypothesis Loop (DEBUG.md): is it deepseek-v4-flash
     target-selection drift (grabbed yellow), or a perception_grasp grasp-stability regress? Compare vs a still-GROUNDED fetch (plain-colour age23).
  4. [OWNER GATE — ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment BYO URDF+manifest, one generic driver) OR D182 (world-owned
     NL→object grounder). CEO-gated ~39r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-282-1 SPINE (eyes-place framing): place-aware verdict-render camera lives in acceptance/capture.py = honest-verify spine; also conditions camera-aim on the place GT oracle → deliberate CEO review + real-face verify owed before it ships. Reverted R282 (was R281/E78). <- frontier#3.
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#4.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING + qwen3-vl JUDGE both Arrearage; a STRONGER local/funded VLM judge would fix R272 non-determ) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R280): gate/token R261..R280 CLEAN; R281 spine touch had NO token → reverted R282, audit-clean. R284 touched NO spine path.
last_review: R280
