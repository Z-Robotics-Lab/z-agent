# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w is a FIRST-CLASS BYO world — resolvable, tool-bearing, embodiment-providing.

The go2w world was validated as an out-of-tree plugin in P2; F2 migrates it into
the kernel's ``worlds`` package as a first-class world registered as a BUILT-IN
(lazy factory in worlds/registry.py), so ``--world go2w`` resolves it WITHOUT
``VECTOR_WORLD_PLUGINS``. These tests pin that contract at the seam level:

* ``--world go2w`` (and the ``isaac-go2w`` alias) resolve ``IsaacGo2WWorld``,
* after ``register_tools`` the tool table carries ``go2w_navigate``/``go2w_where``,
* ``build_embodiment`` returns an agent exposing ``_base`` + ``_skill_registry``,
* the ``go2w_at`` ground-truth predicate reaches the verifier through
  ``build_verify_namespace`` AND the real engine namespace builder.

Offline and LLM-free: the HTTP bridge is monkeypatched (``urllib``) so nothing
touches the network or a simulator. Ground truth = the registry/import graph and
the Protocol contract, neither of which the actor can author.
"""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from typing import Any

import pytest

from vector_os_nano.vcli.worlds import go2w as go2w_mod


# ---------------------------------------------------------------------------
# Bridge stub — no network, no sim
# ---------------------------------------------------------------------------


class _FakeResp(io.BytesIO):
    """A urlopen() context-manager stand-in returning a fixed JSON body."""

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


@pytest.fixture
def fake_bridge(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Monkeypatch go2w's urllib so /gt and /pose return fixed ground truth.

    Records every requested path so a test can assert the bridge was (not) hit.
    ``gt == pose`` => zero SLAM offset, so ``go2w_at`` grades purely on distance.
    """
    calls: list[str] = []
    state = {"gt": {"x": 1.0, "y": 2.0}, "pose": {"x": 1.0, "y": 2.0, "yaw": 0.0}}

    def _urlopen(url_or_req: Any, *a: Any, **k: Any) -> _FakeResp:
        url = url_or_req if isinstance(url_or_req, str) else url_or_req.full_url
        calls.append(url)
        if url.endswith("/gt"):
            return _FakeResp(json.dumps(state["gt"]).encode())
        if url.endswith("/pose"):
            return _FakeResp(json.dumps(state["pose"]).encode())
        if url.endswith("/waypoint"):
            return _FakeResp(json.dumps({"ok": True}).encode())
        raise AssertionError(f"unexpected bridge URL: {url}")

    monkeypatch.setattr(go2w_mod.urllib.request, "urlopen", _urlopen)
    return {"calls": calls, "state": state}


# ---------------------------------------------------------------------------
# Resolution — first-class, no VECTOR_WORLD_PLUGINS needed
# ---------------------------------------------------------------------------


def test_go2w_is_a_builtin_world_id() -> None:
    """``go2w`` and its alias are registered built-ins (no plugin env required)."""
    from vector_os_nano.vcli.worlds import get_world_registry

    names = get_world_registry().names()
    assert "go2w" in names, "go2w must be a first-class built-in world id"
    assert "isaac-go2w" in names, "the original plugin id must remain an alias"


def test_world_flag_go2w_resolves_isaac_world() -> None:
    """``--world go2w`` resolves an ``IsaacGo2WWorld`` through the CLI resolver."""
    from vector_os_nano.vcli.cli import _resolve_active_world

    args = SimpleNamespace(world="go2w", scenario=None)
    world = _resolve_active_world(args, agent=None)
    assert type(world).__name__ == "IsaacGo2WWorld"
    assert world.is_robot() is True


def test_world_flag_isaac_go2w_alias_resolves_same_world() -> None:
    """The back-compat ``isaac-go2w`` alias resolves the same world class."""
    from vector_os_nano.vcli.cli import _resolve_active_world

    args = SimpleNamespace(world="isaac-go2w", scenario=None)
    world = _resolve_active_world(args, agent=None)
    assert type(world).__name__ == "IsaacGo2WWorld"


# ---------------------------------------------------------------------------
# register_tools — the tool table gains go2w_navigate / go2w_where
# ---------------------------------------------------------------------------


def test_register_tools_adds_go2w_nav_tools_under_go2w_category() -> None:
    """After ``register_tools`` the CLI tool table carries both go2w tools."""
    from vector_os_nano.vcli.cli import _register_world_tools
    from vector_os_nano.vcli.tools.base import CategorizedToolRegistry
    from vector_os_nano.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    registry = CategorizedToolRegistry()
    _register_world_tools(world, registry, agent=None)

    tool_names = registry.list_tools()
    assert "go2w_navigate" in tool_names
    assert "go2w_where" in tool_names
    # Contributed under the world's OWN category (never a disabled kernel one),
    # so they are visible to to_anthropic_schemas().
    assert set(registry.list_categories().get("go2w", [])) == {
        "go2w_navigate",
        "go2w_where",
    }
    schema_names = {s["name"] for s in registry.to_anthropic_schemas()}
    assert {"go2w_navigate", "go2w_where"} <= schema_names, (
        "go2w tools must be visible in the exported schema (category not disabled)"
    )


