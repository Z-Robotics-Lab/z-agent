# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R269 (E67) VERIFY/HYGIENE — skeptic re-verify RE-CONFIRMS the oldest STALE confirmed BOARD
  row place.nl-plain-colour (age68, R200 2/2), MODE=place: GROUNDED verified=True (2/2), grasp actor=CAUSED,
  resting_on_receptacle GT-True, native seq CLEAN ZERO re-grasp → R257 post-place guard HELD (FIRST post-guard re-check; R260 flagged). supersedes R200.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: blocked
last-round: R269 (E67, VERIFY/HYGIENE, non-gated). One bare-face skeptic re-verify (deepseek-v4-flash brain +
  local gemma4:e4b eyes, MODE=place '把绿色的瓶子放到架子上'). place.nl-plain-colour RE-CONFIRMED GROUNDED
  verified=True (2/2): perception_grasp→holding_object(pickable_bottle_green) actor=CAUSED; mobile_place→
  resting_on_receptacle()>=1 GT-True (actor=NOT_GRADED = causation-attribution only, the physics AABB is
  unauthorable). Native seq CLEAN ZERO mobile_pick re-grasp ⇒ R257 guard held, no plain-colour regression;
  launch_explore_seen=False; eyes (var/evidence/R269/eyes_place.png): green RESTING in receptacle, gripper empty,
  red+purple remain = discrimination. supersedes R200; sim torn down. PROVIDER: default qwen routing brain now
  ARREARAGE (400) → forced deepseek (cost 1 wasted launch).
frontier: BLOCKED — non-gated NEW-capability frontier EXHAUSTED (3 critics R240/R250/R260 + R262 close). Every
  genuinely-new bar is a CEO gate: S4 (3rd embodiment BYO URDF) and D182 (world-owned NL→object grounder), UNANSWERED
  ~29 rounds. Loop treads water on non-gated HYGIENE (stale-row skeptic re-verify) until an owner gate decision. R270 review due.
watch: Real-face fetch/place recipe: bare vcli + NL, deepseek-v4-flash brain — MUST force the deepseek provider
  (per .env.example; the default qwen route is in ARREARAGE), local ollama gemma4:e4b eyes (repl_accept AUTO-routes
  perception via resolve_local_vlm_env — do NOT set the VLM url env; the qwen3-vl JUDGE shares the arrears key → eyes=self-read).
  repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo}>. RUN `.venv/bin/python` under memory-cap
  `systemd-run --user --scope -p MemoryMax=24G`; tear down `scripts/sim-teardown`; place ~4-6min; Bash 120s →
  BACKGROUND+poll. LEDGER: append 1 preformatted line (result/redteam ≤280, row ≤1KB), never rewrite. NOTE:
  MODE=combo place-leg causation-UNGRADABLE one-session (E17/E64); a MODE=place place-leg resting is GROUNDED-true
  but actor=NOT_GRADED for attribution — moat = grasp CAUSED + GT resting AABB + eyes (E67).
next:
  1. [OWNER GATE — the ONLY path to NEW capability] Unblock S4 (3rd embodiment via BYO URDF+manifest, one generic
     driver) OR D182 (world-owned NL→object grounder). Both CEO-gated (kernel/interface + spine semantics), unanswered
     ~29 rounds. See gates: below + LESSONS ## Frontier R262 line for the exec ask.
  2. [NON-gated HYGIENE] Skeptic re-verify the NEXT oldest ⚠STALE confirmed BOARD row: quantity-place.nl-isolation
     (age64, GROUNDED 2/2, MODE=place). Then quantity-place.nl (age63, GROUNDED-FLAKY). R269 re-confirmed
     place.nl-plain-colour; R268 negated-distractor; R263 category-only — do NOT re-run those. R270 is a REVIEW round.
  3. [BLOCKED — do NOT cross] any 4th world / more colours / combo variant is the SAME local hill (3 critics); do
     not mine it as "new capability". Only pursue if it hardens an existing confirmed bar, not as frontier.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← escalated as next#1.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); would also fix E65 (ordinal→live-scene, not memorised colour). Object plug-in not pure config → S4. ← next#1.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM 402 + the qwen-max ROUTING brain now in Arrearage; local Ollama gemma4:e4b + deepseek route are the working seams) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R260): gate/token audit R251..R259 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R260
