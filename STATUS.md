# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R223 (E50 REFUTED) VERIFY — adjudicated the R219 g1.perception provisional: it did NOT reproduce
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R223 (E50, VERIFY/adjudication). Cleared the R222 quarantine (unadjudicated R219 provisional +
  stale BOARD). Re-ran g1_accept TWICE foreground on the bare face, deepseek-v4-flash, to adjudicate R219's
  E50 g1.perception GROUNDED 1/1: BOTH runs gave RED=RAN 0/6 and 0/17 — GROUNDED did NOT reproduce.
  Ruled out regression (git af0cf05..HEAD empty for worlds/oracle/detect) and query-phrasing (R219 grounded
  with the SAME `红色的东西`); the red stool is static (oracle docstring) → root cause is FOV/tol-marginality:
  the dino box lands outside the seg-centroid tol on ~2/3 of samples (E47/R215 fragility class, now on the
  PERCEPTION axis). Banked a `refuted` acceptance row + E50 refuted experiments row superseding R219; BOARD
  regenerated (g1.perception → refuted). LESSON recorded: g1.perception RED GROUNDED is not a reliable bar.

frontier: Cross-embodiment is CONFIRMED on the nav axis (E49) but REFUTED on the perception axis (E50 R223 —
  non-reproducible at current tol). The plug-in surface is not the bottleneck; the g1 head-cam view is too
  marginal to be an acceptance bar. Un-crossed bars: (1) HARDEN g1.perception non-gated — re-frame the g1
  head-cam / stool so the red stool is centrally framed (world config, NOT loosening the oracle — Inv.1);
  (2) a genuinely-NEW 3rd embodiment (BYO URDF+manifest, S4-gated); (3) D182 world-owned NL→object grounder.

next:
  1. [FRONTIER/robustness, non-gated] HARDEN g1.perception into a reliable bar: re-frame the g1 head camera
     (or the red-stool placement) so the target is centrally framed in g1's spawn view — a WORLD/config
     change (worlds are config, Inv.3), NOT a verify-loosening (widening the seg-centroid tol would make the
     sandbox looser = Inv.1 violation → gated). Then re-run g1_accept for a robust GROUNDED N≥2.
  2. [FRONTIER/breadth] a genuinely-NEW 3rd embodiment via BYO URDF+manifest — needs S4 one-generic-driver
     (CEO-gated, WIRING:53) + new MuJoCo assets; scope as multi-round SDD.
  3. [FRONTIER/robustness] land the D182 world-owned NL→object grounder (CEO spine gate).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4; dashscope key Arrearage-blocked R217) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair audited clean. No new crossings R213-R223.
last_review: R210
