# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R274 (E74 BUILD+VERIFY) — degenerate-spin guard landed; E70 judge-on-place VERIFIED.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182; frontier = model non-determinism on the local/flash seam)
last-round: R274 (E74 BUILD, non-gated). (1) Built a degenerate-spin GUARD in native_loop
  (attacks the R272/R273 verify-face bottleneck: a flaky brain issues action skills turn
  after turn WITHOUT verifying → burns all 24 turns/0 verdicts/~15min, judge never fires).
  Turns-since-verify counter: nudge@6 (force a measurement → a real verdict + judge fires),
  honest break@12 (trace grades RAN/empty, never a forced green). Planner-free (keys only on
  'did a verify happen'). 24/24 unit green. (2) REAL-face non-regression: MODE=fetch green
  GROUNDED verified=True 1/1, guard SILENT; eyes green aloft/others remain. (3) BONUS MODE=place
  closed next#1/E70: judge_witness.log NON-empty for place (witness=PASS 4/4) — the R273
  drain→eyes reorder makes the judge FIRE on place; place GROUNDED 2/2, guard silent, eyes:
  green resting on receptacle/gripper empty. Guard non-regressive on BOTH faces.
frontier: The guard tames the thrash SYMPTOM but is UNIT-proven only — both real runs this round
  grounded CLEANLY (guard silent), so the guard FIRING on a real thrash is not yet observed. ROOT
  causes stay owner/billing: the WEAK non-deterministic gemma4:e4b JUDGE (R272 PASS↔ABSTAIN, needs a
  stronger VLM) + the flaky deepseek-v4-flash ROUTING brain (needs stronger brain or the D182 grounder).
watch: Real-face recipe: bare vcli + NL; FORCE the deepseek provider + the deepseek-v4-flash model via
  env override (.env defaults qwen, ARREARAGE 400); local ollama gemma4:e4b eyes+judge AUTO-routed by repl_accept
  (do NOT set VLM/JUDGE url env). tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|
  place|combo|seq|quantity}>. RUN under `systemd-run --user --scope -p MemoryMax=24G`; place ~10min,
  seq/quantity ~15-20min → BACKGROUND+poll. Sim is IN-PROCESS python (pgrep the TAG; NEVER pkill mujoco).
  LEDGER: append ≤1KB/row, field ≤280 chars, never rewrite. green place-decompose CAN thrash run-to-run
  (E40/E72); the R274 guard now caps that at 12 turns instead of 24.
next:
  1. [NON-gated VERIFY] Catch the R274 guard FIRING on a REAL thrash (MODE=seq two-object, or repeat
     MODE=place until a decompose thrashes) — confirm it nudges then breaks EARLY (<12 turns, honest
     RAN), not a 24-turn/15min hang. THEN promote E74 + verify.eyes-vlm-judge-place (E70) provisional→confirmed.
  2. [NON-gated] Adjudicate R274 provisionals (§1b): runner.degenerate-spin-guard, verify.eyes-vlm-judge-place.
  3. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment, BYO URDF+manifest,
     one generic driver) OR D182 (world-owned NL→object grounder). CEO-gated ~34r. ↓gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← next#3.
  - SPINE (D182): world-owned NL→object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. ← next#3.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING brain + qwen3-vl JUDGE both Arrearage; a STRONGER local/funded VLM judge would fix R272 non-determ) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R270): gate/token R261..R273 CLEAN (no GATE/CEO-APPROVED crossings; last was R187, audited clean R209).
last_review: R270
