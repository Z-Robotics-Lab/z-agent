# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R205 (E40) — quantity-place ROBUSTNESS: GROUNDED but FLAKY (2/3), not deterministic
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R205 (E40, build). Robustness re-run of R204/E39 quantity-place (把两个瓶子放到架子上, deepseek-chat)
  on the REAL bare face, N=2 (launch_explore_seen=False all runs). Campaign incl R204 = GROUNDED 2/3:
  run1 verified=False (1/3, brain abandoned obj-2 → only 1 bottle placed — the R199 v4-flash failure mode
  RECURRING on deepseek-chat); run2 verified=True (3/3, 2 bottles on receptacle, eyes-confirmed red+green).
  FINDING: E39 was NOT pure luck (self-decomposition of 两个 reproduces on the majority) but is NOT reliable —
  deepseek-chat is FLAKY (~1/3 abandons obj-2). Adjudicated R204 quantity-place.nl provisional → confirmed
  GROUNDED-FLAKY 2/3 (supersedes b9d842b). Plug-and-play thesis holds (brain-swap moved the ceiling, zero
  kernel edits) but DETERMINISTIC quantity grounding still needs a runner-side guardrail.

frontier: The single-object/quantity NL ceiling on the frozen 3-object go2 scene is now well-mapped and
  witness-only (D182). Quantity is FLAKY, not solved. Two ungated frontiers plus the standing PIVOT:
  (a) brain-agnostic QUANTITY guardrail — a native_loop per-object grasp→place decomposition so quantity
  grounds DETERMINISTICALLY regardless of brain (would also fix v4-flash, which never self-decomposes);
  (b) BREADTH (R200 ambition critic, still the highest-leverage move): a 2nd scene/world variant OR the
  world-owned NL→object grounder (D182 spine gate) — the loop has polished NL on ONE frozen scene ~12 rounds.

next:
  1. [FRONTIER] brain-agnostic quantity guardrail: add a native_loop QUANTITY decomposition (detect N target
     bottles → per-object grasp→place loop, forbid navigate-as-terminal-goal) so 两个 grounds DETERMINISTICALLY
     on BOTH deepseek-chat (fix the 1/3 flake) and v4-flash (never self-decomposes). Verify N≥3 → deterministic.
  2. [PIVOT/breadth] prove plug-and-play beyond one scene: add a 2nd scene/world variant OR land the
     world-owned NL→object grounder (D182 spine gate, CEO) — rather than more single-object NL on the frozen scene.
  3. [cleanup] next-round §1b: supersede the 2 R205 per-run robustness provisionals (run1 REFUTED, run2 GROUNDED)
     — already summarized by the R205 confirmed campaign row; just append the supersedes rows.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SELF-APPROVAL AUDIT (R200 review, since last_review R190): only crossed gate = G-187-1 (CEO-APPROVED
    self-delegate) — D183 [RULING] filed. No un-audited self-approvals. Next audit at R210 review.
  - SPINE (D182): actor-authored verify target — world-owned NL→object grounder would fix witness-only fidelity.
    META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6 ladder ·
    BILLING (external: VLM-judge + BYO-N≥4) · RELEASE: restructure merge to master (owner).
last_review: R200
