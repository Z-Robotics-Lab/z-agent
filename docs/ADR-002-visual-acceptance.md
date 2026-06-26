# ADR-002 — Visual acceptance: the screen-watching second witness + the verify subsystem

**Status:** Accepted (design). Implementation STAGED — Stage 1 non-gated (the same-process
snapshot hook); Stage 2+ (live VLM judge, attended `:0`+RViz, self-edit loop) are CEO gates.
**Date:** 2026-06-26 · branch `arch/plug-and-play`.
**Context doc:** CLAUDE.md North Star (bare `vector-cli` + NL is the only acceptance face; the
honest-verify spine is the moat; Rule 11) + the find-grasp phase (DECISIONS D88-D98). Companion:
the **autonomous self-edit orchestration** lives OUTSIDE this repo in `~/.claude/workflows/
autonomous-visual-dev.workflow.js` — this ADR is the in-product **verify subsystem** it drives.

## Context

The project's acceptance has been unit tests + glancing at `ros2 topic echo`. It **never actually
looked at MuJoCo or RViz**. That gap produced the project's worst class of bug: every find-grasp
"REAL-SIM VERIFIED" milestone (D91-D95) ran a harness that **stubbed the VLM and hand-built
perception, bypassing the real launcher** — the headline "find-grasp works" was convincing-but-
unproven, exactly what the North Star forbids. The bare `vector-cli` + NL + **real VLM** E2E fetch
has, to date, never been demonstrated.

The honest-verify spine (`vcli/cognitive/`, byte-frozen since D69) reads MuJoCo ground truth the
actor cannot author — `holding_object` (weld 0→1), `lifted_z` (`_LIFT_MIN_Z=0.10`,
`worlds/arm_sim_oracle.py`), `at_position`, plus the `actor_causation` motion gate
(`DISPLACEMENT_EPS=0.02`, `actor_causation.py:364`, downgrades GROUNDED→RAN on teleport/slide).
This is necessary and is the moat. But it is **structurally blind** to a whole failure surface the
owner has repeatedly caught only by eye: a floating/sliding/clipping robot, a black or stale render,
the commanded target not in frame, the gripper not visibly enclosing the object, a frozen viewer,
RViz showing no costmap/path, "moved 1 m in one blink". A pose-reading oracle cannot see these; a
human watching the screen can.

The repo already has the raw materials but never assembled them into an acceptance gate:
`tools/visual_grasp.py:42-50` (EGL offscreen `mj.Renderer` → PNG), `tests/harness/pty_cli.py`
(real bare-cli PTY, `live=True` real LLM/VLM), `tools/measure_*_reliability.py` (N real subprocess
runs, GT-weld graded), `vcli/verdict.py:182` (the `VECTOR_VERDICT` sentinel). It also has a
**mis-wired** vision verifier (`vcli/cognitive/visual_verifier.py`): it fires only on GT *failure*,
uses the robot's own d435 POV (blind to its own body), and grades by keyword overlap with no
ABSTAIN — wrong on three axes; not reusable as a witness.

## Decision

Add a **visual second witness** as a first-class, in-product **verify subsystem**, and treat it as
an extension of the plug-and-play **Verify contract** — not merely internal QA. (One of the five
North-Star contracts is "bring a world-side predicate reading independent GT — how success is
proven." The visual witness is that contract, made *watchable*: a developer plugs in a robot/skill
and the platform **watches it work and proves it**.)

### 1. Layered acceptance (vision can never soften the moat)

```
L0  UNIT/pytest        changed module + frozen contract tests. Necessary, never sufficient.
L1  GT-ORACLE (moat)   the VECTOR_VERDICT from a REAL bare-cli PTY turn. Deterministic oracle
                       predicates consumed non-tautologically + actor_causation motion gate.
                       The ONLY path to verified=True. Fails CLOSED. GT FAIL ⇒ REJECT, full stop.
L2  VISION WITNESS     VisionJudge over the same-process frame strip. Rubric ORTHOGONAL to the
                       oracle (never "did it succeed?"). Emits PASS|FAIL|ABSTAIN into a NEW field
                       that NEVER feeds evidence_passed. Additive falsification only.
L3  BARE-CLI NL E2E    the whole flow through the bare REPL + natural language, real API, watched.
                       A capability behind a flag/-p/script is NOT done.
```

**The disagreement rule is the product, not noise:**
- GT-PASS + vision-PASS ⇒ **ACCEPT**.
- GT-PASS + vision-FAIL/ABSTAIN ⇒ **RED_FLAG** — the high-signal oracle-vs-vision disagreement
  (exactly the D91-D95 stub/bypass class the symbolic oracle is blind to). Records, does NOT count
  clean, BLOCKS any headline, AUTO-INVOKES red-team.
- GT-FAIL ⇒ **REJECT** regardless of vision (vision never rescues a fail).
- GT-PASS + vision-UNAVAILABLE (API down) ⇒ ACCEPT_WITH_WARNING (coverage gap logged).

