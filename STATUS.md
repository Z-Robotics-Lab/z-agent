# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R264 (E64) VERIFY/HYGIENE — skeptic re-verify FLIPPED a stale green to red: the
  next-oldest STALE row fetch-place.nl-compound (age 77, R186 GROUNDED 2/2) does NOT reproduce → REFUTED.
  phase:blocked (non-gated NEW-capability frontier still EXHAUSTED). While S4/D182 CEO gates stay unanswered
  (~24 rounds), the only non-gated work is skeptic re-verify of stale BOARD rows — a stale green is worse than red.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: blocked
last-round: R264 (E64, VERIFY/HYGIENE, non-gated). repl_accept MODE=combo, '把绿色的瓶子拿过来放到架子上', bare
  face, deepseek-v4-flash brain + local gemma4:e4b eyes. Compound DECOMPOSED correctly (perception_grasp→verify
  holding_object('pickable_bottle_green') actor=CAUSED ✓; then mobile_place→verify resting_on_receptacle()) and
  PLACE physically SUCCEEDED (eyes: green resting on receptacle, gripper empty; GT resting_on_receptacle()>=1
  TRUE). BUT verdict RAN verified=False (2/4): the place-leg causation is NOT_GRADED in the same single session
  (E17-class), a bare placed_count() UNCAUSED. R186's 2/2 predates the stricter causation grader (Inv.1: grading
  only tightens) → does not carry forward. BOARD row confirmed⚠STALE → REFUTED (supersedes R186). 1
  acceptance(refuted) + 1 experiments(verify,E64 refuted) banked. Sim torn down. check.sh green.
frontier: BLOCKED — non-gated NEW-capability frontier EXHAUSTED (3 critics R240/R250/R260 + R262 close). Every
  genuinely-new bar is a CEO gate: S4 (3rd embodiment BYO URDF) and D182 (world-owned NL→object grounder), UNANSWERED
  ~24 rounds. Loop treads water on non-gated HYGIENE (stale-row skeptic re-verify) until an owner gate decision.
watch: Real-face fetch/place recipe (unchanged): bare vcli + NL, deepseek-v4-flash brain (provider+model env per
  .env.example), local ollama gemma4:e4b eyes (repl_accept AUTO-routes via resolve_local_vlm_env — do NOT set the VLM
  url env). repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo}>. RUN via `.venv/bin/python`; memory-cap
  `systemd-run --user --scope -p MemoryMax=24G`; tear down `scripts/sim-teardown`; fetch ~4-6min, combo ~10min; Bash
  120s → BACKGROUND + poll log. LEDGER: append 1 preformatted line, never rewrite; free-text fields ≤280, row ≤1KB.
  NOTE: MODE=combo place-leg is causation-UNGRADABLE in one session (E17/E64) — combo grades the grasp CAUSED only.
next:
  1. [OWNER GATE — the ONLY path to NEW capability] Unblock S4 (3rd embodiment via BYO URDF+manifest, one generic
     driver) OR D182 (world-owned NL→object grounder). Both CEO-gated (kernel/interface + spine semantics), unanswered
     ~24 rounds. See gates: below + LESSONS ## Frontier R262 line for the exec ask.
  2. [NON-gated HYGIENE] Skeptic re-verify the NEXT oldest ⚠STALE confirmed BOARD row: fetch.nl-ordinal-spatial
     (age 67), then fetch.nl-negated-distractor (64) / place.nl-plain-colour (64, NOT re-verified post-R257-guard).
     R264 already flipped fetch-place.nl-compound → refuted; do NOT re-run combo expecting green (place-leg
     causation-ungradable, E17/E64) unless a causation-safe compound-place grader lands.
  3. [BLOCKED — do NOT cross] any 4th world / more colours / combo variant is the SAME local hill (3 critics); do
     not mine it as "new capability". Only pursue if it hardens an existing confirmed bar, not as frontier.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← escalated as next#1.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4. ← escalated as next#1.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM 402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R260): gate/token audit R251..R259 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R260
