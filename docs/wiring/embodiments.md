# embodiments — how it plugs in

verified-against: e7adec0

- Invariant 3: embodiments are CONFIG, not code — a robot enters via `vector_os_nano/embodiments/<id>/robot.yaml` (go2/, g1/ today), never a kernel or driver edit.
- A robot.yaml is parsed fail-loud into frozen dataclasses by `vector_os_nano/embodiments/config.py::load_embodiment_config` → `config.py::parse_embodiment_config` → `EmbodimentConfig` (model / spawn / stance / sensors / policy / capabilities / grasp). Frozen dataclasses change ADDITIVELY only (new field last + default, Invariant 7).
- The sim drivers stand the body up and stash the manifest: `vector_os_nano/hardware/sim/mujoco_go2.py::MuJoCoGo2` and `mujoco_g1.py::MuJoCoG1` each call `load_embodiment_config("<id>")` at connect and store it as `self._config` — the handle `capability_profile._declared_profile` reads back at runtime.
- Drivers implement the duck-typed contract `vector_os_nano/hardware/base.py::BaseProtocol` (connect/walk/set_velocity/get_position/get_heading/get_lidar_scan/…) — the agent binds one as `agent._base` (plus `_arm`/`_gripper`/`_perception`).
- The DofLayout seam: `vector_os_nano/embodiments/dof_layout.py::DofLayout(model, root_body, num_actuated)` introspects the root freejoint's qpos/qvel slice addresses from the COMPILED model (replaces per-driver literals; g1's `mujoco_g1.py::_G1Offsets` is now a thin adapter subclass). `dof_layout.py::build_stance_vector` builds the nominal stance FROM the manifest's `stance:` dict in model joint order; `dof_layout.py::build_robot_geom_set` gives the lidar self-filter geom set.
- Capabilities: `config.py::CapabilityProfile` (has_base/has_arm/has_gripper/camera/lidar) is declared in robot.yaml, but the ONE runtime resolver is `vector_os_nano/embodiments/capability_profile.py::resolve_capability_profile(agent)`.
- Resolver authority split: GATED flags (has_base, camera) are runtime-presence-authoritative (byte-identical to the old `agent._base is not None` probes); ENRICHMENT flags (has_arm/has_gripper/lidar) reconcile runtime-OR-declared (honest go2+Piper runtime attach). `agent is None` (dev world) → all False.
- Its three consumers (all gates single-sourced, can't drift): `vector_os_nano/vcli/native_loop.py::_build_motor_tools` (navigate gate on has_base; manipulation-skill gate on has_arm), `vector_os_nano/vcli/worlds/robot.py::_agent_has_camera` (detector registration), `vector_os_nano/vcli/engine.py::init_vgg` (`_has_base` → nav decompose vocab, ~line 428).
- g1 example: camera-bearing, has_arm:false → native loop drops `_ARM_REQUIRING_SKILLS`, detect verifies via `detection_matches_gt` (g1_perception_oracle.py).
- Pending stages (docs/ARCHITECTURE.md ladder): **S4** = ONE generic driver class + embodiment registry replacing the per-driver `MuJoCoGo2`/`MuJoCoG1` classes (CEO-gated); **S5** = policy plugin (the `policy.ref/spec` block becomes a loadable plugin instead of driver-interpreted); **S6** = capability planner-exposure (shift GATED flags' authority to the DECLARED manifest — a behavior change when declared and runtime diverge, deliberately deferred).
- Adding a robot today: write robot.yaml (+ model assets) and a driver honoring BaseProtocol; after S4 the driver disappears — manifest only.

```
anchors:
vector_os_nano/embodiments/config.py::load_embodiment_config
vector_os_nano/embodiments/config.py::parse_embodiment_config
vector_os_nano/embodiments/config.py::EmbodimentConfig
vector_os_nano/embodiments/config.py::CapabilityProfile
vector_os_nano/embodiments/capability_profile.py::resolve_capability_profile
vector_os_nano/embodiments/capability_profile.py::_declared_profile
vector_os_nano/embodiments/dof_layout.py::DofLayout
vector_os_nano/embodiments/dof_layout.py::build_stance_vector
vector_os_nano/embodiments/dof_layout.py::build_robot_geom_set
vector_os_nano/hardware/base.py::BaseProtocol
vector_os_nano/hardware/sim/mujoco_go2.py::MuJoCoGo2
vector_os_nano/hardware/sim/mujoco_g1.py::MuJoCoG1
vector_os_nano/hardware/sim/mujoco_g1.py::_G1Offsets
vector_os_nano/vcli/engine.py::init_vgg
```