### 2. How it watches the screen (verified against this machine: X11 `:0`, EGL, `import`+`ffmpeg`, `rviz2`)

- **Unattended (default; no display dep):** `MUJOCO_GL=egl` offscreen readback **inside the same
  PTY child** that ran the live bare-cli turn — the `visual_grasp.py` pattern generalized into
  `capture.snapshot()`. A free third-person `MjvCamera` (NOT the robot d435 POV). One frame per VGG
  step boundary + a final canonical frame (≥640×480). Runs headless under the supervisor.
- **Attended (owner present; RViz visible):** the CLI runs the GUI MuJoCo window on `:0` and, when
  the full ROS2 bridge is active, `rviz2 -d config/nav2_go2.rviz`. Capture grabs the **real desktop**
  — `import -window root` (still) + `ffmpeg -f x11grab -i :0` (clip → fps-sampled frames). The
  witness sees the exact pixels the owner sees, including whether a window even opened. The robot is
  ALWAYS commanded via bare `vector-cli` + NL — screen-watch is **read-only**, never GUI-clicking.

### 3. The honesty invariants (the non-negotiable spine)

- **Vision can only DOWNGRADE, never UPGRADE.** The frozen `evidence_passed` /
  `classify_step_evidence` stays the SOLE path to GROUNDED; a vision PASS may never flip a GT
  FAIL/RAN to GROUNDED. A contract test (mirroring `test_verdict_matches_evidence_passed`) asserts
  no vision field can change `verified`.
- **Vision questions ORTHOGONAL to the oracle.** Only perceptual/embodiment questions the
  pose-reading oracle is blind to (upright vs floating, rendered vs black, target in-frame,
  gripper-enclosing, no teleport across the strip). Each atomic, one-frame-answerable, mandatory
  justification.
- **Fail-closed on uncertainty.** ABSTAIN / low-confidence / blank-or-stale frame / API-unavailable
  all count as NOT-PASS and a red-team trigger — never a tie-break that loosens the gate.
- **Same-process / same-instance frame.** The verification frame MUST come from the SAME sim process
  that executed the bare-cli turn (a `VECTOR_SNAPSHOT_DIR` hook in the child, written just before the
  `VECTOR_VERDICT` sentinel), with proof the real launcher + real VLM ran (token-usage receipt;
  non-black, non-stale frame). NEVER a second freshly-built in-process sim
  (`scripts/g1_capstone_demo.py`'s separate-sim frame is the D91-D95 bypass renamed — explicitly
  rejected). NEVER a stub-VLM / FakeToolScriptBackend on any acceptance path.
- **Motion judged by deterministic pose-delta as the HARD channel.** `actor_causation` CAUSED/
  UNCAUSED + `DISPLACEMENT_EPS` is the gate for gait-vs-slide / floating / teleport; multi-frame
  vision only NARRATES why and raises a flag — never the sole motion judge.
- **No GT leak into the frame or its annotation.** Cameras render a fixed world pose or the
  PERCEIVED (not GT) object; any Set-of-Marks annotation derives from the perception pipeline/pixels,
  never the GT predicate (verify anchors invisible to the means).
- **Generator model ≠ Evaluator model.** The judge VLM is a different family from the routing brain
  (e.g. judge = gpt-4o via OpenRouter while the brain routes deepseek).
- **Vision verdicts stay OUT of the replayable gate.** They are non-replayable (live API + drift):
  the frame PNG + exact prompt + model id + raw response are stored as an audit artifact alongside
  the trace; `evidence_passed` stays reproducible from the trace alone.

### 4. Module map (in-repo verify subsystem)

| File (new unless noted) | Role |
|---|---|
| `tools/acceptance/capture.py` | `snapshot()` / `record()` — EGL offscreen + real `:0` (import/ffmpeg); free third-person `CamSpec`. Extracted from `tools/visual_grasp.py:42-50`. |
| `tools/acceptance/sim_lock.py` | global `fcntl.flock` on `~/.claude/loops/vector_sim.lock` + `pgrep`/`free -g` preflight + nuke-after. The one-sim-globally discipline the repo lacks today (OOM root). |
| `tools/acceptance/gate.py` | `AcceptanceGate(gt_verdict, vision_verdict)` — downgrade-only; disagreement → RED_FLAG. The ONLY bridge; never touches `evidence_passed`. |
| `tools/acceptance/visual_e2e.py` | the harness: sim-lock → drive REAL bare-cli (`pty_cli`, `live=True`, `VECTOR_SNAPSHOT_DIR`) → collect verdict+frames → gate → emit `AcceptanceRecord.json`. Extends `tools/verify_fetch_cli.py` + `measure_*_reliability.py`. |
| `vcli/cognitive/vision_judge.py` | the VLM witness (replaces the mis-wired `visual_verifier.py`): orthogonal atomic rubric, ABSTAIN-fail-closed, K-sample-on-suspicion, reuses the `perception/vlm_go2.py:266-347` `_call_model` HTTP shape at ≥640×480. |
| `vcli/...` verdict path | a PNG-only `VECTOR_SNAPSHOT_DIR` hook before the `VECTOR_VERDICT` sentinel (`verdict.py:182`). Contract-tested inert w.r.t. `verified`. |
| `config/` (frozen) | the rubric, a held-out acceptance set, `config/nav2_go2.rviz`. |

