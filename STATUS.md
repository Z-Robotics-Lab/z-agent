# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R256 (E60) DEBUG — courtyard PLACE "mid-walk drop" REFUTED; root cause = BRAIN.
  In-process (no brain) the grasp weld holds the bottle 25–30mm from the EE through the WHOLE 1.6m
  walk + Step-6b dock (N=2, 1028 samples, eq_active never flips, never hits floor), and the FULL
  MobilePlaceSkill lands it RESTING on the courtyard bin (resting_on_receptacle=1, gripper empty) —
  machinery SOUND. Real R255 repl trace: mobile_place places OK → brain misreads the (expected) empty
  gripper as '掉了' → re-grasps the just-placed bottle OFF the bin → thrash → resting=False.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R256 (E60, DEBUG, non-gated). Root-caused courtyard PLACE flake to BRAIN post-place
  mis-recovery (NOT a physics drop; H1-H4 refuted N=2 in-process). 1 experiments(debug) row provisional;
  DEBUG.md CONCLUDE; regression test added (machinery rests=1); LESSONS updated; check.sh green.
frontier: 3 worlds ground go2 FETCH; courtyard PLACE is the OPEN non-gated reliability gap but is now
  correctly localized: the mobile_place MACHINERY works (in-process rests=1, weld holds N=2); the flake is
  the BRAIN re-grasping a legitimately-placed object after mobile_place empties the gripper. PLATEAU HOLDS
  (R250 critic): genuinely-new breadth is GATED (3rd embodiment BYO URDF S4 + D182 grounder); non-gated
  frontier = the PLACE post-recovery guard below.
watch: DEBUG probes: scripts/debug_r256_midwalk_drop.py (weld sampling walk+dock) + debug_r256_full_place.py
  (full place, reads resting_on_receptacle). Run in-process, NO ROS2/brain, memory-capped:
  `systemd-run --user --scope -p MemoryMax=24G .venv/bin/python scripts/<probe>.py`; VECTOR_ROOM_TEMPLATE=courtyard,
  VECTOR_SIM_WITH_ARM=1, backend=mpc. Two holding signals: gripper.is_holding()=software flag (cleared only at
  open()); holding_object() oracle=GT (object <0.08m of EE + z>=0.10). R255 evidence lacked [MOBILE-PLACE] driver
  logs (they go to stderr, not the PTY) — that's why "mid-walk drop" was mis-inferred; capture skill stderr next time.
  Real-face place still: bare vcli + NL, deepseek-v4-flash + local ollama gemma4:e4b, courtyard, ~4-8min flaky, tear
  down via scripts/sim-teardown. LEDGER: confirmed redteam starts 'survived'; free-text ≤280 chars; experiments key `e`.
next:
  1. [BUILD, NON-gated] BRAIN post-place recovery guard: after a successful place/mobile_place, an EMPTY gripper is
     the EXPECTED terminal state — the brain must NOT interpret holding_object=False as an accidental drop and
     re-grasp the placed object. Prompt nudge in the place persona AND/OR a runner finish-gate (cf. R206 quantity
     guardrail: enforce in native_loop, model still owns decompose). NOT a mobile_place/weld change (refuted R256).
     Then re-verify courtyard PLACE on the bare face N>=2 (was the R255 refuted bar). Guard must not touch the spine.
  2. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  3. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R250): gate/token audit R241..R249 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R250
