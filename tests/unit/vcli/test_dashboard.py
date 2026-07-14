# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P4 stage 1 — dashboard TUI skeleton (owner chose the info-density panel).

A full_screen prompt_toolkit Application: a persistent top status panel, a
scrollable middle turn region, a persistent bottom input. Stage 1 pins the
pure renderers (status panel) and the three-region layout construction; the
turn region wiring is stage 2. Display-only — consumes the SAME live-status
hook and NativeEvent stream, never touches routing/verify.
"""
from __future__ import annotations

from prompt_toolkit.formatted_text import fragment_list_to_text

from zeno.vcli import cli
from zeno.vcli.dashboard import Dashboard, render_status_panel


def _plain(fragments) -> str:
    return fragment_list_to_text(fragments)


def _styles(fragments) -> list[str]:
    return [s for s, t in fragments if t.strip()]


# ---------------------------------------------------------------------------
# render_status_panel — pure projection of display-only status
# ---------------------------------------------------------------------------


def _status(**over):
    base = {
        "live_status": "pose x=1.96 y=-1.90 yaw=-6.5deg · course -11.6deg (drift -5.1deg) · odom age 0.1s",
        "model": "deepseek-v4-pro",
        "base": "go2w_hw",
        "tools": 44,
        "msgs": 22,
        "permissions": "auto",
        "estop": False,
    }
    base.update(over)
    return base


def test_status_panel_shows_identity_and_pose() -> None:
    frags = render_status_panel(_status())
    text = _plain(frags)
    assert "ZENO" in text
    assert "go2w_hw" in text and "deepseek-v4-pro" in text
    assert "pose" in text and "1.96" in text
    assert "44" in text  # tools count


def test_status_panel_stale_odom_warns() -> None:
    frags = render_status_panel(_status(
        live_status="pose x=0.00 y=0.00 yaw=0.0deg · odom age 7.4s"))
    joined_styles = " ".join(_styles(frags))
    assert "stale" in joined_styles


def test_status_panel_estop_latched_is_loud() -> None:
    frags = render_status_panel(_status(estop=True))
    text = _plain(frags)
    styles = " ".join(_styles(frags))
    assert "ESTOP" in text or "E-STOP" in text
    assert "danger" in styles or "bad" in styles


def test_status_panel_no_odometry_is_honest() -> None:
    frags = render_status_panel(_status(live_status="(no odometry — stack down?)"))
    assert "no odometry" in _plain(frags)


def test_status_panel_escapes_markup() -> None:
    # A live-status string can never inject prompt_toolkit HTML/style.
    frags = render_status_panel(_status(live_status="pose <b>x</b>=[bold]0[/]"))
    text = _plain(frags)
    assert "<b>" in text or "[bold]" in text  # rendered literally, not parsed


# ---------------------------------------------------------------------------
# Dashboard — three-region layout construction (no TTY)
# ---------------------------------------------------------------------------


def _mk_dashboard():
    return Dashboard(
        status_provider=lambda: _status(),
        identity_provider=lambda: _status(),
        on_submit=lambda text: None,
        completer=cli.ZenoCompleter(),
    )


def test_dashboard_builds_three_region_layout() -> None:
    from prompt_toolkit.layout.containers import Window

    dash = _mk_dashboard()
    layout = dash.build_layout()
    windows = [w for w in layout.walk() if isinstance(w, Window)]
    assert len(windows) >= 3  # status, turn region, input (+ maybe separators)


def test_dashboard_status_region_renders_live() -> None:
    dash = _mk_dashboard()
    dash.build_layout()
    text = _plain(dash._status_fragments())
    assert "go2w_hw" in text and "pose" in text


def test_dashboard_submit_appends_to_turn_region() -> None:
    seen: list[str] = []
    dash = Dashboard(
        status_provider=lambda: _status(),
        identity_provider=lambda: _status(),
        on_submit=seen.append,
        completer=cli.ZenoCompleter(),
    )
    dash.build_layout()
    dash.submit("往前走3米")
    assert seen == ["往前走3米"]


def test_dashboard_append_turn_line_shows_in_region() -> None:
    dash = _mk_dashboard()
    dash.build_layout()
    dash.append_turn_line("  [#5cc98f]✓[/] done")
    assert "done" in dash._turn_text()


# ---------------------------------------------------------------------------
# gate — default OFF (stage 1 is opt-in), env enables
# ---------------------------------------------------------------------------


def test_dashboard_gate_default_off(monkeypatch) -> None:
    monkeypatch.delenv("ZENO_DASHBOARD", raising=False)
    assert cli._dashboard_enabled() is False


def test_dashboard_gate_env_enables(monkeypatch) -> None:
    monkeypatch.setenv("ZENO_DASHBOARD", "1")
    assert cli._dashboard_enabled() is True


# ---------------------------------------------------------------------------
# _run_dashboard integration — constructs + builds without a TTY
# ---------------------------------------------------------------------------


def test_run_dashboard_constructs_and_builds(monkeypatch) -> None:
    from types import SimpleNamespace

    built: list[object] = []
    monkeypatch.setattr(Dashboard, "run", lambda self: built.append(self.build_layout()))

    class _Reg:
        def list_tools(self):
            return [1, 2, 3]

    app_state = {
        "model": "deepseek-v4-pro",
        "world": "go2w_real",
        "agent": SimpleNamespace(_base=SimpleNamespace(name="go2w_hw")),
        "permissions": SimpleNamespace(no_permission=True),
    }
    session = SimpleNamespace(_entries=[1, 2])
    cli._run_dashboard(app_state, _Reg(), session, engine_turn=lambda t: None)
    assert len(built) == 1  # run() invoked, layout built without error


# ---------------------------------------------------------------------------
# P4 stage 2 — turn region: rich console → ANSI buffer, turn headers
# ---------------------------------------------------------------------------


def test_make_console_prints_into_turn_region() -> None:
    dash = _mk_dashboard()
    dash.build_layout()
    con = dash.make_console(width=80)
    con.print("[#5cc98f]✓[/] navigate done")
    assert "navigate done" in dash._turn_text()  # ANSI-stripped plain


def test_turn_region_renders_ansi_fragments() -> None:
    from prompt_toolkit.formatted_text import to_formatted_text

    dash = _mk_dashboard()
    dash.build_layout()
    dash.make_console(width=80).print("[#5cc98f]hello[/]")
    frags = dash._turn_fragments()
    plain = fragment_list_to_text(to_formatted_text(frags))
    assert "hello" in plain
    # A color style survived the ANSI round-trip (not a bare plain string).
    assert any("5cc98f" in s or "ansi" in s.lower() or "#" in s for s, _t in frags)


def test_start_turn_emits_numbered_timestamped_header() -> None:
    dash = _mk_dashboard()
    dash.build_layout()
    dash.start_turn("往前走3米", now=lambda: 1000.0)
    dash.start_turn("左转90度", now=lambda: 1000.0)
    text = dash._turn_text()
    assert "#1" in text and "往前走3米" in text
    assert "#2" in text and "左转90度" in text


def test_markup_append_still_works_stage1() -> None:
    # Stage-1 direct markup append keeps rendering (now via ANSI).
    dash = _mk_dashboard()
    dash.build_layout()
    dash.append_turn_line("  [#e8897d]✗[/] failed step")
    assert "failed step" in dash._turn_text()


def test_dashboard_executes_turn_via_engine_turn(monkeypatch) -> None:
    # Stage 2: submit -> worker -> the UNCHANGED engine turn body, whose
    # console (rebound to the turn region) streams output into the panel.
    from types import SimpleNamespace

    ran: dict = {}

    def engine_turn(text: str) -> None:
        ran["text"] = text
        cli.console.print("[#5cc98f]✓[/] step done")

    holder: dict = {}

    def fake_run(self) -> None:
        holder["dash"] = self
        self.submit("往前走3米")
        holder["app_state"]["turn_runner"].wait_idle(3.0)

    monkeypatch.setattr(Dashboard, "run", fake_run)

    class _Reg:
        def list_tools(self):
            return [1]

    app_state = {
        "model": "m", "world": "go2w_real",
        "agent": SimpleNamespace(_base=SimpleNamespace(name="go2w_hw")),
        "permissions": SimpleNamespace(no_permission=False),
    }
    holder["app_state"] = app_state
    cli._run_dashboard(app_state, _Reg(), SimpleNamespace(_entries=[]), engine_turn=engine_turn)

    assert ran.get("text") == "往前走3米"          # engine turn ran on the worker
    text = holder["dash"]._turn_text()
    assert "#1" in text and "往前走3米" in text     # numbered header emitted
    assert "step done" in text                      # console output hit the region
    assert app_state.get("turn_runner") is not None  # runner wired for interject


def test_native_turn_renders_into_dashboard_region(monkeypatch) -> None:
    # The REAL native path (_repl_attempt_native) rendered through the dashboard
    # console lands the ⌂ tree + verdict + footer into the turn region.
    from zeno.vcli.turn_runner import ComposerInterjectQueue, TurnRunner

    from tests.vcli.test_chain_view_repl import _EventFakeEngine
    from tests.vcli.test_repl_native_cutover import (
        _FakeSession, _acted_trace, _stub_oracle,
    )

    _stub_oracle(monkeypatch)
    trace = _acted_trace("g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True)
    dash = _mk_dashboard()
    dash.build_layout()
    con = dash.make_console(width=100)
    # sink mode requires a TurnRunner in app_state.
    app_state = {"turn_runner": TurnRunner(run_turn=lambda t: None, interject_queue=ComposerInterjectQueue())}

    acted = cli._repl_attempt_native(_EventFakeEngine(trace), "走到坐标 (11,3)", _FakeSession(), app_state, con)
    assert acted is True
    text = dash._turn_text()
    assert "⌂" in text                      # execution tree header
    assert "verified=True" in text          # verdict line
    assert "grounded)" in text              # pinned acceptance tail