`AcceptanceRecord` (verdict + frames + VisionVerdict + disagreement) joins the cold-read resume
stack so a compaction loses nothing.

### 5. The placement boundary (eyes here, hands elsewhere)

This subsystem is the **eyes** — it ships, is tested, and is documented with the product; the
plug-and-play platform's "Verify" feature. The **hands** (the autonomous hypothesis→edit→verify→
keep/revert self-editor) are general dev-process methodology and live in `~/.claude/workflows/
autonomous-visual-dev.workflow.js`, parameterized per project. The seam between them is the
black-box **`AcceptanceRecord` + exit-code contract**: this harness is usable WITHOUT the
self-editor (a human, CI, or a plug-in developer runs it), and the self-editor is usable for any
project that exposes such a harness. Fusing them would prevent both from being reusable.

**Frozen-surface ownership:** the GT oracle, `verdict.py`/`trace_store.py`/`actor_causation.py`,
the VisionJudge rubric, the capture code, the gate, and the held-out set are **CI-checksum-pinned,
read-only to any self-edit branch** — a self-improver physically cannot weaken its own gate. This
cross-layer read-only contract is the foundation of the whole design's honesty.

## Why Stage 2+ is GATED

Per `rules/common/agents.md`, these cross the CEO gates and are queued, not crossed autonomously:
- **Judge VLM model + outbound API** (new external dep + cost). Recommend judge = gpt-4o via
  OpenRouter (reachable; HTTP 200) vs deepseek routing — preserves generator≠evaluator.
- **RViz capture** requires the full ROS2 bridge (`_launch_ros2_stack` + `config/nav2_go2.rviz`) —
  cross-package data flow; scope to attended demos, not the everyday gate.
- **apt deps** (`Xvfb`, `x11-utils`/`wmctrl`/`xdotool`) — only for unattended faithful screen+RViz
  / precise window-crop. The everyday path needs only `import`+`ffmpeg`+EGL (present). Defer.
- **Self-edit MERGE-TO-MASTER** is a release gate (dispatcher merges; CEO approves). Worktree
  editing itself is non-gated.

## Consequences / staged build plan

- **Stage 0 (foundation):** `sim_lock.py` + confirm live VLM reachability via OpenRouter routing.
- **Stage 1 (FIRST SPIKE, non-gated, no network):** extract `capture.snapshot()` + the PNG-only
  `VECTOR_SNAPSHOT_DIR` hook + a contract test proving it cannot touch the verdict. Demonstrate on
  one real `--sim-go2` fetch via the offline-gradable reliability path: a non-black, same-process
  third-person PNG lands paired with the verdict. The loop now has eyes on the actual run — real,
  not paper.
- **Stage 2 (gated):** `vision_judge.py` + `gate.py` + red-team call site; a forced-black render
  yields a GT-pass + vision-FAIL disagreement that auto-fires red-team and blocks the headline.
- **Stage 3 (non-gated):** temporal strip + `actor_causation` pose-delta cross-check (injected
  teleport caught by the hard channel, narrated by vision).
- **Stage 4 (gated):** attended real-`:0` + RViz launcher-truth witness (a bypassed launcher caught
  as window-never-opened).
- **Stage 5 (gated):** the self-edit experiment loop (the `~/.claude` Workflow), AcceptanceGate as
  the commit gate, frozen surface read-only, never auto-merge master.

- **The frozen spine stays byte-identical** — vision rides outside the gate; `verdict.py` /
  `trace_store.py` / the oracles are unchanged.
- **No new pip deps** for the core (`mujoco`, `cv2`, `httpx`, `numpy` already imported); the new
  files are pure-stdlib + existing-dep.

## Alternatives considered (rejected)

- **Vision as a grader of task success** (asking "did it grasp?") — rejected: duplicates the oracle,
  re-imports VLM hallucination into the gate, and lets a soft judge override the moat.
- **A second freshly-built in-process sim for the frame** (the `g1_capstone_demo.py` pattern) —
  rejected: it proves nothing about the turn that produced the verdict; it is the D91-D95 bypass.
- **Reusing `visual_verifier.py`** — rejected: wrong trigger (on GT failure), wrong camera (robot
  POV), wrong grading (keyword overlap, no ABSTAIN).
- **Putting the self-editor inside the product repo** — rejected: it is dev-process, not a product
  capability; fusing it breaks the reusability of both layers (see §5).
