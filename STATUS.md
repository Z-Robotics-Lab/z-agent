# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R268 (E65/E66) ADOPT+VERIFY/HYGIENE — adopted R266→R267 inflight; FLIPPED stale
  fetch.nl-ordinal-spatial (R197 2/2 → REFUTED, grasp 0px, E65); CONTROL RE-CONFIRMED fetch.nl-negated-distractor
  (GROUNDED 1/1, red can held → E65 is ORDINAL-specific not a systemic regression, E66); cleared R267 quarantine.
  phase:blocked (frontier EXHAUSTED; S4/D182 CEO gates unanswered ~28 rounds — only non-gated work is re-verify).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: blocked
last-round: R268 (E65/E66, ADOPT+VERIFY/HYGIENE, non-gated). Two bare-face skeptic re-verifies (deepseek-v4-flash
  + local gemma4:e4b eyes). (1) Adopted R266→R267 inflight fetch '把最左边的瓶子拿过来': RAN verified=False (0/5) —
  perception_grasp found NO object (mask_px=0, none-plausible all 6 scans, green not in front-cam) → nothing held →
  UNCAUSED; scene DID load (24 objs) so not empty-sim; R197 memorised leftmost→green → fetch.nl-ordinal-spatial
  REFUTED, supersedes R197 (E65). (2) CONTROL fetch '只把红色的罐子' (reject blue/green): GROUNDED 1/1 actor=CAUSED,
  eyes: gripper holds RED can, distractors untouched → fetch.nl-negated-distractor RE-CONFIRMED supersedes R200 (E66),
  proving E65 is ORDINAL-specific not a systemic regression. 1 refuted+1 confirmed acc + 2 exp banked; quarantine
  cleared (BOARD regen); both sims torn down; check.sh green.
frontier: BLOCKED — non-gated NEW-capability frontier EXHAUSTED (3 critics R240/R250/R260 + R262 close). Every
  genuinely-new bar is a CEO gate: S4 (3rd embodiment BYO URDF) and D182 (world-owned NL→object grounder), UNANSWERED
  ~28 rounds. Loop treads water on non-gated HYGIENE (stale-row skeptic re-verify) until an owner gate decision.
watch: Real-face fetch/place recipe (unchanged): bare vcli + NL, deepseek-v4-flash brain (provider+model env per
  .env.example), local ollama gemma4:e4b eyes (repl_accept AUTO-routes via resolve_local_vlm_env — do NOT set the VLM
  url env). repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo}>. RUN via `.venv/bin/python`; memory-cap
  `systemd-run --user --scope -p MemoryMax=24G`; tear down `scripts/sim-teardown`; fetch ~4-6min, combo ~10min; Bash
  120s → BACKGROUND + poll log. LEDGER: append 1 preformatted line, never rewrite; free-text fields ≤280, row ≤1KB.
  NOTE: MODE=combo place-leg causation-UNGRADABLE one-session (E17/E64). NEW watch: ordinal 'leftmost' grounds to a
  MEMORISED colour (green), not computed from live scene — a green not in front-cam view → grasp finds 0px (E65).
next:
  1. [OWNER GATE — the ONLY path to NEW capability] Unblock S4 (3rd embodiment via BYO URDF+manifest, one generic
     driver) OR D182 (world-owned NL→object grounder). Both CEO-gated (kernel/interface + spine semantics), unanswered
     ~28 rounds. See gates: below + LESSONS ## Frontier R262 line for the exec ask.
  2. [NON-gated HYGIENE] Skeptic re-verify the NEXT oldest ⚠STALE confirmed BOARD row: place.nl-plain-colour
     (age68, NOT re-verified post-R257-guard) via MODE=place. Then quantity-place.nl-isolation (64). R268
     re-confirmed negated-distractor + flipped ordinal-spatial; R264 flipped compound — do NOT re-run those three.
  3. [BLOCKED — do NOT cross] any 4th world / more colours / combo variant is the SAME local hill (3 critics); do
     not mine it as "new capability". Only pursue if it hardens an existing confirmed bar, not as frontier.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← escalated as next#1.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); would also fix E65 (ordinal→live-scene, not memorised colour). Object plug-in not pure config → S4. ← next#1.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM 402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R260): gate/token audit R251..R259 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R260
