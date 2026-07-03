# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R219 (E50 provisional) VERIFY — refreshed 29-round-stale g1.perception with the CURRENT brain
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R219 (E50, VERIFY). Adopted the hung R218 E50 leftover (orphaned g1_accept driver+REPL holding a
  ~3GB in-process g1 sim — R217 hazard; reaped by EXACT PID, never pkill), then completed E50 fresh foreground.
  Refreshed the 29-round-stale g1.perception BOARD row (was R190 deepseek-chat) with the CURRENT routing brain
  deepseek-v4-flash on the bare face: RED 找红色 -> GROUNDED verified=True 1/1 (grounding-dino box within tol of the
  MuJoCo segmentation centroid, RGB-firewalled, GT unauthorable); GREEN 找绿色 -> RAN verified=False 0/13 — the
  model tried 13 green query variants (green bottle/can/chair/stool/object, 绿色, 绿色的物体...) and the SAME oracle
  refused every one = it DISCRIMINATES, not a trivial always-true. sim start g1 ok 1.6s (real SimStartTool marker,
  not model chat); launch_explore_seen=False (g1 in-process, camera-only, no arm). eyes=self-read (g1 detect emits
  no offscreen verdict frame in this build; the deterministic seg-GT oracle is the witness). Provisional ->
  adjudicate R220. Note: R220 is a review round (every 10th).

frontier: Cross-embodiment now REFRESHED-live on BOTH axes with the current brain — nav (E49 confirmed) AND
  perception (E50 provisional). Plug-in surface is NOT the bottleneck. Un-crossed bars, in order: (1) a
  genuinely-NEW 3rd embodiment (BYO URDF+manifest) — needs S4 one-generic-driver (CEO-gated) + new MuJoCo assets =
  multi-round SDD; (2) the D182 world-owned NL→object grounder (CEO spine gate) to kill witness-only; (3) welds+
  colour maps still HARDCODED per-object (S4/D182).

next:
  1. [adjudicate — R220 first job] promote the E50 g1.perception provisional across the round boundary: re-run
     g1_accept (RED GROUNDED + GREEN 0/N refutation) with the current brain, append a `confirmed` row superseding
     R190, OR refute. R220 is ROUND_KIND=review (§7) — fold this into the skeptic pass.
  2. [FRONTIER/breadth] a genuinely-NEW 3rd embodiment via BYO URDF+manifest — needs S4 one-generic-driver
     (CEO-gated, WIRING:53) + new MuJoCo assets, scope as multi-round SDD. Non-gated proxy is now EXHAUSTED on
     existing embodiments (go2 fetch/place/nav, g1 nav+perception all refreshed with the current brain).
  3. [FRONTIER/robustness] land the D182 world-owned NL→object grounder (CEO spine gate) so grasp-vs-wander stops
     being model-strategy/placement-dependent.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). META: `_PREDICATE_ORACLES` hardcoded; object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4; dashscope key Arrearage-blocked R217, VLM-judge still down) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair audited clean. No new crossings R213-R219.
last_review: R210
