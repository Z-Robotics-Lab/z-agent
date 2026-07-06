# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Build combined Go2 + Piper MJCF via MuJoCo MjSpec attach API.

Regenerate when mount pose (xyz / orientation) needs tuning, or when
upstream Go2 / Piper assets update.

Usage:
    cd zeno/hardware/sim/mjcf
    python3 go2_piper/build_go2_piper.py
"""
from __future__ import annotations

import os
from pathlib import Path

import mujoco

# Mount pose — Piper base origin relative to Go2 base_link
# x=-0.02: 15cm behind the Livox MID-360 lidar (lidar at x=0.15)
# y=0:    centerline
# z=0.06: top of trunk collision box (trunk half-height = 0.057)
MOUNT_POS = [-0.02, 0.0, 0.06]
MOUNT_QUAT = [1.0, 0.0, 0.0, 0.0]  # identity — Z-up, X-forward (same as Go2 trunk)

# Piper body mass scale. Set to 1.0 to use the real ~2kg arm mass from
# Menagerie — this is required for Piper's own position actuators
# (kp=80, kv=5) to stay numerically stable in stow pose. Scaling down
# causes under-damped oscillation and drifts the arm out of home.
# Real-mass arm is fine for Go2 locomotion (verified by direct Python
# test: full-mass Piper + Go2 walks 0.75m in 3s under sinusoidal gait).
PIPER_MASS_SCALE: float = 1.0


def main() -> None:
    this_dir = Path(__file__).resolve().parent      # .../mjcf/go2_piper
    mjcf_root = this_dir.parent                     # .../mjcf

    go2 = mujoco.MjSpec.from_file(str(mjcf_root / "go2" / "go2.xml"))
    piper = mujoco.MjSpec.from_file(str(mjcf_root / "piper" / "piper.xml"))

    # Dynamically decouple Piper from Go2 locomotion: scale all Piper link
    # masses + inertias by PIPER_MASS_SCALE. With gravcomp=1 already set on
    # every Piper body, the arm holds pose under gravity, and the tiny mass
    # means arm motion does not disturb the dog's trot.
    if PIPER_MASS_SCALE != 1.0:
        for body in piper.bodies:
            if body.mass > 0.0:
                body.mass = float(body.mass) * PIPER_MASS_SCALE
                body.inertia = [float(v) * PIPER_MASS_SCALE for v in body.inertia]

    # Rewrite mesh file paths to ABSOLUTE paths for the compile step only —
    # MjSpec.attach asset resolution is then independent of any meshdir/anchor
    # semantics. The serialized XML is relativized below (repo-relocatable).
    go2_assets = (mjcf_root / "go2" / "assets").resolve()
    piper_assets = (mjcf_root / "piper" / "assets").resolve()
    for mesh in go2.meshes:
        if not os.path.isabs(mesh.file):
            mesh.file = str(go2_assets / mesh.file)
    for mesh in piper.meshes:
        if not os.path.isabs(mesh.file):
            mesh.file = str(piper_assets / mesh.file)
    go2.meshdir = ""
    piper.meshdir = ""

    # Attach Piper at the mount frame inside Go2's base_link
    go2_base = go2.body("base_link")
    mount_frame = go2_base.add_frame(pos=MOUNT_POS, quat=MOUNT_QUAT)
    go2.attach(piper, prefix="piper_", frame=mount_frame)
    go2.compile()

    # Relativize the mesh paths in the serialized text so the checked-in XML
    # survives a repo move/clone (a baked absolute prefix went stale when the
    # repo moved from ~/Desktop/zeno to ~/Desktop/z-agent). Textual, not on
    # the live spec: to_xml() re-resolves mesh files (and drops meshdir), so
    # spec paths must stay absolute until after serialization. The paths are
    # relative to meshdir="../go2/assets", which resolves to the same
    # directory from go2_piper/ (direct from_xml_path load) and from go2/
    # (the legacy <include> scene) — both are siblings under mjcf/.
    # scene_builder.build_room_scene absolutizes them at load time via
    # robot_meshes_dir (the g1 seam).
    xml = go2.to_xml()
    xml = xml.replace(f'file="{go2_assets}/', 'file="')
    xml = xml.replace(f'file="{piper_assets}/', 'file="../../piper/assets/')
    if str(go2_assets) in xml or str(piper_assets) in xml:
        raise RuntimeError("absolute mesh path survived relativization")
    if "<compiler " not in xml:
        raise RuntimeError("no <compiler> element in serialized XML")
    xml = xml.replace("<compiler ", '<compiler meshdir="../go2/assets" ', 1)

    out = this_dir / "go2_piper.xml"
    out.write_text(xml)
    print(f"Wrote: {out}")

    model = mujoco.MjModel.from_xml_path(str(out))
    print(f"Sanity: nbody={model.nbody}, njnt={model.njnt}, nu={model.nu}")


if __name__ == "__main__":
    main()
