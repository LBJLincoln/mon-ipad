"""Unit tests for Generalized Venn-Abers calibration (proposal #4, 2026-04-21)."""
from __future__ import annotations

import os
import sys
from importlib import reload

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fresh_fe():
    """Reload features.engine so env-flag changes take effect."""
    import features.engine as fe
    reload(fe)
    return fe


def test_flag_default_on_returns_enabled_calibrator():
    os.environ.pop("VENN_ABERS_CALIBRATION", None)
    fe = _fresh_fe()
    cal = fe.VennAbersProbabilityCalibrator()
    assert cal.enabled is True


def test_flag_off_is_passthrough():
    os.environ["VENN_ABERS_CALIBRATION"] = "0"
    fe = _fresh_fe()
    cal = fe.VennAbersProbabilityCalibrator()
    assert cal.enabled is False

    p = np.array([[0.3, 0.7], [0.8, 0.2], [0.5, 0.5]])
    y = np.array([1, 0, 1])
    out = cal.fit(p, y).transform(p)
    assert out.shape == (3,)
    np.testing.assert_allclose(out, p[:, 1])


def test_flag_off_variants():
    for v in ("0", "false", "FALSE", "no", "off"):
        os.environ["VENN_ABERS_CALIBRATION"] = v
        fe = _fresh_fe()
        cal = fe.VennAbersProbabilityCalibrator()
        assert cal.enabled is False, f"expected disabled for {v!r}"


def test_brier_improves_on_miscalibrated():
    # Skip if optional dep missing in CI.
    pytest.importorskip("venn_abers")
    os.environ.pop("VENN_ABERS_CALIBRATION", None)
    fe = _fresh_fe()
    rng = np.random.default_rng(42)
    n = 800
    y = rng.binomial(1, 0.5, n)
    raw = 0.5 + 0.35 * (2 * y - 1) + rng.normal(0, 0.18, n)
    raw = np.clip(raw, 0.05, 0.95)
    p = np.clip(
        np.where(raw > 0.5, 0.5 + (raw - 0.5) * 1.5, 0.5 - (0.5 - raw) * 1.5),
        0.02, 0.98,
    )

    split = 500
    p_cal_mat = np.column_stack([1 - p[:split], p[:split]])
    p_test_mat = np.column_stack([1 - p[split:], p[split:]])
    y_cal, y_test = y[:split], y[split:]

    brier_raw = float(np.mean((p[split:] - y_test) ** 2))
    cal = fe.VennAbersProbabilityCalibrator()
    cal.fit(p_cal_mat, y_cal)
    p_ve = cal.transform(p_test_mat)
    brier_ve = float(np.mean((p_ve - y_test) ** 2))
    # Expect strictly better than raw on this miscalibrated synthetic set.
    assert brier_ve < brier_raw, f"VE Brier {brier_ve} should beat raw {brier_raw}"
    # And at least 5% relative improvement (our synthetic shows ~27%).
    assert (brier_raw - brier_ve) / brier_raw > 0.05


def test_one_shot_calibrate_probs():
    pytest.importorskip("venn_abers")
    os.environ.pop("VENN_ABERS_CALIBRATION", None)
    fe = _fresh_fe()
    rng = np.random.default_rng(1)
    p_cal = np.clip(rng.normal(0.6, 0.2, (200, 2)), 0.01, 0.99)
    p_cal[:, 0] = 1 - p_cal[:, 1]
    y_cal = rng.binomial(1, 0.6, 200)
    p_test = np.clip(rng.normal(0.6, 0.2, (50, 2)), 0.01, 0.99)
    p_test[:, 0] = 1 - p_test[:, 1]
    out = fe.calibrate_probs(p_cal, y_cal, p_test)
    assert out.shape == (50,)
    assert (out >= 0).all() and (out <= 1).all()


def test_1d_input_handled():
    pytest.importorskip("venn_abers")
    os.environ.pop("VENN_ABERS_CALIBRATION", None)
    fe = _fresh_fe()
    rng = np.random.default_rng(3)
    p = np.clip(rng.normal(0.5, 0.2, 300), 0.02, 0.98)
    y = rng.binomial(1, p, 300)
    cal = fe.VennAbersProbabilityCalibrator()
    cal.fit(p[:200], y[:200])
    out = cal.transform(p[200:])
    assert out.shape == (100,)


def test_unfit_transform_is_passthrough_for_2col():
    # When fit was never called, transform should still return shape (n,)
    pytest.importorskip("venn_abers")
    os.environ.pop("VENN_ABERS_CALIBRATION", None)
    fe = _fresh_fe()
    cal = fe.VennAbersProbabilityCalibrator()
    p = np.array([[0.3, 0.7], [0.2, 0.8]])
    # Not fitted -> identity; _fitted is False -> passthrough of column 1
    out = cal.transform(p)
    np.testing.assert_allclose(out, [0.7, 0.8])
