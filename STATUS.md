# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R196 (E32) — ordinal fetch GROUNDED 3/3; "grasp miss" REFUTED = handover-releases-hold
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R196 (E32) — Hypothesis-Loop ISOLATED the R194/R195 ordinal "grasp miss": a MISDIAGNOSIS.
  perception_grasp GROUNDS green ordinal 5/5 skill-direct (grasp_probe VLM-stubbed: weld, lift 0.32→0.56).
  Real cause: v4-flash grasps green SUCCESSFULLY then routes `handover` on '拿过来' (bring-to-user), which
  RELEASES the weld → holding_object=False. R192 deepseek-CHAT grasped the SAME utterance and STOPPED
  →GROUNDED (model variance, E9/E10/E23; so E30 "REFUTED" was a MODEL change). FIX: native_loop "BRING IS
  COMPLETE AT THE HOLD" (bare 拿过来 finishes at the hold; handover only on 递给我/给我). Non-spine,
  holding_object unchanged. REAL-FACE: '把最左边的瓶子拿过来' GROUNDED 3/3 on v4-flash (was 1/2), 0
  handover, green held aloft (eyes). +Case 16 +regression test.

frontier: ordinal fetch GROUNDED 3/3 (E32). RAISE (STATUS next): quantity (两个/两瓶 — gripper holds ONE,
  needs place/stage between grasps) + anaphora (那个/它 → last-referenced object). AMBITION: a world-owned
  NL→object spatial grounder (D182 spine, CEO-gated) removes model-strategy fragility.

blocked: cloud VLM/BYO credit (perception VLM + judge + BYO-N≥4) — external BILLING gate; a local
  Ollama model is the plug-and-play workaround for the perception VLM (recipe: LESSONS/.env.example).
scene (real mujoco_go2 room XML): blue(y=2.78,r=.028)=rightmost-BOTTLE, green(y=3.00,r=.028)=leftmost-
  BOTTLE, red_can(y=3.22,r=.033)=leftmost-OBJECT (excl. by 瓶子). larger world-y → smaller cx → leftmost.
  Green/blue bottles ARE grasp-reliable (probe 5/5) — the R190 "red-can-only grasp-reliable" was wrong.

next:
  1. [ADJUDICATE] R196 fetch.nl-ordinal-spatial GROUNDED 3/3 is PROVISIONAL — next round: red-team + a
     fresh bare-REPL re-run, then promote to `confirmed`. E32 debug row is `inconclusive`; promote after
     the round boundary.
  2. [FRONTIER] quantity NL: 把两个瓶子拿过来 (fetch TWO) — the gripper holds ONE, so the model must
     grasp→verify→place/stage→grasp the 2nd; bank each failure mode as a Casebook case, not just a count.
     Then anaphora (那个/它). Reuse repl_accept.py MODE=fetch; keep the utterance predicate-matched.
  3. [DEBT] 6 aging N=1 provisional rows (R168/174/176/177/182/184) — all superseded by R183/R186
     (check.sh supersession-aware, non-blocking); batch-close on review R200.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder would fix E25/E30/E32
    model-strategy fragility. META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6
    ladder · BILLING (external) · RELEASE: restructure merge to master (owner).
last_review: R190
