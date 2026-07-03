# DEBUG — warehouse green-fetch transfer gap (R232/E54, sim-blocked OBSERVE+HYPOTHESIZE)

Why a confirmed HOUSE green fetch does NOT transfer zero-shot to go2_warehouse (R229/E52,
R231 clean-route N=1). This round the host had a **sibling Isaac warehouse sim live**
(Inv-5 ONE-sim) so NO MuJoCo sim could launch — this is the static OBSERVE+HYPOTHESIZE
pass; the falsifying EXPERIMENTs are designed for next round's ONE sim-free warehouse run.

## OBSERVE (from var/evidence/R231, clean local-VLM route, ZERO 402 — confound ruled out)
Two-phase failure on `把绿色的瓶子拿过来`, plan = [fetch_green_bottle via perception_grasp_skill, handover]:
- **Phase A** `[1/2] fetch_green_bottle failed — verification failed` @26.7s. A FULL
  perceive→approach→grasp→verify cycle ran (26.7s is not a fast perceive-fail) and
  `holding_object()` came back False → it perceived SOMETHING, acted, ended NOT holding.
- **Phase B** (brain replan) `[3/2] grasp_green_bottle failed — Scanned 6 headings; no
  plausible near-table target for 'green bottle' within 1.6 m (closest seen inf m). The
  object is not perceivable from this arrival framing`. `closest seen inf` ⇒ `_perceive_with_scan`
  got gp=None at the arrival heading AND all 6 scan headings — ZERO detections anywhere
  (perception_grasp.py:1574-1582).
- Outcome `[FAIL] 1/2 steps` @84s. Route line: `perception VLM auto-routed to local Ollama`
  → NOT the E53 402 confound (R230 caveat disproven at N=1, per R231).

Ruled out by static evidence:
- **Spawn/pose identical.** Green pickable `10.88 3.00 0.320` byte-for-byte in both XMLs.
  Dog spawn `(10.0,3.0)` is set PROGRAMMATICALLY in `mujoco_go2.connect()` room path
  (qpos[rq+0..2], world-independent); the `home` keyframe (line 734) is ONLY the flat/`else`
  branch, so the warehouse XML's missing `<keyframe>` is IRRELEVANT. Stance + Piper stow identical.
- **Lighting comparable.** house headlight 0.5/0.4 vs warehouse 0.55/0.35; bay lights ~0.55.
  Both have blue-grey haze (house 0.15/0.25/0.35, warehouse 0.20/0.22/0.24) — negligible at 0.88 m.
- **Background should HELP green.** Warehouse is uniformly desaturated grey (concrete floor,
  steel walls, grey skybox); the HSV green resolver's `_SAT_MIN=140` (front_object.py:22) should
  find a vivid green bottle MORE easily against grey, not less.

**CRITICAL BLIND SPOT:** the raw REPL log carries ZERO `[PGRASP]` lines. The non-verbose CLI
pins `vector_os_nano.skills` / `.perception` loggers to ERROR (cli._QUIET_LOGGERS), so arrival
`get_position()` and per-scan-heading detection counts are invisible. We CANNOT yet separate
framing (dog elsewhere) from detection (dog faces green, still None) from approach-miss.
→ FIXED THIS ROUND: `VECTOR_ACCEPT_VERBOSE=1` adds `--verbose` (logging-only; face unchanged).

## HYPOTHESIZE (ranked by evidence, then ease of falsification)
| # | hypothesis | category | evidence |
|---|---|---|---|
| H1 | In the compact 9×8 box the FAR/navigate standoff parks the dog at a DIFFERENT arrival pose than the open 20×14 house (near steel walls: W x=7.5 →3.4 m, S y=0 →3 m give strong lidar returns), leaving green out of the d435 FOV at all 6 scan headings | nav/framing | skill self-diagnoses "arrival framing"; Phase-B inf-at-ALL-headings; enclosed vs open room is the ONLY verified world diff |
| H3 | Phase A's perceive+approach+grasp displaced the dog (approach walked it past/beside the table) → Phase B re-perceives from a bad pose; grasp itself IK-missed the once-seen bottle | approach/grasp | Phase A ran 26.7s and perceived-then-missed (holding_object False), THEN Phase B can't re-find |
| H2 | Correctly framed, HSV/grounding-dino still fails: a render/exposure diff drops the bottle's rendered saturation <140, OR the orange racking / brown crates steal front-object salience | detection/render | Phase-B zero detections; `_SAT_MIN=140` is a hard classical cut. WEAKER: grey bg should aid green |
| H4 | The 6×0.6 rad (~206°) scan sweeps the wrong half — arrival heading into the open bay, sweep never crosses the table bearing | scan geometry | inf at all 6. LOW prior: 206°>half-turn; Phase A perceived first |

## EXPERIMENT (designed — needs the ONE sim-free warehouse run next round)
Single decisive run (host must be sim-free — check `pgrep -f "mujoco|isaac|vcli"` + `free -g` first):
```
VECTOR_ACCEPT_VERBOSE=1 VECTOR_ROOM_TEMPLATE=.../go2_warehouse.xml \
  VECTOR_PROVIDER=deepseek DEEPSEEK_MODEL=deepseek-v4-flash MODE=fetch \
  python tools/acceptance/repl_accept.py '把绿色的瓶子拿过来' '' wh_r233 fetch
```
Then `grep '\[PGRASP\]' repl.raw.log`:
- arrival `get_position()` ≈ (10,3)? — falsifies/confirms **H1** (dog parked elsewhere).
- per-scan `scan step k/6: found/none d=.. plausible=..` — none at every heading with dog
  facing table ⇒ **H2** (detection), not framing.
- Phase A approach `approach: dist/yaw/standoff` + grasp IK result — confirms/falsifies **H3**.
- scan-step headings vs table bearing atan2(3-y,10.88-x) — **H4**.

## CONCLUDE (this round)
Root cause UNRESOLVED — every hypothesis needs the sim to falsify and the sim was Inv-5-blocked.
Most-likely = H1 (compact-enclosure nav parks the dog off-frame) or H3 (approach displaced it),
because the skill self-diagnoses arrival framing AND Phase A perceived-then-missed; H2 is the
plausible-but-weaker fallback. Instrumentation (VECTOR_ACCEPT_VERBOSE) added + unit-tested so a
single next-round run adjudicates all four. Regression: tests/harness/test_vlm_guard.py::TestReplCliArgv.
