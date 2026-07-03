# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R224 (E50) BUILD — HARDENED g1.perception into a reliable bar via a dominant central red WORLD target; GROUNDED N=2 on the bare face.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R224 (E50, BUILD). Executed STATUS next#1 — hardened g1.perception (R223 refuted it: RAN
  0/17, FOV/tol-marginal). ROOT CAUSE observed LIVE (scratchpad/g1_percept_diag.py, real seg + real dino,
  5 settle poses): the scene had MULTIPLE red geoms in g1's view (two bar stools @16/18 + red can), so the
  oracle's UNIONED seg centroid sat on the stool cluster while dino's top box (the can region) landed ~113px
  away → box↔centroid diverged >60px on ~2/3 samples. FIX (Inv.3 world config; oracle+tol BYTE-UNCHANGED =
  Inv.1, no verify-loosening): injected percept_target_red — a dominant central red panel (12.9,3.35,z1.15,
  0.64m) into _G1_EXTRA_GEOMS. Post-fix diagnostic: ~18-20k red seg px ≫ stools' 920px; dino returns ONE
  high-conf box (0.62-0.70) at 4-5px from the centroid → match 5/5, 12× margin. REAL bare-face g1_accept
  (deepseek-v4-flash), TWO independent runs: RED=GROUNDED 1/1 both; GREEN=RAN False both (0/14) → honest
  refutation intact (oracle still discriminates). N=2 banked provisional (supersedes R223). g1 oracle unit
  tests 8/8 (contract intact).

frontier: Cross-embodiment now spans BOTH axes on the 2nd embodiment (current brain, 0 kernel edits): nav
  CONFIRMED (E49) AND perception GROUNDED (E50 R224, provisional N=2). The perception bar needed a WORLD-
  config hardening to be RELIABLE, not just present — the plug-in surface held, the SCENE was the bottleneck.
  Un-crossed bars: (1) a genuinely-NEW 3rd embodiment (BYO URDF+manifest, S4-gated); (2) D182 world-owned
  NL→object grounder (spine gate); (3) breadth beyond the frozen g1 apartment (2nd world / clutter / occlusion).

next:
  1. [ADJUDICATE, R225] Promote the R224 E50 g1.perception GROUNDED N=2 provisional to confirmed (red-team
     survived a round boundary + still reproducible on the bare face), or refute with supersedes. One more
     real-face run optional for N=3.
  2. [FRONTIER/breadth] a genuinely-NEW 3rd embodiment via BYO URDF+manifest — needs S4 one-generic-driver
     (CEO-gated, WIRING:53) + new MuJoCo assets; scope as multi-round SDD.
  3. [FRONTIER/robustness] land the D182 world-owned NL→object grounder (CEO spine gate).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4; dashscope key Arrearage-blocked R217) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair audited clean. No new crossings R213-R224.
last_review: R210
