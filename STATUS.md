# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R262 (E62) VERIFY/PROMOTE — warehouse PLACE PROMOTED to confirmed (N≥2).
  Re-ran the bare face across the R261→R262 boundary (VECTOR_ROOM_TEMPLATE=warehouse MODE=place,
  deepseek-v4-flash brain, local gemma4:e4b eyes): place_verified=True (2/2), launch_explore_seen=False.
  With R261 N=1 this meets E46 N≥2 → confirmed. PLACE now GROUNDED-confirmed on ALL 3 worlds
  (house + courtyard + warehouse); fetch grounds all 3. → non-gated NEW-capability frontier EXHAUSTED.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: blocked
last-round: R262 (E62, BUILD/VERIFY, non-gated). Promoted the R261 warehouse-place provisional: native seq
  CLEAN grasp→verify holding_object(green,CAUSED)→mobile_place→verify resting_on_receptacle→finish; ZERO
  mobile_pick re-grasp (R257 guard held); no nav snag. GT moat = resting_on_receptacle reads place_bin(10.95,
  4.60) live AABB (actor-uncanted, Inv.1). Eyes self-read: green resting in oak receptacle, concrete/yellow-lane
  warehouse shell (NOT house marble), distractors remain = discrimination. 1 acceptance(confirmed) + 1
  experiments(verify) + 1 experiments(research: blocked declaration) row banked. Sim torn down. check.sh green.
frontier: BLOCKED — non-gated NEW-capability frontier EXHAUSTED. 3 consecutive critics (R240/R250/R260) judged
  more colours/worlds/place-on-Nth-world the SAME local hill; R262 closed the last one (place on all 3 worlds).
  Every genuinely-new bar is a CEO gate: S4 (3rd embodiment BYO URDF) and D182 (world-owned NL→object grounder,
  also fixes witness-only fidelity), UNANSWERED ~22 rounds. Loop treads water on non-gated HYGIENE until unblocked.
watch: Real-face place/fetch recipe (unchanged): bare vcli + NL, deepseek-v4-flash brain (provider+model env
  per .env.example), local ollama gemma4:e4b eyes (repl_accept AUTO-routes via resolve_local_vlm_env —
  do NOT set the VLM url env), VECTOR_ROOM_TEMPLATE={courtyard|warehouse} (unset=HOUSE), repl_accept.py
  MODE={fetch|place|combo}; RUN via `.venv/bin/python`; memory-cap `systemd-run --user --scope -p MemoryMax=24G`;
  tear down `scripts/sim-teardown`; ~4-6min/run; Bash 120s → BACKGROUND + poll the log. Warehouse: place_bin
  (10.95,4.60) is +y of pick_table(10.95,3.0). LEDGER: redteam starts 'survived'; free-text≤280; append 1 line (E27).
next:
  1. [OWNER GATE — the ONLY path to NEW capability] Unblock S4 (3rd embodiment via BYO URDF+manifest, one
     generic driver) OR D182 (world-owned NL→object grounder). Both are CEO-gated (kernel/interface + spine
     semantics) and unanswered ~22 rounds. See gates: below + LESSONS ## Frontier R262 line for the exec ask.
  2. [NON-gated HYGIENE, while gates are unanswered] Skeptic re-verify the OLDEST ⚠ STALE confirmed BOARD row
     on the real bare face (fetch-place.nl-category-only ~82r, or fetch-place.nl-compound ~79r) with the working
     deepseek-v4-flash + local-eyes seam — a stale green is worse than a known red. (R270 review will also do this.)
  3. [BLOCKED — do NOT cross] any 4th world / more colours / combo variant is the SAME local hill (3 critics); do
     not mine it as "new capability". Only pursue if it hardens an existing confirmed bar, not as frontier.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← escalated as next#1.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4. ← escalated as next#1.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R260): gate/token audit R251..R259 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R260
