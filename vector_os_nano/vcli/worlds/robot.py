# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Robot world shim.

Phase A keeps the robot path working exactly as before: this shim is the
registration *surface* (persona + "use kernel defaults" for vocab), while the
robot verify namespace and skill tools continue to be built by the engine/CLI
as today. It deliberately imports nothing robot-specific at module load.
"""

from __future__ import annotations

import logging
from typing import Any

from vector_os_nano.vcli.prompt import ROBOT_ROLE_PROMPT, ROBOT_TOOL_INSTRUCTIONS

logger = logging.getLogger(__name__)


def _agent_has_camera(agent: Any) -> bool:
    """True iff *agent* can supply an RGB frame the detector can run on.

    World-agnostic CAMERA-presence check (R4): a frame source is either a bound
    ``_perception`` exposing ``get_color_frame()`` (go2+arm's Go2GraspPerception,
    g1's G1HeadPerception) OR a base/arm exposing ``get_camera_frame()`` (the raw
    MuJoCo camera, e.g. MuJoCoG1). Reaching the frame source through the SAME
    duck-typed accessors the detector itself uses keeps this embodiment-agnostic —
    the detector needs a camera, not an arm. Fails safe to False (no-agent / sensorless).
    """
    if agent is None:
        return False
    perception = getattr(agent, "_perception", None)
    if perception is not None and callable(getattr(perception, "get_color_frame", None)):
        return True
    for member in (getattr(agent, "_base", None), getattr(agent, "_arm", None)):
        if member is not None and callable(getattr(member, "get_camera_frame", None)):
            return True
    return False


def _make_perceived_detections(agent: Any) -> Any:
    """Build ``detect_objects(query="")`` over the LEARNED detector's last observation.

    The no-arm/camera-only verify anchor (R4): returns the boxes/labels the
    grounding-dino route last localized on the live camera (stashed by the native
    detect tool as ``agent._last_detection``), shaped like the arm oracle's
    ``detect_objects`` output (a list of ``{"name", "score", "bbox"}`` dicts) so
    ``len(detect_objects()) > 0`` reads truth-bearingly. A non-empty ``query``
    substring-filters by label. Fails safe to ``[]`` (no detection yet / read error)
    — it NEVER fabricates: an empty list when the model saw nothing, never a default
    truthy stub. This reports the MEANS' real observation, and the step grades RAN
    (read-only perception), never GROUNDED-by-causation — the moat is not loosened.
    """

    def detect_objects(query: str = "") -> list[dict[str, Any]]:
        last = getattr(agent, "_last_detection", None)
        if not isinstance(last, dict):
            return []
        boxes = last.get("boxes") or []
        labels = last.get("labels") or []
        scores = last.get("scores") or []
        q = (query or "").strip().lower()
        out: list[dict[str, Any]] = []
        for i, box in enumerate(boxes):
            label = str(labels[i]) if i < len(labels) else "object"
            if q and q not in label.lower():
                continue
            score = float(scores[i]) if i < len(scores) else 0.0
            out.append({"name": label, "score": score, "bbox": list(box)})
        return out

    return detect_objects


class RobotWorld:
    """Adapter for the robot domain (Go2 / SO-101 / Piper)."""

    name = "robot"

    def is_robot(self) -> bool:
        return True

    def persona_blocks(self) -> tuple[str, str]:
        return ROBOT_ROLE_PROMPT, ROBOT_TOOL_INSTRUCTIONS

    def register_tools(self, registry: Any, agent: Any) -> None:
        # Robot/diag/sim tools are registered by the CLI from discover_*; skill
        # wrappers are added via wrap_skills(agent) at startup. No-op here in
        # Phase A (the full robot-world migration is Phase C).
        return None

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        # Ground the verifier on the SIM deterministic oracle(s). The engine
        # builds its dev/robot bindings + empty perception stubs first
        # (engine._build_verifier_namespace), then merges THIS on top — so when a
        # sim embodiment is present these predicates REPLACE the stubs (e.g.
        # detect_objects->[], describe_scene->"") with real ground-truth lookups,
        # and the planner's verify allowlist (derived from this namespace) gains
        # them. Single-sourced from the kernel-side oracles (ADR-008 C1 / kernel
        # rule 3); lazily imported here so the module load stays robot-free.
        #
        # Compose whatever embodiment(s) the agent actually has, so an arm-only,
        # a go2-base-only, OR a go2+arm agent each get a GROUNDED verify namespace
        # (world-agnostic — no embodiment is special-cased). Real hardware / no
        # sim oracle contributes nothing, leaving the engine namespace byte-
        # identical. object_names=() => all scene objects (the plain robot world
        # has no Scenario to declare a known-set).
        ns: dict[str, Any] = {}

        arm = getattr(agent, "_arm", None)
        if arm is not None and hasattr(arm, "get_object_positions"):
            from vector_os_nano.vcli.worlds.arm_sim_oracle import (
                make_arm_at_home,
                make_describe_scene,
                make_detect_objects,
                make_holding_object,
                make_placed_count,
            )
            ns.update({
                "detect_objects": make_detect_objects(agent, ()),
                "describe_scene": make_describe_scene(agent, ()),
                "holding_object": make_holding_object(agent),
                "arm_at_home": make_arm_at_home(agent),
                "placed_count": make_placed_count(agent),
            })

        base = getattr(agent, "_base", None)
        if (
            base is not None
            and hasattr(base, "get_position")
            and hasattr(base, "get_heading")
        ):
            # Ground the base predicates the go2 vocab verifies against. The plain
            # robot world has no Scenario, so ``visited`` (which needs a named-room
            # set) is left to the playground; ``at_position`` / ``facing`` need
            # only the live base and replace the engine stubs.
            from vector_os_nano.vcli.worlds.go2_sim_oracle import (
                make_at_position,
                make_facing,
            )
            ns.update({
                "at_position": make_at_position(agent),
                "facing": make_facing(agent),
            })

        # R4: a CAMERA-bearing agent WITHOUT an arm (g1: head camera, no manipulator)
        # has no ground-truth ``get_object_positions`` to anchor ``detect_objects`` on,
        # so the arm path above never supplied it. Bind a perception-fed
        # ``detect_objects()`` that reports what the LEARNED detector last localized on
        # the live camera (``agent._last_detection``, stashed by the native detect
        # route). This makes ``verify(len(detect_objects()) > 0)`` truth-bearing on g1
        # WITHOUT a manipulator — and it grades RAN (read-only perception, no actor
        # causation), the honest D50 grade for a perceive-only step. World-agnostic: a
        # capability-check (camera, no arm), never an embodiment special-case. NOT
        # added when an arm already supplied the ground-truth ``detect_objects`` (the
        # GT anchor stays the moat there; we never overwrite it with the means' output).
        if (
            "detect_objects" not in ns
            and _agent_has_camera(agent)
            and getattr(agent, "_arm", None) is None
        ):
            ns["detect_objects"] = _make_perceived_detections(agent)

        return ns

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        # Register the learned open-vocabulary DETECTOR (grounding-dino-tiny) as a
        # routable second model family. Read-only — it only perceives; the verify
        # spine remains the sole grader (the capability never self-certifies).
        #
        # Guarded two ways so dev / sensorless / CI without weights stay byte-identical:
        #   1. torch/transformers must be importable (ImportError -> register nothing);
        #   2. the agent must actually have a CAMERA to detect on (a perception with
        #      ``get_color_frame()`` OR a base/arm with ``get_camera_frame()``) — a
        #      no-agent probe or a sensorless agent registers nothing. The detector
        #      needs ONLY a camera, not an arm: a go2+arm grasps with it, a g1 (camera,
        #      NO arm) localizes with it. So the gate is a CAMERA-presence CAPABILITY
        #      check (R4), world-agnostic — NOT an arm/embodiment special-case (rule 7).
        #      The model itself is NOT loaded here — the DetectorCapability /
        #      GroundingDinoDetector loads lazily on first detect.
        if agent is None or not _agent_has_camera(agent):
            return None
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            logger.info(
                "[ROBOT-WORLD] torch/transformers absent — detector capability "
                "not registered (path stays detector-free)"
            )
            return None
        from vector_os_nano.perception.detector_capability import DetectorCapability

        # Bind the agent's live RGB source so a PRODUCER-routed ``detect`` sub-goal
        # can perceive on the capability-dispatch path. The kernel builds a
        # SkillContext for capability invoke (it has no camera frame), so without
        # this the routed detector returns "no RGB frame". World-side wiring only —
        # the kernel/cognitive seam is untouched.
        #
        # COLD-TURN rebind (R37 Task B): register_capabilities runs at init_vgg,
        # which can precede the NL sim-start that actually boots the arm+camera — so
        # ``agent._perception`` may be None RIGHT NOW. Bind the AGENT (not the
        # current snapshot) so the capability pulls the LIVE ``_perception`` lazily at
        # invoke time; a cold product turn (sim started this same turn) then perceives
        # with no pre-boot. We still pass the snapshot perception when present (it
        # wins in _live_perception, keeping the warm path identical).
        perception = getattr(agent, "_perception", None)
        registry.register(DetectorCapability(perception=perception, agent=agent))
        logger.info(
            "[ROBOT-WORLD] registered 'detect' capability (grounding-dino), "
            "perception=%s (agent-bound for cold-turn rebind)",
            type(perception).__name__ if perception else None,
        )
        return None

    def decompose_vocab(self) -> None:
        # None => the engine derives the vocab from the live skill registry
        # (see derive_vocab_from_registry); falls back to GoalDecomposer class
        # defaults if no registry/namespace is available.
        return None

    def derive_vocab_from_registry(self) -> bool:
        # Single-source the decompose vocabulary from the skill registry so the
        # prompt, the validator allowlist, and the params-help can never drift.
        # Serves both go2 (has_base=True) and the arm (has_base=False); the
        # engine inspects the agent to decide has_base.
        return True
