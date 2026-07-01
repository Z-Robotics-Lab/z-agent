"""g1 navigation skill-direct probe — de-risks the bare-REPL nav acceptance.

NOT the acceptance (that is bare vector-cli + NL). This is the deterministic
pre-check (mirrors grasp_probe.py for grasp): connect a real MuJoCoG1, drive
navigate_to(target) directly, then reproduce EXACTLY what the moat spine will do
on the bare face — capture an actor baseline before, a post after, grade
at_position(target) via actor_causation.grade(), and evaluate the at_position
oracle on the live base. Confirms:
  (a) which targets are REACHABLE from spawn (reached=True, no fall), and
  (b) that a genuinely skill-caused walk grades CAUSED (needs the new cmd_motion
      counter) so the bare-REPL verify can reach GROUNDED, not just RAN.

Run ONE sim at a time; `rosm nuke --yes` after. Usage:
    python g1_nav_probe.py [tx ty] [tx2 ty2] ...   (defaults to a small sweep)
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("VECTOR_NO_ROS2", "1")
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.pop("DISPLAY", None)

from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1
from vector_os_nano.vcli.cognitive.actor_causation import (
    capture_actor_baseline,
    grade,
)
from vector_os_nano.vcli.worlds.go2_sim_oracle import make_at_position


def _targets() -> list[tuple[float, float]]:
    args = sys.argv[1:]
    if len(args) >= 2:
        return [
            (float(args[i]), float(args[i + 1]))
            for i in range(0, len(args) - 1, 2)
        ]
    # Default sweep around spawn (10, 3): back, +y, forward-left.
    return [(9.0, 3.0), (10.0, 4.0), (8.5, 2.5)]


def main() -> int:
    g1 = MuJoCoG1(gui=False, room=True)
    g1.connect()
    agent = SimpleNamespace(_base=g1, _arm=None, _gripper=None)
    at_position = make_at_position(agent)
    oracle_names = frozenset({"at_position", "facing"})
    try:
        for tx, ty in _targets():
            p0 = g1.get_position()
            base = capture_actor_baseline(agent)
            res = g1.navigate_to(tx, ty)
            post = capture_actor_baseline(agent)
            pf = g1.get_position()
            verify = f"at_position({tx}, {ty})"
            actor = grade(base, post, verify, oracle_names)
            at_ok = at_position(tx, ty)
            dcmd = (post.base_cmd_motion or 0.0) - (base.base_cmd_motion or 0.0)
            dxy = ((pf[0] - p0[0]) ** 2 + (pf[1] - p0[1]) ** 2) ** 0.5
            print(
                f"target=({tx},{ty}) reached={bool(res)} reason={res.get('reason')!r} "
                f"start=({p0[0]:.2f},{p0[1]:.2f}) end=({pf[0]:.2f},{pf[1]:.2f}) z={pf[2]:.2f} "
                f"moved={dxy:.2f}m dcmd_motion={dcmd:.2f} "
                f"at_position={at_ok} actor={actor.value} "
                f"=> spine={'GROUNDED' if (at_ok and actor.value=='CAUSED') else 'RAN/UNGROUNDED'}"
            )
    finally:
        g1.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
