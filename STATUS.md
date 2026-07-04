# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R278 (E75 VERIFY) — adopted R275-seq inflight; guard fires on a REAL thrash CONFIRMED.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182; frontier = guard goal-awareness + eyes-frame workspace framing)
last-round: R278 (E75 VERIFY, non-gated). Cleared the R275->R277 stuck quarantine cycle: adopted the
  R275 MODE=seq inflight run (had outlived R276/R277 un-adopted), regenerated BOARD, adjudicated the two
  >2-round-old R274 provisionals. The seq run COMPLETED and DELIVERED next#1: turn1 place-blue thrashed
  w/o verifying -> the R274 degenerate-spin guard NUDGED (log 'native re-prompting: measure progress') ->
  brain issued verify holding_object -> honest RAN verified=False, NO 24-turn/~15min burn (eyes_seq1: empty
  gripper facing shelf). Upgrades R274's UNIT-only claim to REAL-face observed. turn2 place-red GT-grounded
  True(1/1) clean (guard non-regressive on the healthy turn). eyes vlm-judge FIRED non-empty on BOTH place
  turns (judge_witness.log) = E70 wiring reproduced. Adjudicated: E74 runner.degenerate-spin-guard +
  E70 verify.eyes-vlm-judge-place -> confirmed (supersedes R274). FINDINGS below.
frontier: (1) The guard's turns-since-verify counter resets on ANY verify — turn2 interspersed an OFF-GOAL
  `verify at_position` that reset it, so hard-break@12 stays UNOBSERVED and worst-case turns fall to the
  _MAX_NATIVE_TURNS(63) cap; a GOAL-AWARE counter (reset only on a verify of the actual goal predicate) is
  the refinement. (2) The offscreen eyes verdict-render off-centers the shelf -> vlm-judge workspace_in_frame=no
  false-negs on BOTH place turns, incl seq2 which GT-grounded True — the judge fires but its verdict is a
  framing artifact (weak gemma4:e4b + off-center frame). ROOT causes stay owner/billing (stronger VLM + brain).
watch: Real-face recipe: bare vcli + NL; FORCE deepseek provider + deepseek-v4-flash via env (.env defaults
  qwen, ARREARAGE); local ollama gemma4:e4b eyes+judge AUTO-routed by repl_accept (do NOT set VLM/JUDGE url).
  tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo|seq|quantity}>. RUN under
  `systemd-run --user --scope -p MemoryMax=24G`; place ~10min, seq ~20-25min -> BACKGROUND+poll (adopt next
  round if it outlives the deadline). Sim is IN-PROCESS python (pgrep the TAG; NEVER pkill mujoco). LEDGER:
  append <=1KB/row, string field <=280 chars (Python len), never rewrite a COMMITTED row. board.py WRITES
  BOARD.md itself — run `python3 loop/board.py` (NO shell redirect; a redirect corrupts line 1).
next:
  1. [NON-gated BUILD] GOAL-AWARE degenerate-spin guard: reset the turns-since-verify counter only on a verify
     of the ACTUAL goal predicate (not any predicate), so an at_position-thrash mode reaches hard-break@12. TDD.
  2. [NON-gated BUILD/harness] Fix the eyes verdict-render framing so the workspace (shelf/bin) is in-frame ->
     the vlm-judge can corroborate a place instead of workspace_in_frame=no false-neg. Cheap, unblocks eyes-place.
  3. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment, BYO URDF+manifest, one
     generic driver) OR D182 (world-owned NL->object grounder). CEO-gated ~34r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#3.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#3.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING brain + qwen3-vl JUDGE both Arrearage; a STRONGER local/funded VLM judge would fix R272 non-determ) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R270): gate/token R261..R278 CLEAN (no GATE/CEO-APPROVED crossings; last was R187, audited clean R209).
last_review: R270
