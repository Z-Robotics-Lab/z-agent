# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R261 (E62) BUILD/VERIFY — WAREHOUSE PLACE transfer GROUNDED (provisional N=1).
  Bare face, VECTOR_ROOM_TEMPLATE=warehouse MODE=place '把绿色的瓶子放到架子上', deepseek-v4-flash brain,
  local-ollama gemma4:e4b eyes. place_verified=True (2/2). Native seq CLEAN: perception_grasp -> verify
  holding_object(green) CAUSED -> mobile_place -> verify resting_on_receptacle -> finish; ZERO mobile_pick
  re-grasp/掉了 thrash (R257 post-place guard held). NO nav-sub-goal snag (unlike E56 courtyard). Warehouse
  shell confirmed from the frame (yellow safety lanes + concrete-checker floor, NOT house marble).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R261 (E62, BUILD, non-gated). Warehouse PLACE composite transfers zero-config to the 3rd world
  on the bare face: GROUNDED verified=True 2/2 provisional N=1. GT moat = resting_on_receptacle reads
  place_bin(10.95,4.60) live AABB (actor-uncanted, Inv.1). Eyes self-read: green resting on an oak receptacle
  table in the warehouse; receptacle IDENTITY leans on the GT oracle (pick_table/place_bin byte-identical oak
  boxes). 1 acceptance(provisional) + 1 experiments(verify) row banked (E62). check.sh green.
frontier: PLACE now GROUNDED on all 3 worlds (house + courtyard CONFIRMED, warehouse provisional N=1);
  fetch grounds all 3 zero-shot. Per R260 AMBITION CRITIC: once warehouse-place PROMOTES to confirmed
  (next round), the non-gated frontier is EXHAUSTED — place-on-Nth-world is the same local hill. Genuinely-new
  bars (S4 3rd-embodiment BYO URDF, D182 grounder) are GATED + UNANSWERED ~21 rounds — owner must unblock.
watch: Real-face place/fetch: bare vcli + NL, deepseek-v4-flash brain (provider per .env.example), local
  ollama gemma4:e4b eyes (repl_accept AUTO-routes via resolve_local_vlm_env — do NOT set the VLM url env),
  VECTOR_ROOM_TEMPLATE={courtyard|warehouse} (unset=HOUSE), repl_accept.py MODE={fetch|place|combo}; RUN via
  `.venv/bin/python`; memory-cap `systemd-run --user --scope -p MemoryMax=24G`; tear down `scripts/sim-teardown`;
  ~4-10min/run; Bash 120s -> BACKGROUND + poll the log. Guard: native_loop.py post-place guard (WIRING:80).
  Warehouse: place_bin(10.95,4.60) is +y from pick_table(10.95,3.0); resting_on_receptacle=_RECEPTACLE_BODY
  'place_bin' (robot.py:37). LEDGER: redteam starts 'survived'; free-text<=280; append 1 line (E27).
next:
  1. [VERIFY/PROMOTE, NON-gated] Adjudicate R261/E62 warehouse-place provisional (GROUNDED 1/1): re-run on
     the bare face across the R261->R262 boundary (VECTOR_ROOM_TEMPLATE=warehouse MODE=place) to meet E46
     N>=2 and PROMOTE to confirmed. do_not_retry_unless: warehouse PLACE regresses to RAN, OR R257 post-place
     guard reverted (regr=tests/unit/vcli/test_native_loop.py post_place). IF it holds -> ALL 3 worlds place
     CLOSED -> per R260 critic the non-gated frontier is EXHAUSTED -> phase: blocked, HOLD at the gates.
  2. [SPINE, GATED] D182 world-owned NL->object grounder — removes witness-only fidelity; CEO gate.
  3. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL->object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) -> S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R260): gate/token audit R251..R259 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R260
