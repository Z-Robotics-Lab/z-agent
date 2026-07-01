"""Classify each place_campaign RESULT line into a failure mode + print the rate."""
import json, sys, re
log = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/place_campaign_R14.log"
rows = []
for ln in open(log):
    ln = ln.strip()
    if not ln.startswith("RESULT"):
        continue
    try:
        rows.append(json.loads(ln[len("RESULT "):]))
    except Exception:
        pass
n = len(rows)
grounded = grasp_fail = transport = rolloff = settling = other = 0
for r in rows:
    # grounded if resting at verdict OR after settle
    g = r.get("resting") or r.get("resting_t2") or r.get("resting_t4")
    if not r.get("grasp_ok", False):
        grasp_fail += 1; mode = "grasp_fail"
    elif g:
        grounded += 1; mode = "GROUNDED"
    elif r.get("diag") == "object_lost_in_transport" or r.get("held_after") is False and not r.get("bottle_in_region", True):
        transport += 1; mode = "transport_loss"
    elif r.get("bottle_in_region") is False:
        rolloff += 1; mode = "roll_off"
    elif r.get("bottle_in_region") is True:
        settling += 1; mode = "in_region_not_atrest(settling?)"
    else:
        other += 1; mode = "other/" + str(r.get("diag") or r.get("fail") or r.get("error"))
    b = r.get("bottle"); print(f"  {mode:30s} resting={r.get('resting')},{r.get('resting_t4')} diag={r.get('diag')} bottle={b} in_region={r.get('bottle_in_region')} held_after={r.get('held_after')}")
print(f"\nN={n}  GROUNDED={grounded}  grasp_fail={grasp_fail}  roll_off={rolloff}  transport={transport}  settling={settling}  other={other}")
if n: print(f"place rate (grasp-ok denom) = {grounded}/{n-grasp_fail} = {grounded/max(1,n-grasp_fail):.2f}   overall = {grounded}/{n} = {grounded/n:.2f}")
