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
    monkeypatch.delenv("VECTOR_DASHBOARD", raising=False)
    monkeypatch.delenv("ZENO_DASHBOARD", raising=False)
    assert cli._dashboard_enabled() is False


def test_dashboard_gate_env_enables(monkeypatch) -> None:
    monkeypatch.setenv("VECTOR_DASHBOARD", "1")
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
    cli._run_dashboard(app_state, _Reg(), session)
    assert len(built) == 1  # run() invoked, layout built without error
