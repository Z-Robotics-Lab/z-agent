# DEBUG — courtyard PLACE mid-walk drop (R256/E60)

## OBSERVE
- Symptom (R255): compound courtyard PLACE → RAN verified=False. Grasp holding_object CAUSED=True,
  then during mobile_place the held bottle is LOST; brain sees '瓶子…掉了' → re-grasp thrash → ends
  empty-armed, resting_on_receptacle=False. Eyes: no bottle placed.
- Across N=3 real runs courtyard PLACE is FLAKY (R246 2/3, R253 1/1, R255 dropped). R253's _NAV_RETRIES
  fix (absorb a transient first-nav MISS) is real but INSUFFICIENT — the residual is a MID-WALK DROP,
  not a nav-miss (do NOT re-diagnose as nav-miss; E23/R253 already fixed that).
- Two distinct "holding" signals in code:
  - `gripper.is_holding()` (mujoco_piper_gripper.py:150) → software flag `_held_object`, set at grasp,
    cleared ONLY by `open()`/`_release_all()`. Never cleared by locomotion.
  - `holding_object()` oracle (arm_sim_oracle.py:125) → GT: requires software-flag AND object lifted
    (z>=_LIFT_MIN_Z=0.10) AND within `_NEAR_EE_RADIUS=0.08m` of the EE. This is what the brain's verify
    and the acceptance oracle read.
- The weld (scene_builder.py:175) pins the object's RELATIVE pose to piper_link6 at DEFAULT solref/solimp
  (no stiffness set). The go2 walks a real trot gait (mujoco_go2.walk → set_velocity + 1kHz daemon step),
  so the base bounces/accelerates while carrying.

## HYPOTHESIZE
| # | hypothesis | category | evidence |
|---|------------|----------|----------|
| H1 | Weld COMPLIANCE under trot: object lags EE by >0.08m transiently during the gait, so holding_object() flickers False while eq_active stays 1 (object never actually leaves the gripper) | physics/oracle-threshold | default weld solref + trot accelerations; _NEAR_EE_RADIUS=0.08 tight vs a 0.06 grasp offset |
| H2 | Weld SEPARATION: constraint force exceeded, object physically detaches (eq_active still 1 but object on floor, or a collision knocks it) | physics | "lost in transport" honest-fail path already exists (mobile_place.py:608) — a real floor-drop was seen before |
| H3 | READ RACE: holding_object() reads get_object_positions() and _ee_position() at different 1kHz-daemon instants while the base moves fast → spuriously inflated distance, no real drop | concurrency | navigate_to docstring warns mj_forward races the daemon; EE instantaneous velocity during trot ≫ 0.4 m/s nominal |
| H4 | DOCK repose (Step-6b `_grasp_ready_repose`/`_approach_object`) swings the arm/object into the table/bin → collision knocks it off | physics | Step-6b runs arm+base motion right before the drop |

## EXPERIMENT
Probe: `scripts/debug_r256_midwalk_drop.py` — in-process go2+Piper+gripper (courtyard), NO brain/VLM.
Grasp the green bottle (assert holding_object True), then base.navigate_to an approach ~1 m away in a
thread while sampling at ~30 Hz: object-EE distance, object z, eq_active(weld), is_holding flag,
holding_object(). Records max distance excursion + whether eq_active ever flips + whether object hits floor.

- H1 CONFIRMED iff: dist_max > 0.08 during walk BUT eq_active stays 1 AND object z stays lifted (returns
  <0.08 when stable) → transient compliance, not a real drop.
- H2 CONFIRMED iff: object z → floor (<0.10) and stays, or eq_active flips to 0.
- H3 CONFIRMED iff: excursion vanishes when sampled with the daemon paused / two stationary re-reads disagree.
- H4 CONFIRMED iff: the drop only appears during the Step-6b dock, not the plain navigate walk.

→ result pending run.

## CONCLUDE
(pending)
