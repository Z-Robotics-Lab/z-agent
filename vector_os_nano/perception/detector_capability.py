# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""DetectorCapability — the learned open-vocab detector as a routable capability.

Wraps :class:`GroundingDinoDetector` behind the Phase-C Capability contract
(``vcli/cognitive/capabilities/types.py``) so a ``detect`` sub-goal can be ROUTED
to a second model family alongside the chat LLM. Read-only (``side_effecting=False``)
— it only perceives. Per the protocol, ``invoke`` reports only that the detector
RAN; the sub-goal's deterministic verify predicate (evaluated by the GoalExecutor)
decides real success — the capability never self-certifies.

Lives OUTSIDE ``vcli/cognitive/`` (the frozen verify+routing seam): it is domain
perception code that the robot world registers into the kernel's registry.
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from vector_os_nano.vcli.cognitive.capabilities.types import CapabilityResult


class DetectorCapability:
    """Open-vocabulary detector as a routable, read-only capability.

    Payload (the sub-goal's ``strategy_params``):
        - ``query``: str  (REQUIRED) — natural-language target ("the can").
        - ``rgb``: (H,W,3) uint8 array  (one of rgb / perception required)
        - ``perception``: an object exposing ``get_color_frame()`` (alternative
          to a raw ``rgb`` — the live RGB-D backend supplies the frame).
    Output: ``{"detections": [Detection.to_dict, ...], "boxes": [...],
    "labels": [...], "scores": [...]}``.
    """

    name = "detect"
    kind = "detector"
    side_effecting = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "rgb": {"type": "array"},
            "perception": {"type": "object"},
        },
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "detections": {"type": "array"},
            "boxes": {"type": "array"},
            "labels": {"type": "array"},
            "scores": {"type": "array"},
        },
    }

    def __init__(
        self, detector: Any = None, perception: Any = None, agent: Any = None
    ) -> None:
        # Default to the shared lazy singleton so this capability and the grasp
        # route share ONE loaded model. Injectable for tests (no torch load).
        self._detector = detector
        # Optional bound RGB source (exposes ``get_color_frame()``), supplied at
        # registration by the world. The capability-dispatch path builds a
        # SkillContext (not a perception), so the kernel context cannot itself
        # yield a frame; binding the world's perception here lets the routed
        # ``detect`` sub-goal perceive WITHOUT any kernel/cognitive change. Stays
        # None for dev/CI; ``_resolve_rgb`` then falls back to the payload/context.
        self._perception = perception
        # COLD-TURN rebind (R37 Task B): register_capabilities runs at init_vgg,
        # BEFORE a mid-session NL `启动 go2 带机械臂` boots the arm — so the agent's
        # ``_perception`` is None at bind time and a snapshot would stay None forever.
        # Hold the AGENT instead and pull its LIVE ``_perception`` lazily at invoke
        # time, so a cold product turn (sim started this same turn) perceives without
        # any pre-boot. World-side wiring only; the cognitive seam is untouched.
        self._agent = agent

    def _live_perception(self) -> Any:
        """The current frame source: a snapshot perception, else the agent's LIVE one.

        Prefers an explicitly-bound ``perception`` (tests / a world that already had
        one); otherwise reads ``agent._perception`` fresh on every call so a sim
        started AFTER registration is picked up (cold-turn rebind). Returns None when
        neither yields a source (dev/CI) — the payload/context fallback then applies.
        """
        if self._perception is not None:
            return self._perception
        agent = self._agent
        if agent is not None:
            return getattr(agent, "_perception", None)
        return None

    def _get_detector(self) -> Any:
        if self._detector is None:
            from vector_os_nano.perception.grounding_dino import get_shared_detector
            self._detector = get_shared_detector()
        return self._detector

    def estimate(self, payload: dict[str, Any]) -> tuple[float, float]:
        # Cheap, no I/O: a free, ~0.3 s prior for routing/tiebreak.
        return (0.0, 0.3)

    def invoke(self, payload: dict[str, Any], context: Any) -> CapabilityResult:
        start = time.monotonic()
        if not isinstance(payload, dict):
            return CapabilityResult(success=False, error="payload must be a dict")
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            return CapabilityResult(
                success=False,
                error="missing required input: query (non-empty string)",
            )

        rgb = self._resolve_rgb(payload, context, self._live_perception())
        if rgb is None:
            return CapabilityResult(
                success=False,
                error="no RGB frame: supply 'rgb' or a 'perception' with get_color_frame()",
                latency_sec=time.monotonic() - start,
            )

        try:
            detections = self._get_detector().detect(rgb, query)
        except Exception as exc:  # noqa: BLE001
            return CapabilityResult(
                success=False,
                error=f"detector error: {exc}",
                latency_sec=time.monotonic() - start,
            )

        output = {
            "detections": [d.to_dict() for d in detections],
            "boxes": [list(d.bbox) for d in detections],
            "labels": [d.label for d in detections],
            "scores": [d.confidence for d in detections],
        }
        # success reports only that it RAN AND found something (per the protocol
        # docstring); the sub-goal's verify decides the real outcome.
        return CapabilityResult(
            success=bool(detections),
            output=output,
            latency_sec=time.monotonic() - start,
        )

    @staticmethod
    def _resolve_rgb(
        payload: dict[str, Any], context: Any, bound_perception: Any = None
    ) -> np.ndarray | None:
        """Get an (H,W,3) RGB frame from the payload rgb, a perception, or context.

        Source priority: an explicit ``rgb`` array, then the payload's
        ``perception``, then the capability's REGISTRATION-BOUND perception, then
        a ``context`` that itself yields a frame (``get_color_frame`` or a
        ``.perception`` exposing it). The bound source is how the routed ``detect``
        sub-goal reaches the live go2 camera — the kernel context is a SkillContext
        (no frame), so without it the capability route cannot perceive.
        """
        rgb = payload.get("rgb")
        if isinstance(rgb, np.ndarray) and rgb.ndim == 3:
            return rgb
        # A SkillContext exposes its perception via ``.perception``; unwrap it so a
        # context-only call can still reach a frame source.
        ctx_perception = getattr(context, "perception", None)
        for src in (
            payload.get("perception"),
            bound_perception,
            context,
            ctx_perception,
        ):
            getter = getattr(src, "get_color_frame", None)
            if getter is not None:
                try:
                    frame = getter()
                except Exception:  # noqa: BLE001 — best-effort frame source
                    frame = None
                if isinstance(frame, np.ndarray) and frame.ndim == 3:
                    return frame
        return None
