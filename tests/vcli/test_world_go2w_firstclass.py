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

from zeno.vcli.worlds import go2w as go2w_mod


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
    from zeno.vcli.worlds import get_world_registry

    names = get_world_registry().names()
    assert "go2w" in names, "go2w must be a first-class built-in world id"
    assert "isaac-go2w" in names, "the original plugin id must remain an alias"


def test_world_flag_go2w_resolves_isaac_world() -> None:
    """``--world go2w`` resolves an ``IsaacGo2WWorld`` through the CLI resolver."""
    from zeno.vcli.cli import _resolve_active_world

    args = SimpleNamespace(world="go2w", scenario=None)
    world = _resolve_active_world(args, agent=None)
    assert type(world).__name__ == "IsaacGo2WWorld"
    assert world.is_robot() is True


def test_world_flag_isaac_go2w_alias_resolves_same_world() -> None:
    """The back-compat ``isaac-go2w`` alias resolves the same world class."""
    from zeno.vcli.cli import _resolve_active_world

    args = SimpleNamespace(world="isaac-go2w", scenario=None)
    world = _resolve_active_world(args, agent=None)
    assert type(world).__name__ == "IsaacGo2WWorld"


# ---------------------------------------------------------------------------
# register_tools — the tool table gains go2w_navigate / go2w_where
# ---------------------------------------------------------------------------


def test_register_tools_adds_go2w_nav_tools_under_go2w_category() -> None:
    """After ``register_tools`` the CLI tool table carries both go2w tools."""
    from zeno.vcli.cli import _register_world_tools
    from zeno.vcli.tools.base import CategorizedToolRegistry
    from zeno.vcli.worlds import resolve_world_named

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
        "go2w_bringup",
        "go2w_status",
    }
    schema_names = {s["name"] for s in registry.to_anthropic_schemas()}
    assert {"go2w_navigate", "go2w_where"} <= schema_names, (
        "go2w tools must be visible in the exported schema (category not disabled)"
    )


def test_register_tools_suppresses_kernel_mujoco_sim_category() -> None:
    """With go2w active, the kernel MuJoCo sim tools vanish from the schema.

    Regression for the 2026-07-06 live session: the user said "启动仿真" and the
    model routed it to the kernel's ``start_simulation`` (MuJoCo go2) instead of
    ``go2w_bringup`` (Isaac + navstack + RViz) — because with an embodied agent
    the CLI keeps ALL kernel categories enabled and both tools sat in the schema.
    The world itself must disable the ``sim`` category through the registry it
    already receives (plug-and-play: zero kernel edit). Assembled exactly like
    the CLI assembles it: full kernel toolset first, then the world hook.
    """
    from zeno.vcli.cli import _register_world_tools
    from zeno.vcli.tools import discover_categorized_tools
    from zeno.vcli.tools.base import CategorizedToolRegistry
    from zeno.vcli.worlds import resolve_world_named

    registry = CategorizedToolRegistry()
    tools_list, cat_map = discover_categorized_tools()
    for t in tools_list:
        cat = next((c for c, names in cat_map.items() if t.name in names), "default")
        registry.register(t, category=cat)
    _register_world_tools(resolve_world_named("go2w"), registry, agent=None)

    schema_names = {s["name"] for s in registry.to_anthropic_schemas()}
    assert "go2w_bringup" in schema_names
    assert "start_simulation" not in schema_names, (
        "kernel MuJoCo start_simulation must NOT be offered in the go2w world — "
        "'启动仿真' would route to the wrong simulator"
    )
    assert "stop_simulation" not in schema_names


def _assemble_go2w_registry(with_agent: bool = True):
    """Assemble the tool registry exactly as the CLI does for the go2w world.

    Full kernel toolset first, then (optionally) the wrapped skills of a real
    go2w embodiment under the ``robot`` category, then the world's
    ``register_tools`` hook. Returns the CategorizedToolRegistry.
    """
    from zeno.vcli.cli import _register_world_tools
    from zeno.vcli.tools import discover_categorized_tools
    from zeno.vcli.tools.base import CategorizedToolRegistry
    from zeno.vcli.tools.skill_wrapper import wrap_skills
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    agent = world.build_embodiment() if with_agent else None
    registry = CategorizedToolRegistry()
    tools_list, cat_map = discover_categorized_tools()
    for t in tools_list:
        cat = next((c for c, names in cat_map.items() if t.name in names), "default")
        registry.register(t, category=cat)
    if agent is not None:
        for st in wrap_skills(agent):
            registry.register(st, category="robot")
    _register_world_tools(world, registry, agent)
    return registry


