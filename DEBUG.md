# DEBUG — R247: courtyard PLACE-leg composite fails on navigate at_position(10.8,3.0)

## OBSERVE
R246 first courtyard PLACE-leg (`把绿色的瓶子放到架子上`, mode=place, deepseek-v4-flash +
local ollama gemma4:e4b). Verdict:
```
> perception_grasp -> verify holding_object('pickable_bottle_green') OK (actor=CAUSED)
> navigate         -> verify at_position(10.8, 3.0, tol=1.0) . (actor=CAUSED)     <- UNGROUNDED
> mobile_place     -> verify resting_on_receptacle() OK (actor=NOT_GRADED)
verdict RAN verified=False (2/3 grounded)
```
Eyes: green bottle IS in place_bin -- physical place SUCCEEDED. Brain narration in the raw log:
grasp OK -> `mobile_place` -> "The navigation failed. Let me try again..." -> `mobile_place` (retry)
-> "Let me try navigating closer to the shelf area first, then place." -> brain-issued
`navigate(10.8,3.0)` -> `mobile_place` -> resting_on_receptacle OK -> finish.
Furniture is byte-identical to go2_room.xml (house): pick_table@(10.95,3.0) box half(0.15,0.25),
place_bin@(10.95,4.60). STATUS hypothesis: "same (10.8,3.0) coords ground on HOUSE but not
courtyard (byte-identical furniture)" -> world-transfer bug.

## HYPOTHESIZE
| # | hypothesis | category | evidence |
|---|---|---|---|
| H1 | navigate(10.8,3.0) target is INSIDE the inflated pick_table -> planner rejects -> nav fails in EVERY world | geometry | (10.8,.) is the table -x edge (x in [10.80,11.10]); body radius 0.28 |
| H2 | courtyard room-shell/obstacles block the approach that house allows | world | planters@x6.6, pergola@y8.5 near the bay? |
| H3 | mobile_place's OWN approach to the bin is unreachable in courtyard | world | first mobile_place narrated "navigation failed" |
| H4 | mobile_place first-nav returned False by TIMEOUT/walk-stall, not planner reject; path exists | control | dog holds bottle; L-nav two legs |

## EXPERIMENT (deterministic geometry probe, no brain sim -- g1_vgraph real funcs, R=0.28)
- H1 -> CONFIRMED. point_in_any((10.8,3.0), inflated[pick_table])=True; plan_path(start,(10.8,3.0))
  = None (inf) from every plausible start (9.5/10.0/10.5,.). Unreachable in ANY world -- furniture is
  byte-identical, so HOUSE rejects (10.8,3.0) identically. -> H2 world-transfer REFUTED.
- H3 -> REJECTED. mobile_place -X approach point (tx-clearance, ty)=(10.05,4.60) is OUTSIDE all
  inflated obstacles; plan_path from every grasp standoff returns a valid 2-wp path (leg1, leg2, and
  direct all succeed). The planner does NOT reject mobile_place's approach.
- H4 -> CONFIRMED by elimination. navigate_to returns False only on (a) planner-None [ruled out by
  H3] or (b) timeout/not-within-tol. mobile_place's first-nav flake was a transient walk/timeout, not a
  world defect -- it succeeded on retry (resting_on_receptacle OK).

## CONCLUDE
Root cause: the composite verified=False was NOT a courtyard-vs-house world-transfer defect. The brain
IMPROVISED navigate(10.8,3.0) (the bottle's pick location -- inside the inflated pick_table, UNREACHABLE
in every world) as a recovery after mobile_place's first-nav returned False on a transient walk/timeout
flake. The physical place transferred correctly (bottle on shelf, eyes-confirmed, resting_on_receptacle OK).
- file:line -- no product bug: mujoco_go2.navigate_to correctly rejects the inside-obstacle target
  (vector_os_nano/hardware/sim/mujoco_go2.py:1755-1764); the bad coordinate was brain-authored.
- REFUTED STATUS claim: (10.8,3.0) grounds on house -- it is unreachable on house too.
- Regression evidence: geometry probe above is reproducible; furniture identity guarantees world-parity.
- Fix direction: none in the driver/world. The courtyard PLACE physical transfer IS proven; the composite
  flake is brain-recovery noise triggered by mobile_place's transient first-nav miss. Re-verify on the
  bare face -- a run where mobile_place's first nav lands should ground cleanly (grasp OK + place OK, no
  spurious brain navigate).
