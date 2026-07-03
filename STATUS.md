# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R257 (E60) BUILD/VERIFY — courtyard PLACE GROUNDED N=2 provisional; the
  R256-root-caused BRAIN post-place mis-recovery is FIXED. Guard = persona post-place-no-regrasp
  nudge + a deterministic runner re-grasp-until-verify gate (NOT a mobile_place/weld change,
  refuted R256). Both bare-face runs (deepseek-v4-flash, MODE=place, in-process) grounded
  resting_on_receptacle True with NO mobile_pick re-grasp; eyes: green RESTING in bin, gripper empty.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R257 (E60, BUILD/VERIFY, non-gated). Fixed the R256 root cause (brain re-grasps a
  legitimately-placed object). TDD: 3 RED->GREEN (persona teaches empty-gripper-after-place is not a
  drop; runner refuses a re-grasp until a verify closes the place, bounded/quantity-safe). Real face
  N=2 both GROUNDED (was R255 refuted RAN 0/1). 1 acceptance provisional + 1 experiments(confirmed) row.
frontier: 3 worlds ground go2 FETCH; courtyard PLACE now GROUNDED N=2 provisional — the long-running
  reliability gap is CLOSED to the R255 bar. RESIDUAL (honest): run2 brain wandered post-place
  (look/at_position/repeat-place) but non-destructively — the guard kills the DESTRUCTIVE re-grasp,
  not all post-place flakiness. PLATEAU HOLDS (R250 critic): genuinely-new breadth is GATED (3rd
  embodiment BYO URDF S4 + D182 grounder). Non-gated polish: tighten post-place convergence only if it recurs.
watch: Real-face place: bare vcli + NL, deepseek-v4-flash brain (provider env per .env.example),
  courtyard template, local ollama gemma4:e4b, repl_accept.py MODE=place; FETCH='把绿色的瓶子拿过来'
  PLACE='把绿色的瓶子放到架子上'; memory-cap `systemd-run --user --scope -p MemoryMax=24G`; tear down
  `scripts/sim-teardown`; ~7min/run. Bash tool 120s limit — run acceptance in the BACKGROUND. Guard code:
  native_loop.py `_GRASP_SKILLS`/`_PLACE_SKILLS`/`_POST_PLACE_REGRASP_NUDGE` + NativeStepRunner
  `_place_awaiting_verify`. LEDGER: confirmed redteam starts 'survived'; free-text ≤280 chars; row ≤1KB.
next:
  1. [PROMOTE, §1c] Adjudicate the R257 courtyard PLACE provisional (place.nl-new-world-courtyard
     GROUNDED 2/2) next round: re-run N>=1 across the boundary + red-team; if it holds, promote to
     confirmed. Do NOT promote same-round.
  2. [BUILD, NON-gated] IF a post-place wander recurs (run2 style): add a runner finish-nudge that,
     once resting_on_receptacle PASSES, steers the brain to finish rather than re-place/look. Optional
     polish — the destructive failure is already fixed; only build if the wander costs a real verdict.
  3. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  4. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R250): gate/token audit R241..R249 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R250
