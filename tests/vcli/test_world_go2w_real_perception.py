# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real perception SKILLS — find_object / scene_query via RynnBrain (RED first).

CEO-gated round (2026-07-22): wire the local RynnBrain embodied VLM
(http://127.0.0.1:8786, JSON POST /infer) into the real-dog world as READ-ONLY
perception skills. Perception output is DECISION INPUT only — it never enters
the verify namespace (Inv-1: a VLM self-report is not ground truth; arrival is
still proven by at()/moved()/turned() odometry oracles).

Pinned here:

* RynnBrainClient coordinate parsing is a PURE function (no network in tests):
  ``<object>(x1,y1),(x2,y2)</object>`` with [0,1000]-normalized coords.
* RealFindObjectSkill ('find_object', strategy find_object_skill): frame from
  ``base.get_camera_image()`` (the None-honest accessor, NEVER the black-frame
  one) -> client -> box centre -> image side + horizontal bearing (deg,
  positive = turn left). Honest failures: no_base / camera_failed (no frame) /
  no_vlm (service down) / object_not_found (no box in the reply).
* RealSceneQuerySkill ('scene_query'): thinking-mode QA passthrough.
* Neither skill may trip the motor-keyword detector (they must wrap as
  read-only + concurrency-safe tools) — the effects/description must avoid
  the 7 MOTOR_KEYWORDS.
* Wiring: skills registered, vocab teaches both strategies, embodiment owns
  ONE shared client (services['rynn'] + driver fallback, the two-seam rule).

Hermetic: FakeRynnClient + fake driver, no network, no ROS env, no LLM.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest


def _find_skill():
    from zeno.vcli.worlds.go2w_real_perception import RealFindObjectSkill

    return RealFindObjectSkill()


def _query_skill():
    from zeno.vcli.worlds.go2w_real_perception import RealSceneQuerySkill

    return RealSceneQuerySkill()


def _ctx(base=None, services=None, instruction: str = ""):
    return SimpleNamespace(base=base, services=services or {},
                           instruction=instruction)


class _CamFakeHW:
    """Driver fake: get_camera_image() is the None-honest accessor."""

    def __init__(self, frame="rgb"):
        if frame == "rgb":
            self._frame = np.zeros((48, 64, 3), dtype=np.uint8)
        else:
            self._frame = frame  # None => never received a frame

    def get_camera_image(self):
        return self._frame

    def has_camera(self):
        return self._frame is not None


class FakeRynnClient:
    """Records calls; scripted replies. No network."""

    def __init__(self, locate_reply="<object>(700,300),(800,500)</object>",
                 ask_reply="a table with two bowls", raise_exc=None):
        self.locate_reply = locate_reply
        self.ask_reply = ask_reply
        self.raise_exc = raise_exc
        self.locate_calls: list = []
        self.ask_calls: list = []

    def locate(self, frame, description):
        if self.raise_exc is not None:
            raise self.raise_exc
        self.locate_calls.append((frame.shape, description))
        return self.locate_reply

    def ask(self, frame, question, think=True):
        if self.raise_exc is not None:
            raise self.raise_exc
        self.ask_calls.append((frame.shape, question, think))
        return self.ask_reply


# ---------------------------------------------------------------------------
# client: coordinate parsing is a pure function (no network needed)
# ---------------------------------------------------------------------------


def test_parse_boxes_single():
    from zeno.perception.rynnbrain import parse_boxes

    boxes = parse_boxes("<object>(100,200),(300,400)</object>")
    assert boxes == [((100, 200), (300, 400))]


def test_parse_boxes_multiple_and_prose():
    from zeno.perception.rynnbrain import parse_boxes

    reply = ("I can see two: <object>(10,20),(30,40)</object> and "
             "<object>(500,600),(700,800)</object>.")
    assert parse_boxes(reply) == [((10, 20), (30, 40)), ((500, 600), (700, 800))]


def test_parse_boxes_none_or_malformed_is_empty():
    from zeno.perception.rynnbrain import parse_boxes

    assert parse_boxes("no such object in view") == []
    assert parse_boxes("<object>(100,200)</object>") == []  # one point ≠ a box
    assert parse_boxes("") == []


def test_client_url_from_env(monkeypatch):
    """ZENO_-first env resolution (read_env seam), default localhost:8786."""
    from zeno.perception.rynnbrain import RynnBrainClient

    monkeypatch.delenv("ZENO_RYNNBRAIN_URL", raising=False)
    monkeypatch.delenv("VECTOR_RYNNBRAIN_URL", raising=False)
    assert "127.0.0.1:8786" in RynnBrainClient().base_url
    monkeypatch.setenv("ZENO_RYNNBRAIN_URL", "http://10.0.0.9:8786")
    assert RynnBrainClient().base_url == "http://10.0.0.9:8786"


# ---------------------------------------------------------------------------
# find_object — bearing math + honest failure ladder
# ---------------------------------------------------------------------------


def test_find_object_right_side_bearing():
    """Box centre cx=750 => right side, bearing ≈ -17.25° (negative = right)."""
    client = FakeRynnClient("<object>(700,300),(800,500)</object>")
    result = _find_skill().execute(
        {"description": "black bowl"}, _ctx(base=_CamFakeHW(),
                                            services={"rynn": client}))
    assert result.success, result.error_message
    data = result.result_data or {}
    assert data.get("side") == "右"
    assert data.get("bearing_deg") == pytest.approx(-17.25, abs=0.5)
    assert data.get("box") == [[700, 300], [800, 500]]
    assert client.locate_calls, "must query the client with the live frame"


def test_find_object_center_bearing_zero():
    client = FakeRynnClient("<object>(450,300),(550,500)</object>")
    result = _find_skill().execute(
        {"description": "plate"}, _ctx(base=_CamFakeHW(),
                                       services={"rynn": client}))
    assert result.success
    data = result.result_data or {}
    assert data.get("side") == "中"
    assert data.get("bearing_deg") == pytest.approx(0.0, abs=0.5)


def test_find_object_teaches_odometry_verify_not_self():
    """The result message must steer toward at()/turned() (decision input,
    never self-certifying) — Inv-1 in the perception seam."""
    client = FakeRynnClient()
    result = _find_skill().execute(
        {"description": "charger"}, _ctx(base=_CamFakeHW(),
                                         services={"rynn": client}))
    msg = str((result.result_data or {}).get("message", ""))
    assert "at(" in msg or "turned(" in msg


def test_find_object_without_base_fails_honestly():
    result = _find_skill().execute({"description": "x"}, _ctx(base=None))
    assert not result.success
    assert result.diagnosis_code == "no_base"


def test_find_object_without_frame_fails_honestly():
    """get_camera_image() None => never received a frame — refuse, never send
    the black fallback frame to the VLM."""
    client = FakeRynnClient()
    result = _find_skill().execute(
        {"description": "x"}, _ctx(base=_CamFakeHW(frame=None),
                                   services={"rynn": client}))
    assert not result.success
    assert result.diagnosis_code == "camera_failed"
    assert not client.locate_calls


def test_find_object_service_down_is_no_vlm():
    client = FakeRynnClient(raise_exc=RuntimeError("connection refused"))
    result = _find_skill().execute(
        {"description": "x"}, _ctx(base=_CamFakeHW(),
                                   services={"rynn": client}))
    assert not result.success
    assert result.diagnosis_code == "no_vlm"


def test_find_object_no_box_is_object_not_found():
    client = FakeRynnClient(locate_reply="I cannot see that object.")
    result = _find_skill().execute(
        {"description": "unicorn"}, _ctx(base=_CamFakeHW(),
                                         services={"rynn": client}))
    assert not result.success
    assert result.diagnosis_code == "object_not_found"


def test_find_object_client_via_driver_fallback():
    """VGG GoalExecutor contexts carry no world services — the client must
    also ride the driver (base.rynn_client), the standard two-seam rule."""
    client = FakeRynnClient()
    base = _CamFakeHW()
    base.rynn_client = client
    result = _find_skill().execute({"description": "bowl"}, _ctx(base=base))
    assert result.success
    assert client.locate_calls


# ---------------------------------------------------------------------------
# scene_query — thinking-mode QA passthrough
# ---------------------------------------------------------------------------


def test_scene_query_passes_question_with_think():
    client = FakeRynnClient(ask_reply="两只碗在桌上")
    result = _query_skill().execute(
        {"question": "桌上有什么"}, _ctx(base=_CamFakeHW(),
                                     services={"rynn": client}))
    assert result.success
    assert "两只碗在桌上" in str((result.result_data or {}).get("message", ""))
    (_shape, question, think), = client.ask_calls
    assert question == "桌上有什么"
    assert think is True


def test_scene_query_without_base_fails_honestly():
    result = _query_skill().execute({"question": "x"}, _ctx(base=None))
    assert not result.success
    assert result.diagnosis_code == "no_base"


# ---------------------------------------------------------------------------
# motor-keyword trap — both skills MUST wrap as read-only / concurrency-safe
# ---------------------------------------------------------------------------


def test_perception_skills_avoid_motor_keywords():
    """MOTOR_KEYWORDS scan preconditions+effects+description — a stray 'move'
    or a 'base'/'navigate' in the prose would silently turn a perception skill
    into a motor skill (permission ask + serialized). Pin the wording."""
    from zeno.vcli.tools.skill_wrapper import MOTOR_KEYWORDS

    for sk in (_find_skill(), _query_skill()):
        combined = " ".join([
            str(getattr(sk, "preconditions", "")),
            str(getattr(sk, "effects", "")),
            str(getattr(sk, "description", "")),
        ]).lower()
        for kw in MOTOR_KEYWORDS:
            assert kw not in combined, (sk.name, kw)


def test_perception_skills_wrap_read_only_and_concurrency_safe():
    from zeno.vcli.tools.skill_wrapper import wrap_skills
    from zeno.vcli.worlds import resolve_world_named

    emb = resolve_world_named("go2w_real").build_embodiment()
    tools = {t.name: t for t in wrap_skills(emb)}
    for name in ("find_object", "scene_query"):
        assert name in tools, f"{name} must wrap for the native loop"
        assert tools[name].is_read_only({}), name
        assert tools[name].is_concurrency_safe({}), name


def test_perception_skill_names_avoid_native_traps():
    """native_loop special-cases the names 'navigate' (dropped) and 'detect'
    (overridden) — perception skills must not collide with either."""
    assert _find_skill().name == "find_object"
    assert _query_skill().name == "scene_query"


# ---------------------------------------------------------------------------
# wiring — registration, shared client, vocab, capability card
# ---------------------------------------------------------------------------


def test_perception_skills_registered_in_embodiment():
    from zeno.vcli.worlds import resolve_world_named

    emb = resolve_world_named("go2w_real").build_embodiment()
    skills = set(emb._skill_registry.list_skills())
    assert "find_object" in skills
    assert "scene_query" in skills


def test_embodiment_owns_one_shared_rynn_client():
    from zeno.vcli.worlds import resolve_world_named

    emb = resolve_world_named("go2w_real").build_embodiment()
    client = getattr(emb, "_rynn", None)
    assert client is not None, "embodiment must own the RynnBrain client"
    assert getattr(emb._base, "rynn_client", None) is client
    assert emb._build_context().services.get("rynn") is client


def test_vocab_teaches_perception_strategies():
    from zeno.vcli.worlds import resolve_world_named

    vocab = resolve_world_named("go2w_real").decompose_vocab()
    for strategy in ("find_object_skill", "scene_query_skill"):
        assert strategy in vocab.strategies
        assert strategy in vocab.strategy_descriptions
        assert strategy in vocab.strategy_params_help
    assert set(vocab.strategy_descriptions) == set(vocab.strategies)


def test_capability_card_documents_vision():
    """The card must now advertise the perception skills, keep perception out
    of verify (decision input only), and still never say 'look skill'."""
    from pathlib import Path

    import zeno.vcli.worlds.go2w_real as world_mod

    md = (Path(world_mod.__file__).parent / "go2w_real_capabilities.md").read_text(
        encoding="utf-8")
    low = md.lower()
    assert "find_object" in low
    assert "scene_query" in low
    assert "look skill" not in low  # lifecycle contract twin
