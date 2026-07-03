# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R263 (E63) VERIFY/HYGIENE — oldest STALE confirmed BOARD row re-confirmed on the current seam.
  phase:blocked (non-gated NEW-capability frontier still EXHAUSTED). While the CEO gates are unanswered, the only
  non-gated work is skeptic re-verify of stale BOARD rows (a stale green is worse than a known red). This round
  re-verified fetch-place.nl-category-only (age 79, confirmed ONLY on retired deepseek-chat R183) on the CURRENT
  deepseek-v4-flash + local gemma4:e4b seam: GROUNDED 1/1, category '罐子'→pickable_can_red (the only can) actor=CAUSED.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: blocked
last-round: R263 (E63, VERIFY/HYGIENE, non-gated). Ran repl_accept MODE=fetch, FETCH='把罐子拿过来', bare face,
  deepseek-v4-flash brain + local-ollama gemma4:e4b eyes. Native seq CLEAN: perception_grasp(query=罐子)→verify
  holding_object('pickable_can_red') actor=CAUSED → GROUNDED verified=True (1/1); launch_explore_seen=False. Eyes
  self-read: red can aloft in gripper, green/blue/purple/yellow remain on pick_table=discrimination, HOUSE marble
  shell. Category-only grounding UNAMBIGUOUS (only can) — distinct from E6 (refuted ambiguous identical-geom).
  BOARD row refreshed age 79→0 + provider deepseek-chat→v4-flash (FIRST v4-flash run of this cap). 1 acceptance
  (confirmed, supersedes @R183) + 1 experiments(verify) row banked. Sim torn down. check.sh green.
frontier: BLOCKED — non-gated NEW-capability frontier EXHAUSTED (3 critics R240/R250/R260 + R262 close). Every
  genuinely-new bar is a CEO gate: S4 (3rd embodiment BYO URDF) and D182 (world-owned NL→object grounder), UNANSWERED
  ~23 rounds. Loop treads water on non-gated HYGIENE (stale-row skeptic re-verify) until an owner gate decision.
watch: Real-face fetch/place recipe (unchanged): bare vcli + NL, deepseek-v4-flash brain (provider+model env per
  .env.example), local ollama gemma4:e4b eyes (repl_accept AUTO-routes via resolve_local_vlm_env — do NOT set the VLM
  url env). repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo}>; category-only FETCH='把罐子拿过来'.
  RUN via `.venv/bin/python`; memory-cap `systemd-run --user --scope -p MemoryMax=24G`; tear down `scripts/sim-teardown`;
  fetch ~4-6min; Bash 120s → BACKGROUND + poll the log. LEDGER: redteam starts 'survived'; free-text≤280; append 1 line.
next:
  1. [OWNER GATE — the ONLY path to NEW capability] Unblock S4 (3rd embodiment via BYO URDF+manifest, one generic
     driver) OR D182 (world-owned NL→object grounder). Both CEO-gated (kernel/interface + spine semantics), unanswered
     ~23 rounds. See gates: below + LESSONS ## Frontier R262 line for the exec ask.
  2. [NON-gated HYGIENE, while gates unanswered] Skeptic re-verify the NEXT oldest ⚠ STALE confirmed BOARD row:
     fetch-place.nl-compound (age 76, MODE=combo) on the working deepseek-v4-flash + local-eyes seam. Then
     fetch.nl-ordinal-spatial (65) / place.nl-plain-colour (62, NOT re-verified post-R257-guard — R260 fidelity note).
  3. [BLOCKED — do NOT cross] any 4th world / more colours / combo variant is the SAME local hill (3 critics); do
     not mine it as "new capability". Only pursue if it hardens an existing confirmed bar, not as frontier.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← escalated as next#1.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4. ← escalated as next#1.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R260): gate/token audit R251..R259 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R260
