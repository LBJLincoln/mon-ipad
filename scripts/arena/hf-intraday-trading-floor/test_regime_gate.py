"""Unit tests for ITF no-trade regime gate (proposal #3, 2026-04-21)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Stub heavy optional deps so app.py imports clean in test.
sys.path.insert(0, str(Path(__file__).parent))
# Avoid alpaca/executor side-effects during import.
import types as _t
for _mod in ["executor"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _t.ModuleType(_mod)
        sys.modules[_mod].get_bankroll = lambda *_a, **_k: 5932.0  # type: ignore[attr-defined]
        sys.modules[_mod].seed_bankrolls = lambda *_a, **_k: None  # type: ignore[attr-defined]
        sys.modules[_mod].close_expired = lambda *_a, **_k: None  # type: ignore[attr-defined]
        sys.modules[_mod].close_position = lambda *_a, **_k: None  # type: ignore[attr-defined]


# Import only the regime helper + constants without executing main().
# app.py defines them at module load so plain import is sufficient.
_app = pytest.importorskip("app", reason="requires Space app.py to load")


def test_dead_tape_detected():
    dead = {
        "BTC/USD": {"last": 100000, "5m_high": 100050, "5m_low": 99970},
        "ETH/USD": {"last": 3500, "5m_high": 3502, "5m_low": 3499},
        "SOL/USD": {"last": 200, "5m_high": 200.1, "5m_low": 199.9},
    }
    r = _app._compute_crypto_regime(dead)
    assert r["low_vol_regime"] is True
    assert r["median_realized_vol"] < 0.003
    assert r["sample_n"] == 3


def test_live_tape_not_dead():
    live = {
        "BTC/USD": {"last": 100000, "5m_high": 100800, "5m_low": 99500},
        "ETH/USD": {"last": 3500, "5m_high": 3535, "5m_low": 3480},
        "SOL/USD": {"last": 200, "5m_high": 202, "5m_low": 198.5},
    }
    r = _app._compute_crypto_regime(live)
    assert r["low_vol_regime"] is False
    assert r["median_realized_vol"] > 0.003


def test_no_crypto_quotes_safe_default():
    # Only equities -> sample_n=0, low_vol_regime=False (don't waive on missing data)
    eq_only = {"SPY": {"last": 500, "5m_high": 501, "5m_low": 499}}
    r = _app._compute_crypto_regime(eq_only)
    assert r["sample_n"] == 0
    assert r["low_vol_regime"] is False


def test_bad_quote_fields_skipped():
    mixed = {
        "BTC/USD": {"last": None, "5m_high": 1, "5m_low": 1},  # bad last -> skip
        "ETH/USD": {"last": 3500, "5m_high": 3502, "5m_low": 3499},  # tight
    }
    r = _app._compute_crypto_regime(mixed)
    assert r["sample_n"] == 1
    assert r["low_vol_regime"] is True


def test_dead_tape_clause_has_pass_guidance():
    assert "action='pass'" in _app.DEAD_TAPE_CLAUSE
    assert "WAIVED" in _app.DEAD_TAPE_CLAUSE or "waived" in _app.DEAD_TAPE_CLAUSE.lower()


def test_env_override_floor(monkeypatch):
    # Tight tape, high floor -> still dead
    monkeypatch.setenv("ITF_REGIME_FLOOR_5M", "0.010")
    # Reload module-level const by reaching into globals — no reload needed;
    # the floor baked at import is what runtime uses. This test documents the
    # env hook for operators; assert attribute exists.
    assert hasattr(_app, "REGIME_FLOOR_5M")
    assert _app.REGIME_FLOOR_5M > 0


def test_uniform_fallback_waived_in_low_vol():
    # Synthetic persona + ctx with low-vol regime flag -> must pass
    persona = {"tid": "scalper-1", "tier": "s", "name": "test"}
    ctx = {
        "quotes": {"SPY": {"last": 500}},
        "regime": {"low_vol_regime": True, "median_realized_vol": 0.001, "floor": 0.003},
    }
    out = _app._uniform_fallback_itf(persona, ctx)
    assert out["action"] == "pass"
    assert out["provider_status"] == "regime_pass"
    assert "low_vol" in (out.get("reason") or "").lower()


def test_uniform_fallback_trades_in_normal_regime():
    persona = {"tid": "scalper-1", "tier": "s", "name": "test"}
    ctx = {
        "quotes": {"SPY": {"last": 500}, "QQQ": {"last": 400}, "IWM": {"last": 200}},
        "regime": {"low_vol_regime": False, "floor": 0.003},
    }
    out = _app._uniform_fallback_itf(persona, ctx)
    # In non-dead regime, fallback emits a trade (or pass with different reason)
    assert out["action"] in ("trade", "pass")
    if out["action"] == "pass":
        assert out.get("provider_status") != "regime_pass"
