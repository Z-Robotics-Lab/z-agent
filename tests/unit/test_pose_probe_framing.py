# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit: pose_probe framing + classifier (R316).

R315/E106 established minicpm-v discriminates go2 pose ONLY under NEUTRAL framing, but that
neutral prompt lived in an ephemeral inline script — pose_probe.py shipped ONLY the fault-primed
prompt (which collapses minicpm to FALLEN-both, reproduced R316). This locks in a tracked neutral
framing + proves the classifier parses BOTH vocabularies (UPRIGHT/FALLEN and STANDING/LYING), so
E106 is reproducible from a tool, not a lost inline snippet. Pure-unit, no network, no sim.
"""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "pose_probe", Path(__file__).resolve().parents[2] / "tools" / "acceptance" / "pose_probe.py"
)
pose_probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pose_probe)


class TestClassify:
    def test_fault_vocab_upright(self):
        assert pose_probe._classify("UPRIGHT") == "UPRIGHT"

    def test_fault_vocab_fallen(self):
        assert pose_probe._classify("FALLEN") == "FALLEN"

    def test_neutral_vocab_standing_maps_upright(self):
        assert pose_probe._classify("STANDING") == "UPRIGHT"

    def test_neutral_vocab_lying_maps_fallen(self):
        assert pose_probe._classify("LYING") == "FALLEN"

    def test_lying_in_a_sentence(self):
        assert pose_probe._classify("The robot is lying on its side on the floor.") == "FALLEN"

    def test_standing_in_a_sentence(self):
        assert pose_probe._classify("It is standing on all four feet.") == "UPRIGHT"

    def test_unparseable(self):
        assert pose_probe._classify("purple monkey dishwasher") == "UNPARSEABLE"


class TestFraming:
    def test_default_is_fault_primed(self):
        # E105 reproducibility: the default prompt keeps the safety-inspector fault framing.
        p = pose_probe._prompt_for("fault")
        assert "fall" in p.lower() and "UPRIGHT or FALLEN" in p

    def test_neutral_is_not_fault_primed(self):
        # No fall / safety-inspector priming; symmetric STANDING/LYING options.
        p = pose_probe._prompt_for("neutral")
        low = p.lower()
        assert "fall" not in low and "safety inspector" not in low
        assert "STANDING or LYING" in p

    def test_unknown_framing_raises(self):
        try:
            pose_probe._prompt_for("sideways")
        except ValueError:
            return
        raise AssertionError("unknown framing must raise ValueError, not silently default")