def test_register_tools_suppresses_stale_diag_and_system_categories() -> None:
    """go2w disables the ``diag`` and ``system`` categories — they are all stale.

    Regression (go2w-experience audit findings #3–#6): in the go2w world every
    tool in the kernel ``diag`` category (nav_state / ros2_topics / ros2_nodes /
    ros2_log / terrain_status) reads MuJoCo-era paths or the host default ROS
    domain — but the go2w navstack runs inside docker under ROS_DOMAIN_ID=42, so
    those tools return empty/misleading data that makes the model misjudge the
    stack as dead. The ``system`` category (robot_status / open_foxglove /
    skill_reload) is likewise stale: robot_status reports in-process object
    wiring as "connected" (misleading liveness), open_foxglove starts a bridge in
    the wrong ROS domain, skill_reload is a MuJoCo-era dev tool.

    Neither category contains any go2w-own tool, so disabling them causes ZERO
    friendly-fire; go2w_status is the single source of truth for stack health.
    """
    registry = _assemble_go2w_registry(with_agent=True)
    schema_names = {s["name"] for s in registry.to_anthropic_schemas()}

    # diag category — all stale, gone.
    for stale in ("nav_state", "ros2_topics", "ros2_nodes", "ros2_log", "terrain_status"):
        assert stale not in schema_names, f"stale diag tool {stale} must be hidden in go2w"
    # system category — all stale, gone.
    for stale in ("robot_status", "open_foxglove", "skill_reload"):
        assert stale not in schema_names, f"stale system tool {stale} must be hidden in go2w"

    # go2w's own health source-of-truth stays present.
    assert "go2w_status" in schema_names


def test_register_tools_keeps_robot_category_go2w_skills() -> None:
    """Disabling diag/system must NOT collateral-kill the go2w core skills.

    navigate / explore / pick wrap into the kernel ``robot`` category (cli.py),
    so ``robot`` must stay ENABLED — the audit's explicit no-friendly-fire
    guard for finding #2/#4. world_query (also in ``robot``) stays in the schema
    but is now fail-safe (see test_robot_tools) rather than crashing.
    """
    registry = _assemble_go2w_registry(with_agent=True)
    schema_names = {s["name"] for s in registry.to_anthropic_schemas()}
    for skill in ("navigate", "explore", "pick"):
        assert skill in schema_names, (
            f"go2w core skill {skill} must stay offered — disabling robot would kill it"
        )


def test_world_declares_go2w_essential_category() -> None:
    """go2w declares ``go2w`` as an essential router category (finding #1 seam).

    The optional ``essential_categories()`` world hook is what the CLI feeds into
    the IntentRouter so route() always keeps go2w tools in scope. Pin the hook so
    a refactor can't silently drop it.
    """
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    hook = getattr(world, "essential_categories", None)
    assert callable(hook), "go2w must declare essential_categories() for routing"
    assert "go2w" in set(hook())


