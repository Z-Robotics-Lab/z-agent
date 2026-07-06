# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Tests for zeno.skills.calibration — FIX 3.

Verifies that load_calibration() with no env var and no explicit file:
  - returns np.eye(4)  (identity — correct for sim)
  - does NOT emit a WARNING-level log (absence is normal in sim, not an error)

Also verifies that an explicit calib_file= path still loads correctly.
"""
from __future__ import annotations

import logging

import numpy as np
import yaml


# ---------------------------------------------------------------------------
# load_calibration: no-config path (the sim default)
# ---------------------------------------------------------------------------

class TestLoadCalibrationNoConfig:
    """When no file is configured, load_calibration returns identity silently."""

    def test_returns_identity_when_no_env_no_arg(self, monkeypatch):
        """With VECTOR_CALIB_FILE unset and no explicit arg, get np.eye(4)."""
        monkeypatch.delenv("VECTOR_CALIB_FILE", raising=False)
        from zeno.skills.calibration import load_calibration
        T = load_calibration()
        assert T.shape == (4, 4)
        assert np.allclose(T, np.eye(4))

    def test_no_warning_emitted_when_no_config(self, monkeypatch, caplog):
        """Absence of a calib file must NOT produce a WARNING (it's normal in sim)."""
        monkeypatch.delenv("VECTOR_CALIB_FILE", raising=False)
        from zeno.skills.calibration import load_calibration
        with caplog.at_level(logging.WARNING, logger="zeno.skills.calibration"):
            load_calibration()
        assert caplog.records == [], (
            "Expected no WARNING-level logs when no calib file is configured; "
            f"got: {[r.message for r in caplog.records]}"
        )

    def test_returns_identity_when_env_points_to_missing_file(self, monkeypatch, tmp_path):
        """If VECTOR_CALIB_FILE is set but the file doesn't exist, get identity."""
        missing = str(tmp_path / "does_not_exist.yaml")
        monkeypatch.setenv("VECTOR_CALIB_FILE", missing)
        from zeno.skills.calibration import load_calibration
        T = load_calibration()
        assert np.allclose(T, np.eye(4))


# ---------------------------------------------------------------------------
# load_calibration: explicit file path
# ---------------------------------------------------------------------------

class TestLoadCalibrationExplicitFile:
    """When an explicit calib_file is provided, it loads correctly."""

    def test_loads_transform_matrix_from_yaml(self, tmp_path):
        """Explicit calib_file= loads the transform_matrix from YAML."""
        T_expected = np.eye(4)
        T_expected[0, 3] = 0.15  # known translation
        data = {
            "transform_matrix": T_expected.tolist(),
            "mean_error_mm": 2.5,
        }
        calib_yaml = tmp_path / "workspace_calibration.yaml"
        calib_yaml.write_text(yaml.dump(data))

        from zeno.skills.calibration import load_calibration
        T = load_calibration(calib_file=str(calib_yaml))
        assert T.shape == (4, 4)
        assert np.allclose(T, T_expected, atol=1e-9)

    def test_env_var_path_used_when_no_arg(self, monkeypatch, tmp_path):
        """VECTOR_CALIB_FILE env var is used when calib_file arg is None."""
        T_expected = np.eye(4)
        T_expected[1, 3] = 0.05
        data = {"transform_matrix": T_expected.tolist()}
        calib_yaml = tmp_path / "calib.yaml"
        calib_yaml.write_text(yaml.dump(data))
        monkeypatch.setenv("VECTOR_CALIB_FILE", str(calib_yaml))

        from zeno.skills.calibration import load_calibration
        T = load_calibration()
        assert np.allclose(T, T_expected, atol=1e-9)

    def test_explicit_arg_overrides_env(self, monkeypatch, tmp_path):
        """calib_file= arg takes priority over VECTOR_CALIB_FILE env var."""
        # Env file has identity; explicit file has a translation
        identity_data = {"transform_matrix": np.eye(4).tolist()}
        env_yaml = tmp_path / "env.yaml"
        env_yaml.write_text(yaml.dump(identity_data))
        monkeypatch.setenv("VECTOR_CALIB_FILE", str(env_yaml))

        T_explicit = np.eye(4)
        T_explicit[2, 3] = 0.30
        explicit_data = {"transform_matrix": T_explicit.tolist()}
        explicit_yaml = tmp_path / "explicit.yaml"
        explicit_yaml.write_text(yaml.dump(explicit_data))

        from zeno.skills.calibration import load_calibration
        T = load_calibration(calib_file=str(explicit_yaml))
        assert np.allclose(T, T_explicit, atol=1e-9)
