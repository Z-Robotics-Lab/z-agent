# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R259 (E60) VERIFY/ADJUDICATE — courtyard PLACE PROMOTED to CONFIRMED.
  Re-ran the R257 provisional on the bare face across the boundary: GROUNDED verified=True (2/2),
  native skill seq CLEAN (perception_grasp->verify holding->mobile_place->verify resting->finish),
  ZERO mobile_pick re-grasp — the R257 post-place guard held (cleaner than R257 run2's wander).
  Eyes: green bottle resting in the courtyard bin, gripper empty. Courtyard PLACE CLOSED.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R259 (E60, VERIFY/ADJUDICATE, non-gated). Also cleared the R258 stale-BOARD quarantine
  (regen loop/board.py) + adopted the R258 rounds.jsonl append. 1 acceptance(confirmed) + 1
  experiments(confirmed) row banked; supersedes the R257 provisional. 3 clean same-brain GROUNDED
  total (R257×2 + R259). No sim leftover (sim-teardown clean).
frontier: 3 worlds ground go2 FETCH; PLACE now CONFIRMED on house + courtyard (2 of 3 worlds).
  NEXT non-gated FLOOR-raise: does the PLACE composite (grasp->nav->place, the fragile nav-sub-goal
  per E56) transfer to the WAREHOUSE — the hue-adjacent hard world (E54)? Fetch transferred zero-shot
  everywhere; place is the multi-step composite that does NOT follow from fetch. PLATEAU HOLDS (R250
  critic): genuinely-new breadth is GATED (3rd embodiment BYO URDF S4 + D182 grounder).
watch: Real-face place: bare vcli + NL, deepseek-v4-flash brain (provider env per .env.example),
  VECTOR_ROOM_TEMPLATE={courtyard|warehouse}, local ollama gemma4:e4b, repl_accept.py MODE=place;
  PLACE='把绿色的瓶子放到架子上'; RUN via `.venv/bin/python` (bare `python` is NOT on the scope PATH —
  systemd-run resets it, R259 wasted one launch on env:python not-found); memory-cap `systemd-run
  --user --scope -p MemoryMax=24G`; tear down `scripts/sim-teardown`; ~4-6min/run; Bash 120s limit ->
  run in BACKGROUND. Guard code: native_loop.py `_GRASP_SKILLS`/`_PLACE_SKILLS`/`_POST_PLACE_REGRASP_NUDGE`
  + NativeStepRunner `_place_awaiting_verify`. LEDGER: confirmed redteam starts 'survived'; free-text ≤280; row ≤1KB.
next:
  1. [BUILD/VERIFY, NON-gated] WAREHOUSE PLACE transfer: VECTOR_ROOM_TEMPLATE=warehouse MODE=place
     '把绿色的瓶子放到架子上' on the bare face, N>=1. Confirms PLACE composite generalizes to all 3
     worlds (not just fetch). If it RANs, Hypothesis-Loop the nav-sub-goal (E56 fragile link), NOT
     perception (warehouse perception already fixed R237/R238). Provisional -> promote next round.
  2. [SPINE, GATED] D182 world-owned NL->object grounder — removes witness-only fidelity; CEO gate.
  3. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL->object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) -> S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R250): gate/token audit R241..R249 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R250
