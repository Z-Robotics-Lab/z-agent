# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R233 (E54) BUILD — SIM-BLOCKED 3rd round (sibling Isaac /workspace/go2w
  screenshot hung ~108min, Inv-5 ONE-sim, un-killable per NEVER-KILL-INFRA). Refused to blind-fix
  the grasp gap before the diagnostic run (respects Hypothesis Loop); instead sharpened the
  DIAGNOSIS: the acceptance harness was LOSING its eyes-frames (wrote them to /tmp SNAP, never
  copied out) — now auto-persists to var/evidence/R<N> so the next sim window is decisive with EYES.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R233 (E54, BUILD, non-gated). check.sh was red at cold start (BOARD stale from
  supervisor's R232 rounds.jsonl append) → regen floor committed (b36376a). Then: `vlm_guard.py`
  gained pure `resolve_evidence_dir` (VECTOR_EVIDENCE_DIR > var/evidence/R<ROUND_N> > None; never
  /tmp) + `persist_evidence` (copies *.png/*.log, best-effort/idempotent); wired into `repl_accept.py`
  tail. 24/24 harness unit green (9 new), py_compile clean. Acceptance-face e2e NOT verified this
  round (needs a sim) — provisional; the next warehouse run is BOTH the H1-H4 adjudication AND this
  wiring's e2e proof (it will now auto-save frames). No blind grasp fix shipped — diagnosis first.

frontier: Make the confirmed HOUSE green fetch TRANSFER zero-shot to go2_warehouse. Harness now
  confound-proof (R231) + trace-capable (R232) + FRAME-PRESERVING (R233). NEW BAR unchanged:
  adjudicate H1-H4 in ONE decisive verbose+framed run, then fix the top cause.

watch: sibling Isaac sim (/workspace/go2w, not our loop/REGISTRY) held the ONE-sim slot ~108min hung,
  blocking R231/R232/R233's decisive warehouse run. NOT a CEO gate; not ours to kill (NEVER-KILL-INFRA).

next:
  1. [DEBUG/VERIFY, NON-gated] ONCE host sim-free (pgrep -f "mujoco|isaac|vcli" empty + free -g):
     `VECTOR_ACCEPT_VERBOSE=1 ... go2_warehouse ... MODE=fetch` ONCE. It now auto-saves frames to
     var/evidence/R<N>. grep `[PGRASP]` for arrival get_position() + per-scan detection AND LOOK at
     the eyes frame → adjudicate H1(off-frame)/H2(blind)/H3(approach)/H4(scan-dir). Also the E52 N=2.
  2. [DEBUG/breadth, NON-gated] Apply the diagnosed fix (nav standoff / approach re-pose for the
     compact enclosure) and re-verify green fetch GROUNDED in go2_warehouse; promote fetch.nl-new-world-warehouse.
  3. [FRONTIER/breadth, GATED] a NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver
     (WIRING:53) + new MuJoCo assets; multi-round SDD.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4 + PERCEPTION VLM look/describe_scene, all OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R230): gate/token audit R211..R230 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R230
