# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R225 (E50) BUILD — ADJUDICATED the R224 g1.perception provisional → CONFIRMED N=3; reproduced on the bare face across the R224→R225 boundary.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R225 (E50, BUILD). Executed STATUS next#1: adjudicate the R224 E50 g1.perception GROUNDED
  N=2 provisional. Ran a FRESH g1_accept on the bare face (deepseek-v4-flash, oracle+tol BYTE-UNCHANGED
  = Inv.1) — the exact reproducibility test R223 FAILED on R219's un-hardened bar. RESULT: RED 找前面的红色
  的东西 → GROUNDED verified=True 1/1; GREEN 找前面的绿色的东西 → RAN verified=False (1/11 spurious, aggregate
  refuses → discriminates, not always-True). Real bare REPL, NL-started sim (marker `sim start g1 ok 1.6s`
  = real SimStartTool, not chat claim), in-process (launch_explore_seen=False). Verdict = oracle
  detection_matches_gt vs unauthorable MuJoCo seg centroid. → g1.perception CONFIRMED N=3 (R224 2/2 + R225
  1/1), supersedes the R224 provisional. The world-config hardening made perception RELIABLE where R219's
  un-hardened bar was a lucky sample. BOARD flipped confirmed; LESSONS frontier + E50 promoted. Sim torn
  down (scripts/sim-teardown), no orphan; check.sh green.

frontier: BOTH cross-embodiment axes now CONFIRMED on the 2nd embodiment (current brain, 0 kernel edits):
  nav (E49) AND perception (E50, N=3). That is a FLOOR. The frozen g1/go2 apartment is now the local hill
  (R200 ambition critic): zero scene diversity, no clutter/occlusion, no 2nd world. Un-crossed bars: (1) a
  2nd WORLD / clutter / occlusion variant via CONFIG (Inv.3, NON-gated) to prove plug-and-play breadth; (2)
  a genuinely-NEW 3rd embodiment (BYO URDF+manifest, S4-gated); (3) D182 world-owned NL→object grounder
  (spine gate).

next:
  1. [FRONTIER/breadth, NON-gated] Add a 2nd world / scene variant via CONFIG (Inv.3 — worlds are config,
     one generic driver, no kernel edits): clutter or occlusion or a distinct room, then re-run an existing
     confirmed bar (fetch or g1.perception) on it to prove plug-and-play holds off the frozen apartment.
     This attacks the R200 local-hill critic directly and needs no gate.
  2. [FRONTIER/breadth, GATED] a genuinely-NEW 3rd embodiment via BYO URDF+manifest — needs S4 one-generic-
     driver (WIRING:53) + new MuJoCo assets; scope as multi-round SDD.
  3. [FRONTIER/robustness, GATED] land the D182 world-owned NL→object grounder (CEO spine gate).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4; dashscope key Arrearage-blocked R217) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair audited clean. No new crossings R213-R225.
last_review: R210
