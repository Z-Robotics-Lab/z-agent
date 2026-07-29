# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Startup speed guard: the MuJoCo/numpy stack stays OUT of the import path.

`import zeno` (and therefore every `zeno` CLI cold start) used to eagerly import
``zeno.hardware.sim.mujoco_arm`` / ``mujoco_gripper``, which drag in the whole numpy
stack — ~57ms measured, ~66ms off the total in-process `import zeno.vcli.cli` cost
(175ms → 109ms) — even though the go2w_real CLI never touches the sim arm at startup.
The optional hardware symbols are now resolved lazily via PEP 562 ``__getattr__``.

These guards run in a CLEAN subprocess interpreter (module-state sensitive) to pin:
  1. after `import zeno`, numpy + the mujoco sim modules are NOT yet imported;
  2. the public API is unchanged — `zeno.MuJoCoArm` still resolves on access (and
     accessing it is what finally pulls the sim module in), and an unknown attribute
     still raises AttributeError.
Hermetic: no sim spawned, no network, no MuJoCo instantiated.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap


def _run(snippet: str) -> str:
    """Execute a snippet in a fresh interpreter; return stdout (raises on failure)."""
    proc = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(snippet)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"subprocess failed:\n{proc.stderr}"
    return proc.stdout.strip()


def test_import_zeno_does_not_pull_numpy_or_mujoco() -> None:
    """A bare `import zeno` must not drag in numpy or the MuJoCo sim modules."""
    out = _run(
        """
        import sys
        import zeno
        heavy = [m for m in ("numpy", "mujoco",
                             "zeno.hardware.sim.mujoco_arm",
                             "zeno.hardware.sim.mujoco_gripper")
                 if m in sys.modules]
        print(",".join(heavy) if heavy else "CLEAN")
        """
    )
    assert out == "CLEAN", f"startup path eagerly imported: {out}"


def test_lazy_symbol_resolves_and_triggers_load() -> None:
    """Public API parity: `zeno.MuJoCoArm` resolves on access (lazily loading the module)."""
    out = _run(
        """
        import sys
        import zeno
        assert "zeno.hardware.sim.mujoco_arm" not in sys.modules, "loaded too early"
        cls = zeno.MuJoCoArm
        # Accessing the attribute is what pulls the module in (or leaves None if the
        # optional dep is genuinely absent — legacy contract preserved).
        loaded = "zeno.hardware.sim.mujoco_arm" in sys.modules
        print(f"{cls is not None}:{loaded}")
        """
    )
    resolved, loaded = out.split(":")
    # If the class resolved, the backing module must now be imported.
    if resolved == "True":
        assert loaded == "True", "resolved class but module not imported"
    else:
        # Optional dep absent in this env — still must not crash, just None.
        assert resolved == "False"


def test_unknown_attribute_still_raises() -> None:
    """`__getattr__` must not swallow genuinely-missing names."""
    out = _run(
        """
        import zeno
        try:
            zeno.NotAThing
            print("NO_RAISE")
        except AttributeError:
            print("RAISED")
        """
    )
    assert out == "RAISED"