def test_go2w_tools_reach_model_on_routed_sim_and_nav_phrases() -> None:
    """END-TO-END routing: go2w_* tools reach the model on the LIVE routed path.

    This is the finding-#1 acceptance check the old unit tests missed: they only
    asserted go2w tools were in the DEFAULT (unfiltered) schema, never through
    ``route()`` category filtering. Here we assemble the registry AND the router
    exactly as the CLI wires them (router seeded with the world's essential
    categories), then drive the same route()->to_anthropic_schemas(categories=...)
    path engine.py runs for '启动仿真' / '导航' / '探索' / '抓'.
    """
    from zeno.vcli.intent_router import IntentRouter
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    registry = _assemble_go2w_registry(with_agent=True)
    essential = set(getattr(world, "essential_categories", lambda: set())())
    router = IntentRouter(essential_categories=essential)

    # '启动仿真'/'关闭仿真' — the go2w lifecycle tool MUST be visible.
    for phrase in ("启动仿真", "start the sim", "关闭仿真"):
        cats = router.route(phrase)
        names = {s["name"] for s in registry.to_anthropic_schemas(categories=cats)}
        assert "go2w_bringup" in names, (
            f"go2w_bringup must reach the model for {phrase!r}; got {sorted(names)}"
        )
        # The wrong (MuJoCo) sim tool must still be absent (category disabled).
        assert "start_simulation" not in names

    # Navigation / exploration / pick phrases — go2w tools + skills visible.
    for phrase, expect in (
        ("导航到 (2, 3)", "go2w_navigate"),
        ("去探索一下仓库", "go2w_status"),
        ("抓起箱子", "go2w_where"),
    ):
        cats = router.route(phrase)
        names = {s["name"] for s in registry.to_anthropic_schemas(categories=cats)}
        assert expect in names, (
            f"{expect} must reach the model for {phrase!r}; got {sorted(names)}"
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
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    embodiment = world.build_embodiment()
    assert embodiment is not None
    assert getattr(embodiment, "_base", None) is not None
    assert getattr(embodiment, "_skill_registry", None) is not None
    # A fresh embodiment each call (no shared mutable state across sessions).
    assert world.build_embodiment() is not embodiment


def test_init_agent_uses_go2w_embodiment_without_sim() -> None:
    """``_init_agent`` with ``--world go2w`` and NO ``--sim`` yields the embodiment."""
    from zeno.vcli.cli import _init_agent

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
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w")
    ns = world.build_verify_namespace(agent=None)
    assert "go2w_at" in ns and callable(ns["go2w_at"])


def test_go2w_at_reads_ground_truth_from_the_bridge(fake_bridge: dict[str, Any]) -> None:
    """``go2w_at`` grades on SIM ground truth (/gt) — the verify moat, mocked bridge.

    gt == pose (zero offset), so the target grades purely on distance: the robot
    IS at (1, 2) within tolerance, and is NOT at (5, 5).
    """
    from zeno.vcli.worlds import resolve_world_named

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
    from zeno.vcli.cognitive.trace_store import verify_oracle_names
    from zeno.vcli.engine import VectorEngine
    from zeno.vcli.worlds import resolve_world_named

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


# ---------------------------------------------------------------------------
# Teardown fidelity — the tool must NOT report success when the script fails.
# Regression for the 2026-07-06 "Isaac 杀不死" complaint: the teardown branch
# ignored the script's exit code, so a teardown that left kit-python alive still
# read as success to the model ("工具说关了实际没关"). These pin: non-zero exit
# => is_error=True + residuals surfaced; zero exit => plain success.
# Offline & LLM-free: subprocess.run is monkeypatched; no bash/docker/sim runs.
# ---------------------------------------------------------------------------


class _FakeCompleted:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _bringup_ctx() -> Any:
    """Minimal ToolContext — the bringup tool's teardown branch reads none of it."""
    import threading
    from pathlib import Path

    from zeno.vcli.tools.base import ToolContext

    return ToolContext(agent=None, cwd=Path("/tmp"), session=None,
                       permissions=None, abort=threading.Event())


def _patch_teardown_subprocess(
    monkeypatch: pytest.MonkeyPatch, result: _FakeCompleted
) -> dict[str, Any]:
    """Make the bringup tool see a valid script and a scripted subprocess result."""
    calls: dict[str, Any] = {}

    def _run(cmd: Any, *a: Any, **k: Any) -> _FakeCompleted:
        calls["cmd"] = cmd
        return result

    # The tool checks os.path.isfile(script) before running; force it True.
    monkeypatch.setattr(go2w_mod.os.path, "isfile", lambda _p: True)
    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", _run)
    return calls


def test_teardown_reports_error_when_script_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero teardown exit (residual kit-python) => is_error=True.

    This is the exact fidelity gap behind the CEO complaint: the tool must not
    claim the stack is down when the scoped teardown could not verify it.
    """
    residual = ("[teardown] FAILED: 拆链未达判据 — residual_pids='82059' l0='true'\n"
                "[teardown] 宿主侧 pgrep: 82059 /isaac-sim/kit/python/bin/python3 ...")
    _patch_teardown_subprocess(
        monkeypatch, _FakeCompleted(returncode=1, stdout="", stderr=residual))

    tool = go2w_mod.Go2WBringupTool()
    res = tool.execute({"action": "teardown"}, _bringup_ctx())

    assert res.is_error is True, "non-zero teardown must surface as is_error=True"
    assert "82059" in res.content, "the residual process table must reach the model"
    assert "FAILED" in res.content or "exit=1" in res.content


def test_teardown_reports_success_when_script_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean teardown (exit 0) stays a non-error success."""
    ok = "[teardown] SUCCESS: kit-python 已灭（宿主 pgrep 空）且 l0=false"
    _patch_teardown_subprocess(
        monkeypatch, _FakeCompleted(returncode=0, stdout=ok, stderr=""))

    tool = go2w_mod.Go2WBringupTool()
    res = tool.execute({"action": "teardown"}, _bringup_ctx())

    assert not res.is_error, "a clean teardown must not be flagged as an error"
    assert "SUCCESS" in res.content
