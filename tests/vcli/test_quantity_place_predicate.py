# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R198 (E35): the honest QUANTITY-place predicate is ``resting_on_receptacle() >= N``,
NOT ``placed_count() >= N``.

FINDING (refutes R197/E34's scope premise "placed_count>=2 is the predicate"): on the
go2 tabletop face the pickables START on ``pick_table`` at z=0.320 and a placed bottle
settles in ``place_bin`` at z~0.31 — BOTH above ``placed_count``'s floor cutoff
_LIFT_MIN_Z=0.10. So ``placed_count`` (a FLOOR oracle) is STRUCTURALLY STUCK AT 0 for a
go2 place-on-a-height-receptacle task: it credits neither the start state nor a correct
placement. ``placed_count() >= 2`` is therefore ALWAYS FALSE on this face — using it as
the quantity predicate would grade every real placement as UNMET (a false RED), the mirror
of a false GREEN and just as dishonest.

The correct honest quantity predicate already EXISTS and needs NO spine change: the D106
moat oracle ``resting_on_receptacle()`` RETURNS A COUNT of distinct objects supported at
the receptacle height, at rest, not held. ``resting_on_receptacle() >= N`` is thus the
ungated quantity-place predicate (same honesty level as the already-accepted single
place.nl-plain-colour row; the D168 actor-causation residual is identical, not new).

Pure oracle test (fake arm, NO MuJoCo): pins WHY placed_count is the wrong predicate so a
future round cannot silently re-adopt ``placed_count>=2`` and record a structurally-false
verdict. Verified against the live go2_room.xml heights (pickable z=0.320, place_bin top
~0.31).
"""
from zeno.vcli.worlds.arm_sim_oracle import (
    make_placed_count,
    make_resting_on_receptacle,
)

# go2_room.xml ground truth (verified R198): pickables spawn on pick_table at z=0.320;
# place_bin sits at (10.95, 4.60) with its top ~0.31 m. Region = the bin xy footprint.
_TABLE_Z = 0.320
_BIN_Z = 0.31
_BIN_REGION = (10.70, 4.40, 11.20, 4.80)


class _FakeArm:
    def __init__(self, objects):
        self._objects = objects
        self._connected = True

    def get_object_positions(self):
        return self._objects

    def get_object_velocities(self):
        # AT REST (finite, ~0 speed) so resting_on_receptacle's at-rest gate passes.
        return {k: [0.0, 0.0, 0.0] for k in self._objects}

    def get_joint_positions(self):
        return [0.0]

    def fk(self, _joints):
        # EE parked far away so holding_object (released-check) reads not-held.
        return ([99.0, 99.0, 99.0], None)


class _FakeGripper:
    def is_holding(self):
        return False


class _FakeAgent:
    def __init__(self, arm):
        self._arm = arm
        self._gripper = _FakeGripper()


def _scene_start():
    # Two bottles + a can, all resting on the pick_table at z=0.320 (the real start state).
    return _FakeAgent(_FakeArm({
        "blue": [10.90, 2.78, _TABLE_Z],
        "green": [10.88, 3.00, _TABLE_Z],
        "red": [10.90, 3.22, _TABLE_Z],
    }))


def _two_in_bin():
    # Two bottles correctly placed IN the bin (over its footprint, at bin-top height).
    return _FakeAgent(_FakeArm({
        "blue": [10.90, 4.60, _BIN_Z],
        "green": [10.88, 4.60, _BIN_Z],
    }))


# --- placed_count is the WRONG predicate (structurally 0 on the go2 tabletop) -----------

def test_placed_count_zero_at_scene_start():
    # Nothing placed on the floor: the floor oracle reads 0 (objects are on the table).
    assert make_placed_count(_scene_start())() == 0


def test_placed_count_STILL_zero_after_a_correct_bin_placement():
    # THE FINDING: even with two bottles correctly resting IN the bin, placed_count stays
    # 0 because the bin top (~0.31 m) is ABOVE _LIFT_MIN_Z=0.10 — the floor oracle treats
    # the placed bottles as "still lifted". So `placed_count() >= 2` can NEVER be True for a
    # go2 place-on-the-bin task. (Refutes R197/E34: placed_count is NOT the quantity predicate.)
    assert make_placed_count(_two_in_bin())() == 0


# --- resting_on_receptacle IS the honest quantity predicate (ungated, counts at height) -

def test_resting_on_receptacle_counts_two_in_bin():
    ror = make_resting_on_receptacle(_two_in_bin(), _BIN_REGION, _BIN_Z)
    assert ror() == 2  # distinct objects supported at the bin height, at rest, not held


def test_resting_on_receptacle_zero_at_scene_start():
    # On the pick_table (not over the bin) -> 0. So `resting_on_receptacle() >= 2` is FALSE
    # at start and only becomes True once TWO objects are actually placed in the bin: a real
    # quantity predicate the actor cannot satisfy without doing the two placements.
    ror = make_resting_on_receptacle(_scene_start(), _BIN_REGION, _BIN_Z)
    assert ror() == 0
