"""Point #4 — prompt-byte menu visibility guard.

Protects against regressions like the ITF 84% crypto-pass (RCA: `_build_prompt`
sliced quotes[:22], 48 equities filled the slot, crypto invisible despite the
persona style literally saying "bet crypto 24/7").

These tests hit the real `_build_prompt` with synthetic quotes that span four
asset classes and assert each class leaves a visible trace in the rendered
prompt bytes for every persona. If anyone ever reintroduces a truncation bug
the CI goes red before deploy.
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
for p in (REPO, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _stub_missing_deps() -> None:
    """Stub the heavy Space-only modules so app.py imports in CI."""
    def _empty_module(name: str) -> types.ModuleType:
        m = types.ModuleType(name)
        sys.modules[name] = m
        return m

    if "executor" not in sys.modules:
        m = _empty_module("executor")
        m.submit = lambda *_a, **_k: None          # type: ignore[attr-defined]
        m.submit_option = lambda *_a, **_k: None   # type: ignore[attr-defined]

    if "gateway_client" not in sys.modules:
        m = _empty_module("gateway_client")
        m.gateway_call = lambda *_a, **_k: None    # type: ignore[attr-defined]

    for full in (
        "scripts.arena.shared",
        "scripts.arena.shared.quote_bus",
        "scripts.arena.shared.context_bus",
    ):
        if full not in sys.modules:
            _empty_module(full)
    sys.modules["scripts.arena.shared.quote_bus"].refresh = lambda *_a, **_k: None  # type: ignore[attr-defined]
    sys.modules["scripts.arena.shared.quote_bus"].latest = lambda *_a, **_k: {}     # type: ignore[attr-defined]
    sys.modules["scripts.arena.shared.context_bus"].build_intraday_context = lambda *_a, **_k: {}  # type: ignore[attr-defined]


_stub_missing_deps()

import app as itf_app  # noqa: E402
from personas import PERSONAS  # noqa: E402


def _synthetic_quotes() -> dict:
    """71-instrument universe shape, one ticker per class + the priority equities."""
    return {
        # Index probe
        "^VIX":  {"last": 16.2,  "change_pct": 1.4,  "volume": 0},
        # Priority equities (ETFs, sectors, leveraged, vol, single-name)
        "SPY":   {"last": 512.4, "change_pct": 0.3,  "volume": 82_000_000},
        "QQQ":   {"last": 443.8, "change_pct": 0.4,  "volume": 41_000_000},
        "IWM":   {"last": 204.1, "change_pct": -0.2, "volume": 23_000_000},
        "DIA":   {"last": 389.2, "change_pct": 0.1,  "volume": 3_400_000},
        "XLK":   {"last": 218.5, "change_pct": 0.6,  "volume": 5_800_000},
        "XLE":   {"last": 91.7,  "change_pct": -0.8, "volume": 19_500_000},
        "XLF":   {"last": 44.2,  "change_pct": 0.2,  "volume": 31_000_000},
        "TQQQ":  {"last": 68.4,  "change_pct": 1.1,  "volume": 72_000_000},
        "SQQQ":  {"last": 8.9,   "change_pct": -1.1, "volume": 65_000_000},
        "UVXY":  {"last": 23.1,  "change_pct": 2.4,  "volume": 18_000_000},
        "VXX":   {"last": 51.2,  "change_pct": 1.9,  "volume": 9_000_000},
        "NVDA":  {"last": 924.5, "change_pct": 2.1,  "volume": 55_000_000},
        "TSLA":  {"last": 181.3, "change_pct": -0.9, "volume": 92_000_000},
        "AAPL":  {"last": 182.8, "change_pct": 0.4,  "volume": 58_000_000},
        "META":  {"last": 511.2, "change_pct": 0.7,  "volume": 15_000_000},
        # Extra equities so `remaining_eq` has candidates
        "XLV":   {"last": 149.0, "change_pct": 0.1,  "volume": 8_000_000},
        "XLP":   {"last": 74.2,  "change_pct": 0.0,  "volume": 7_000_000},
        "XLU":   {"last": 68.7,  "change_pct": -0.3, "volume": 12_000_000},
        "AMD":   {"last": 162.1, "change_pct": 1.5,  "volume": 44_000_000},
        "COIN":  {"last": 221.0, "change_pct": 3.2,  "volume": 12_000_000},
        # Crypto — MUST survive truncation. Set |chg| > 0.2 so CRYPTO_PIVOT fires.
        "BTC/USD": {"last": 62_340.0, "change_pct": 0.7, "volume": 18_000_000_000},
        "ETH/USD": {"last": 3_140.5,  "change_pct": 1.1, "volume": 8_400_000_000},
        "SOL/USD": {"last": 149.2,    "change_pct": 2.3, "volume": 1_900_000_000},
        "AVAX/USD": {"last": 41.8,    "change_pct": -0.8, "volume": 320_000_000},
        "LINK/USD": {"last": 18.9,    "change_pct": 0.3, "volume": 280_000_000},
        "DOGE/USD": {"last": 0.163,   "change_pct": 1.7, "volume": 950_000_000},
    }


def _ctx() -> dict:
    return {
        "quotes": _synthetic_quotes(),
        "quotes_ts": datetime.now(timezone.utc).isoformat(),
        "quotes_source": "synthetic-test",
        "nba_top_edges": [
            {"away": "BOS", "home": "MIL", "pick": "BOS -2.5", "edge_pct": 3.1},
        ],
        "pol_top_signals": [
            {"event": "FOMC", "sector_etf": "XLF", "strength": 0.62},
        ],
        "pqtf_state": {"last_day": 50, "fleet_bankroll": 602_354.0, "open_positions": []},
    }


def _assert_class_visible(prompt: str, tokens: list[str], cls: str, persona_tid: str) -> None:
    for tok in tokens:
        if tok in prompt:
            return
    raise AssertionError(
        f"[{persona_tid}] asset class '{cls}' not visible in prompt. "
        f"Required any of {tokens}; prompt len={len(prompt)}"
    )


def test_each_persona_sees_all_asset_classes() -> None:
    ctx = _ctx()
    crypto_tokens   = ["BTC/USD", "ETH/USD", "SOL/USD"]
    index_tokens    = ["^VIX"]
    equity_tokens   = ["SPY", "QQQ", "IWM"]
    leveraged_tokens = ["TQQQ", "SQQQ", "UVXY", "VXX"]
    heading_tokens  = ["--- Crypto", "--- Equities", "--- VIX"]

    for persona in PERSONAS:
        prompt = itf_app._build_prompt(persona, ctx)
        _assert_class_visible(prompt, crypto_tokens,   "crypto",   persona["tid"])
        _assert_class_visible(prompt, index_tokens,    "index",    persona["tid"])
        _assert_class_visible(prompt, equity_tokens,   "equity",   persona["tid"])
        _assert_class_visible(prompt, leveraged_tokens,"leveraged",persona["tid"])
        _assert_class_visible(prompt, heading_tokens,  "headings", persona["tid"])
    print(f"[OK] {len(PERSONAS)} personas × 4 classes × 1 heading group = "
          f"{len(PERSONAS) * 5} substring assertions PASS")


def test_off_hours_crypto_pivot_style() -> None:
    """When equity hours closed + crypto moving → style must SWAP to off-hours mandate.

    We don't monkeypatch the clock — the helper `_off_hours_crypto_signal` only
    returns True when any of BTC/ETH/SOL has |chg|>0.2. So when equity_hours is
    True (most of the weekday) the override never fires. What we CAN verify is:
    the override mapping covers every persona except `options-1` (which legit
    has no 24/7 market) and each override string carries the 'OFF-HOURS' marker.
    """
    overrides = itf_app._OFF_HOURS_STYLE_BY_TID
    covered = set(overrides)
    all_tids = {p["tid"] for p in PERSONAS}
    # Every persona except options-1 MUST have a crypto-pivot fallback style.
    missing = (all_tids - covered) - {"options-1"}
    assert not missing, f"personas missing off-hours crypto style: {missing}"
    for tid, style in overrides.items():
        assert "OFF-HOURS" in style, f"{tid} override missing OFF-HOURS marker"
    # options-1 is explicitly present but mandates pass (no 24/7 options market).
    assert "pass" in overrides["options-1"].lower(), "options-1 override must mandate pass off-hours"
    print(f"[OK] off-hours override coverage = {len(covered)}/{len(all_tids)} personas")


def test_crypto_signal_gate() -> None:
    """The 0.2% threshold must actually trip on our synthetic quotes."""
    assert itf_app._off_hours_crypto_signal(_synthetic_quotes()) is True
    flat = {k: {**v, "change_pct": 0.0} for k, v in _synthetic_quotes().items()}
    assert itf_app._off_hours_crypto_signal(flat) is False
    print("[OK] _off_hours_crypto_signal gate responds to tape")


def test_fallback_emitter_never_silent_pass_without_tag() -> None:
    """Point #2 guard — every ITF fallback must carry a provider_status tag so
    analytics can segregate uniform-fallback trades from real LLM decisions."""
    for persona in PERSONAS:
        dec = itf_app._uniform_fallback_itf(persona, _ctx())
        assert dec.get("provider_status") == "fallback_uniform", (
            f"{persona['tid']}: fallback emitter dropped provider_status tag "
            f"({dec})"
        )
        # If it's a trade, it must actually point at a live quote ticker.
        if dec.get("action") == "trade":
            assert dec.get("ticker") in _ctx()["quotes"], (
                f"{persona['tid']} fallback chose unknown ticker {dec.get('ticker')}"
            )
    print(f"[OK] {len(PERSONAS)} personas × fallback emitter tagged + live-quote bound")


def _run_all() -> int:
    tests = [
        test_each_persona_sees_all_asset_classes,
        test_off_hours_crypto_pivot_style,
        test_crypto_signal_gate,
        test_fallback_emitter_never_silent_pass_without_tag,
    ]
    fails = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fails += 1
            print(f"[FAIL] {t.__name__}: {e}")
        except Exception as e:
            fails += 1
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
    if fails:
        print(f"\n{fails}/{len(tests)} tests failed")
    else:
        print(f"\nall {len(tests)} tests PASSED")
    return fails


if __name__ == "__main__":
    sys.exit(_run_all())
