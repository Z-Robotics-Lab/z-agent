# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R230 (E53) REVIEW — skeptic GROUNDED the oldest bar on the real face, but uncovered an ACTIVE OpenRouter-402 perception-VLM confound; R229 E52 warehouse adjudicated refuted (with confound caveat).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R230 (E53, REVIEW §7). (a) SKEPTIC re-ran the oldest fundamental confirmed bar (fetch.nl-
  plain-colour green fetch) on the real bare face, current brain v4-flash: GROUNDED 1/1 — holding_object
  ('pickable_bottle_green') GT actor=CAUSED, eyes self-read (green held aloft, house), de-staled 39→0.
  (b) R229 E52 warehouse provisional ADJUDICATED → refuted (0/2 zero-shot). (c) Re-red-teamed R228/E51
  scene-clutter CONFIRMED → SURVIVES (weldless same-hue decoy ⇒ holding_object GT unfakeable). (d) Gate
  audit R211..R230 CLEAN; WIRING 21 rounds old (<25); Casebook 14 (<15).
  CONFOUND (the real finding): the perception VLM (look/describe_scene, vlm_go2.py) is OpenRouter-402
  credit-exhausted NOW (E28 ACTIVE). Control run WITHOUT the local Ollama route FAILED — brain escalated to
  look → 402 → silent spin, no verdict; WITH VECTOR_VLM_URL local route → clean GROUNDED. ⇒ the R229 E52
  warehouse 0/2 is very likely the SAME confound, not a world-transfer failure. Sims torn down by exact PID
  (a false-DONE pgrep briefly left 2 sims — caught+reaped, memory at baseline). Banked 2 acceptance + E53.

frontier: Breadth pivot (E48-52) answered the R200 local-hill critique, but R230 exposes the acceptance
  HARNESS as the weak link — a perception-VLM 402 fails SILENTLY (spins to no-verdict), so recent breadth
  "refutations" (E52) are of UNKNOWN provenance. NEW BAR (non-gated): harden repl_accept (default local VLM
  route + fail-loud on a look 402), THEN re-open E52 new-world transfer cleanly.

next:
  1. [HARNESS-HARDEN, NON-gated] Make tools/acceptance/repl_accept.py confound-proof: (a) default
     VECTOR_VLM_URL=localhost:11434 + VECTOR_VLM_MODEL=gemma4:e4b when unset AND Ollama is up (probe
     /api/tags), else fail-loud with the recipe; (b) detect a look/describe_scene 402 in the REPL stream and
     ABORT with a distinct VLM-BILLING-402 marker (never a silent no-verdict spin). TDD: unit test feeds a
     canned 402 stream, asserts the loud abort. Makes every future breadth verdict billing-confound-free.
  2. [DEBUG/breadth, NON-gated] With the hardened harness, RE-RUN green fetch in go2_warehouse WITH the
     local VLM route N≥2 (E52 do_not_retry_unless). GROUNDS ⇒ flip E52, CONFIRM new-world breadth; fails
     clean ⇒ Hypothesis-Loop the warehouse visual+lidar scene (detector/approach/framing).
  3. [FRONTIER/breadth, GATED] a NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver
     (WIRING:53) + new MuJoCo assets; multi-round SDD.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4 + PERCEPTION VLM look/describe_scene, all OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R230): gate/token audit R211..R230 CLEAN — no new CEO/GATE-APPROVED crossings since the R210 review. R209 schema-cap approval remains the last, audited clean.
last_review: R230
