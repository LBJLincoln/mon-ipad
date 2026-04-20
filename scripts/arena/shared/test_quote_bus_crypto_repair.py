"""Point #6 local test — verify _repair_crypto_change_pct backfills chg=0.0 from bars.

Alpaca's /latest/quotes gives point-in-time bid/ask but no 24h Δ; leaving
change_pct=0.0 silenced 6/7 ITF personas (every persona passes 'tape flat').
This test stubs the bar-fetch call and asserts chg% is populated.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (REPO, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from scripts.arena.shared import quote_bus  # noqa: E402


def test_repair_populates_change_pct_from_bars():
    out = {
        "BTC/USD": {"last": 62_500.0, "change_pct": 0.0, "volume": 0},
        "ETH/USD": {"last": 3_140.0,  "change_pct": 0.0, "volume": 0},
        "SOL/USD": {"last": 150.0,    "change_pct": 0.0, "volume": 0},
    }
    fake_bars = {
        "BTC/USD": [{"o": 61_000.0}],  # 62500 / 61000 - 1 = +2.459%
        "ETH/USD": [{"o": 3_080.0}],   # +1.948%
        "SOL/USD": [{"o": 155.0}],     # -3.226%
    }

    class _FakeResp:
        status_code = 200
        def json(self): return {"bars": fake_bars}

    with mock.patch("requests.get", return_value=_FakeResp()):
        quote_bus._repair_crypto_change_pct(out, list(out.keys()), "k", "s")

    assert abs(out["BTC/USD"]["change_pct"] - 2.459) < 0.01, out["BTC/USD"]
    assert abs(out["ETH/USD"]["change_pct"] - 1.948) < 0.01, out["ETH/USD"]
    assert abs(out["SOL/USD"]["change_pct"] - (-3.226)) < 0.01, out["SOL/USD"]
    print("[OK] _repair_crypto_change_pct backfills chg% from 1Day bars")


def test_repair_skips_when_chg_already_nonzero():
    """Repair must NOT clobber live, non-zero change_pct values."""
    out = {"BTC/USD": {"last": 62_500.0, "change_pct": 1.23, "volume": 0}}

    calls = []
    def _fail(*a, **kw):
        calls.append((a, kw))
        raise AssertionError("should not call bars endpoint when chg already set")

    with mock.patch("requests.get", side_effect=_fail):
        quote_bus._repair_crypto_change_pct(out, ["BTC/USD"], "k", "s")
    assert out["BTC/USD"]["change_pct"] == 1.23, out
    assert calls == []
    print("[OK] _repair_crypto_change_pct no-ops when chg% already live")


def test_repair_silent_on_rate_limit():
    class _FakeResp:
        status_code = 429
        def json(self): return {}
    out = {"BTC/USD": {"last": 62_500.0, "change_pct": 0.0, "volume": 0}}
    with mock.patch("requests.get", return_value=_FakeResp()):
        quote_bus._repair_crypto_change_pct(out, ["BTC/USD"], "k", "s")
    assert out["BTC/USD"]["change_pct"] == 0.0, "rate-limited path must be silent no-op"
    print("[OK] _repair_crypto_change_pct silent on 429")


if __name__ == "__main__":
    fails = 0
    for t in (
        test_repair_populates_change_pct_from_bars,
        test_repair_skips_when_chg_already_nonzero,
        test_repair_silent_on_rate_limit,
    ):
        try:
            t()
        except Exception as e:
            fails += 1
            print(f"[FAIL] {t.__name__}: {e}")
    print(f"\n{'all PASSED' if fails == 0 else f'{fails} failed'}")
    sys.exit(fails)
