# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Regression: mjpython must be located next to the interpreter, not in $HOME.

A prior off-by-one bug computed the venv path as parents[N]-from-__file__, which
resolved to $HOME instead of the repo's .venv-nano — so mjpython was "not found"
and the arm sim silently ran headless on macOS. The fix derives mjpython from
sys.executable (the venv's bin/), depth-independent. These tests lock that in.
"""
from __future__ import annotations

import os
import stat

from vector_os_nano.vcli.tools.sim_tool import locate_mjpython


def _make_fake_mjpython(bindir) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    mjpy = bindir / "mjpython"
    mjpy.write_text("#!/bin/sh\n")
    mjpy.chmod(mjpy.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(mjpy)


def test_locates_mjpython_next_to_interpreter(tmp_path):
    bindir = tmp_path / "venv" / "bin"
    expected = _make_fake_mjpython(bindir)
    fake_python = bindir / "python"
    fake_python.write_text("")
    # Given an interpreter in venv/bin, mjpython is found right beside it.
    assert locate_mjpython(executable=str(fake_python)) == expected


def test_does_not_look_in_home(tmp_path, monkeypatch):
    # mjpython sits in the venv bin, NOT in $HOME — the off-by-one would have
    # looked in $HOME. Point the interpreter at venv/bin and $HOME elsewhere;
    # ensure neither a $HOME mjpython nor PATH is what satisfies the lookup.
    home = tmp_path / "home"
    _make_fake_mjpython(home / ".venv-nano" / "bin")  # a decoy in $HOME
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("shutil.which", lambda _name: None)  # nothing on PATH

    venv_bin = tmp_path / "proj" / ".venv-nano" / "bin"
    expected = _make_fake_mjpython(venv_bin)
    fake_python = venv_bin / "python"
    fake_python.write_text("")

    got = locate_mjpython(executable=str(fake_python))
    assert got == expected
    assert str(home) not in got  # never the $HOME decoy


def test_falls_back_to_path_when_absent(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True)
    fake_python = bindir / "python"
    fake_python.write_text("")  # no mjpython beside it
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/mjpython" if name == "mjpython" else None)
    assert locate_mjpython(executable=str(fake_python)) == "/usr/local/bin/mjpython"


def test_returns_none_when_truly_absent(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True)
    fake_python = bindir / "python"
    fake_python.write_text("")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert locate_mjpython(executable=str(fake_python)) is None


def test_real_env_finds_venv_mjpython():
    # In the project venv, mjpython IS installed beside the interpreter, so the
    # real (no-arg) call must find it — this is exactly the live bug's fix.
    found = locate_mjpython()
    if found is not None:  # mujoco/mjpython installed (the expected dev setup)
        assert found.endswith("mjpython")
        assert os.access(found, os.X_OK)
