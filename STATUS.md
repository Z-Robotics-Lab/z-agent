# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R273 (E72 VERIFY / E70 BUILD) — adjudicated the deadline-critical R270
  provisional (REFUTED) and fixed the E70 place/combo vlm-judge race (code+test, e2e owed).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182; frontier = model non-determinism on the local/flash seam)
last-round: R273 (E72 VERIFY + E73 BUILD, non-gated). (1) DEADLINE-CRIT adjudication of the R270
  quantity-place.nl-isolation PARTIAL provisional: a DEDICATED clean MODE=seq re-run (turn1蓝,
  turn2红 — AVOIDING the known green-2nd-obj fragility) had turn1-BLUE ITSELF THRASH — 0 verdicts
  in ~15min, degenerate loop (look3726/pgrasp1573/nav1608/describe1781). So R204's confirmed 2/2
  is NON-REPRODUCIBLE and the thrash is NOT green-specific: the deepseek-v4-flash routing brain's
  place-decompose is FLAKY run-to-run (R272-judge non-determinism class). 2 REFUTED rows supersede
  R270+R204; machinery-vs-BRAIN LESSON (E38) still holds. (2) E70/E73 fix: reordered
  `drain_until_quiet`→`_eyes_frame` in fetch/place/combo/quantity (settled frame, mirror seq)
  +regr test (green); REAL place+vlm-judge e2e re-verify DEFERRED (one sim slot spent on #1).
frontier: MODEL NON-DETERMINISM is the verify-face bottleneck on BOTH ends of the local seam — the
  gemma4:e4b JUDGE (R272 PASS→ABSTAIN) AND the deepseek-v4-flash ROUTING BRAIN (R273 place-decompose
  thrash). A runner degenerate-loop guardrail (detect look/describe/navigate spin → break it, cf.
  R206/R257 guards) is the next NON-gated build; stronger models remain owner/billing.
watch: Real-face recipe (.env.example): bare vcli + NL; FORCE deepseek provider (default qwen in
  ARREARAGE 400); local ollama gemma4:e4b eyes+judge auto-routed by repl_accept (resolve_local_vlm_env
  + resolve_judge_env LOCAL-PREFERS gemma4:e4b, overrides stale supervisor qwen3-vl-plus) — do NOT set
  VLM/JUDGE url env. tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo|
  seq|quantity}>; all branches now drain-then-eyes (E73 settled frame). RUN `.venv/bin/python` under
  `systemd-run --user --scope -p MemoryMax=24G`; seq/quantity ~15-20min → BACKGROUND+poll (Bash 120s).
  Sim is IN-PROCESS python (NOT a `mujoco` binary) — pgrep the TAG, tear down MY OWN PIDs +
  scripts/sim-teardown, NEVER pkill mujoco. LEDGER: append ≤1KB/row, field ≤280 chars (Chinese 1/char),
  never rewrite. green/place-decompose as a 2nd/ordinal target is thrash-prone (E40/E45/E65/E72).
next:
  1. [NON-gated VERIFY — owed] Re-verify the E70 fix on the REAL face: MODE=place eyes=vlm-judge,
     confirm judge_witness.log is NON-empty (judge fires on place). Promote E70 provisional→confirmed.
  2. [NON-gated BUILD] Runner degenerate-loop guardrail: detect the look/describe/navigate spin
     (N repeats, 0 verdicts) and break to an honest fail — attacks the R272+R273 non-determinism.
  3. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment, BYO
     URDF+manifest, one generic driver) OR D182 (world-owned NL→object grounder). CEO-gated ~33r. ↓gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← next#3.
  - SPINE (D182): world-owned NL→object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. ← next#3.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: qwen ROUTING brain + qwen3-vl JUDGE both in Arrearage; local ollama gemma4:e4b + deepseek route are the working seams) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R270): gate/token R261..R269 CLEAN (no GATE/CEO-APPROVED crossings; last was R187, audited clean R209).
last_review: R270