# ---------------------------------------------------------------------------
# build_embodiment — the BYO front door yields a usable agent
# ---------------------------------------------------------------------------


def test_build_embodiment_returns_agent_with_base_and_skill_registry() -> None:
    """``build_embodiment`` returns an object exposing ``_base`` + ``_skill_registry``.

    ``_base is not None`` is the VGG readiness criterion; the skill registry holds
    the navigate skill the MOTION path routes to. No network — construction never
    touches the bridge.
    """
    from vector_os_nano.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    embodiment = world.build_embodiment()
    assert embodiment is not None
    assert getattr(embodiment, "_base", None) is not None
    assert getattr(embodiment, "_skill_registry", None) is not None
    # A fresh embodiment each call (no shared mutable state across sessions).
    assert world.build_embodiment() is not embodiment


def test_init_agent_uses_go2w_embodiment_without_sim() -> None:
    """``_init_agent`` with ``--world go2w`` and NO ``--sim`` yields the embodiment."""
    from vector_os_nano.vcli.cli import _init_agent

    args = SimpleNamespace(sim=False, sim_go2=False, world="go2w", scenario=None)
    agent = _init_agent(args)
    assert type(agent).__name__ == "IsaacGo2WEmbodiment"
    assert getattr(agent, "_base", None) is not None
    assert getattr(agent, "_skill_registry", None) is not None


# ---------------------------------------------------------------------------
# go2w_at predicate — exposed through build_verify_namespace and the engine seam
# ---------------------------------------------------------------------------


def test_go2w_at_is_exposed_via_build_verify_namespace() -> None:
    """The world's ``build_verify_namespace`` contributes the ``go2w_at`` predicate."""
    from vector_os_nano.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    ns = world.build_verify_namespace(agent=None)
    assert "go2w_at" in ns and callable(ns["go2w_at"])


def test_go2w_at_reads_ground_truth_from_the_bridge(fake_bridge: dict[str, Any]) -> None:
    """``go2w_at`` grades on SIM ground truth (/gt) — the verify moat, mocked bridge.

    gt == pose (zero offset), so the target grades purely on distance: the robot
    IS at (1, 2) within tolerance, and is NOT at (5, 5).
    """
    from vector_os_nano.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    at = world.build_verify_namespace(agent=None)["go2w_at"]
    assert at(1.0, 2.0) is True
    assert at(5.0, 5.0) is False
    # The predicate genuinely consulted the bridge ground truth, not a constant.
    assert any(u.endswith("/gt") for u in fake_bridge["calls"])


def test_go2w_at_reaches_the_verifier_through_the_real_engine_seam() -> None:
    """``go2w_at`` survives the REAL engine namespace builder (delivery seam).

    Wires the go2w world into a real ``VectorEngine`` exactly as a resolved
    session does (one line: ``engine._world = world``) and asserts the predicate
    name reaches ``verify_oracle_names`` — proving ``_merge_world_verify_namespace``
    actually merges ``build_verify_namespace`` for this world, not just that the
    dict contains the name. Offline: ``VectorEngine.__init__`` never calls the
    backend, and reaching the oracle NAMES needs no bridge call.
    """
    from vector_os_nano.vcli.cognitive.trace_store import verify_oracle_names
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.worlds import resolve_world_named

    engine = VectorEngine(backend=SimpleNamespace())
    engine._world = resolve_world_named("go2w")
    agent = SimpleNamespace(_base=None, _spatial_memory=None)

    names = verify_oracle_names(agent, engine)
    assert "go2w_at" in names, (
        "go2w_at did not survive the real engine namespace builder — the "
        "plug-and-play verify delivery seam regressed for the go2w world"
    )


# ---------------------------------------------------------------------------
# Bridge override — GO2W_BRIDGE reconfigures the endpoint without a code edit
# ---------------------------------------------------------------------------


def test_go2w_bridge_env_overrides_default_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``GO2W_BRIDGE`` overrides the default 127.0.0.1:8042 endpoint at call time."""
    assert go2w_mod._bridge() == "http://127.0.0.1:8042"
    monkeypatch.setenv("GO2W_BRIDGE", "http://10.0.0.5:9000")
    assert go2w_mod._bridge() == "http://10.0.0.5:9000"
