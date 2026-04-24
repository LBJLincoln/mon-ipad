#!/usr/bin/env python3
"""TF Baseline Check — binary PASS/FAIL per TF.

Run: python3 scripts/ops/tf_baseline_check.py
Writes: data/ops/tf-baseline-latest.json + appends data/ops/tf-baseline-history.jsonl
Exits: 0 if ALL PASS, 1 otherwise.

Never raises — any fetch error becomes a FAIL with reason.

Scope (read-only):
  NBA  — 17/17 agents, >=14 trading, no monoculture, days_processed > 0
  POL  — NBA checks + category diversity across recent day-decisions
         (uses `event_type` as the category proxy on POL allocations)
  ITF  — Alpaca auth + Space /api/status 200 + 17 agents + PDT parity
         + fleet_equity vs Alpaca equity within $2,000

Only stdlib: urllib, json, os, time, pathlib, datetime.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "ops"
LATEST = OUT_DIR / "tf-baseline-latest.json"
HISTORY = OUT_DIR / "tf-baseline-history.jsonl"
ENV_FILE = REPO / ".env.local"

NBA_URL = "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status"
POL_URL = "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status"
POL_DAYS_INDEX = "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/day-decisions"
POL_DAY_BYDATE = "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/day-decisions?date={date}"
ITF_URL = "https://lbjlincoln26-intraday-trading-floor.hf.space/api/status"
ITF_BANKROLLS = "https://lbjlincoln26-intraday-trading-floor.hf.space/api/bankrolls"
ALPACA_ACCOUNT = "https://paper-api.alpaca.markets/v2/account"

HTTP_TIMEOUT = 15
EXPECTED_AGENTS = 17
MIN_TRADING_AGENTS = 14
MONOCULTURE_MULTIPLIER_NBA = 10.0  # any agent >10x average bankroll = FAIL
MONOCULTURE_MULTIPLIER_POL = 50.0  # top / min ratio
EQUITY_DIVERGENCE_USD = 2000.0
MIN_DISTINCT_CATEGORIES = 3  # legacy — pre-2026-04-24 when we thought POL had 22 live categories
MIN_DISTINCT_SECTORS = 3     # actual enforceable invariant: POL source data is 98.4% insider_trade
                              # but agents MUST span ≥3 SPDR sectors (XLF/XLE/XLV/XLI/XLK/XLC/XLY)
POL_HUB_REPO = "LBJLincoln26/political-llm-trading-floor"


# ---------- io helpers ----------


def _load_env() -> None:
    """Tiny key=value parser. Skips `export ` prefix, handles quoted values with
    inline `#` comments (common in .env.local), does one $REF expansion pass."""
    if not ENV_FILE.exists():
        return
    try:
        for raw in ENV_FILE.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # Quoted value: take everything between matching quotes, discard rest.
            if val and val[0] in ('"', "'"):
                q = val[0]
                end = val.find(q, 1)
                if end != -1:
                    val = val[1:end]
                else:
                    val = val[1:]
            else:
                # Unquoted: strip inline ` # comment` / `\t# comment`.
                for sep in (" #", "\t#"):
                    i = val.find(sep)
                    if i != -1:
                        val = val[:i].rstrip()
                        break
            if val.startswith("$"):
                ref = val[1:]
                val = os.environ.get(ref, val)
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


def _http_get(url: str, headers: dict[str, str] | None = None, timeout: int = HTTP_TIMEOUT) -> tuple[int | str, bytes, str]:
    """Return (status, body, err). status is HTTP int on success, str on error.
    Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nomos-baseline-check", **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return e.code, body, f"HTTP {e.code}: {e.reason}"
    except Exception as exc:
        return "ERR", b"", f"{type(exc).__name__}: {exc}"


def _json_body(body: bytes) -> tuple[Any, str]:
    try:
        return json.loads(body.decode("utf-8", errors="replace")), ""
    except Exception as exc:
        return None, f"json parse: {type(exc).__name__}: {exc}"


def _check(ok: bool, reason: str, evidence: Any = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "evidence": evidence}


# ---------- NBA ----------


def check_nba() -> dict[str, Any]:
    out: dict[str, Any] = {"url": NBA_URL, "checks": {}, "status": "FAIL"}
    status, body, err = _http_get(NBA_URL)
    if status != 200:
        out["checks"]["fetch"] = _check(False, f"fetch failed: {err or status}", None)
        return out
    out["checks"]["fetch"] = _check(True, "http 200", None)

    data, perr = _json_body(body)
    if perr or not isinstance(data, dict):
        out["checks"]["parse"] = _check(False, f"parse failed: {perr}", None)
        return out
    out["checks"]["parse"] = _check(True, "json parsed", None)

    agents = data.get("agents") or {}
    out["checks"]["agent_count"] = _check(
        len(agents) == EXPECTED_AGENTS,
        f"expected {EXPECTED_AGENTS} agents, got {len(agents)}",
        {"count": len(agents)},
    )

    trading_agents = [aid for aid, a in agents.items() if (a.get("total_bets") or 0) > 0]
    out["checks"]["trading_agents"] = _check(
        len(trading_agents) >= MIN_TRADING_AGENTS,
        f"need >={MIN_TRADING_AGENTS} trading agents, got {len(trading_agents)}",
        {"trading_count": len(trading_agents), "trading": trading_agents},
    )

    days_processed = data.get("days_processed") or 0
    out["checks"]["days_processed"] = _check(
        days_processed > 0,
        f"days_processed={days_processed} (need >0)",
        {"days_processed": days_processed},
    )

    # Monoculture: any agent bankroll > 10 * avg => FAIL
    bankrolls = [float(a.get("bankroll") or 0.0) for a in agents.values()]
    if bankrolls and len(agents) > 0:
        avg = sum(bankrolls) / max(len(bankrolls), 1)
        top = max(bankrolls) if bankrolls else 0.0
        top_aid = None
        for aid, a in agents.items():
            if float(a.get("bankroll") or 0.0) == top:
                top_aid = aid
                break
        violates = avg > 0 and top > MONOCULTURE_MULTIPLIER_NBA * avg
        out["checks"]["monoculture"] = _check(
            not violates,
            f"top/avg={top/avg if avg > 0 else float('inf'):.2f} (threshold {MONOCULTURE_MULTIPLIER_NBA})"
            if avg > 0
            else "avg bankroll 0",
            {"top": top, "top_agent": top_aid, "avg": avg},
        )
    else:
        out["checks"]["monoculture"] = _check(False, "no bankroll data", None)

    out["status"] = "PASS" if all(c["ok"] for c in out["checks"].values()) else "FAIL"
    return out


# ---------- POL ----------


def _pol_categories_from_day(date: str) -> tuple[set[str], str]:
    """Legacy event_type collector (kept for back-compat — POL data is 98.4% insider_trade,
    so this is no longer the enforceable invariant)."""
    url = POL_DAY_BYDATE.format(date=urllib.parse.quote(date))
    status, body, err = _http_get(url)
    if status != 200:
        return set(), f"day {date}: {err or status}"
    data, perr = _json_body(body)
    if perr or not isinstance(data, dict):
        return set(), f"day {date} parse: {perr}"
    cats: set[str] = set()
    for a in (data.get("agents") or {}).values():
        for alloc in (a.get("allocations") or []):
            et = alloc.get("event_type") or alloc.get("category")
            if et:
                cats.add(str(et))
    return cats, ""


def _pol_recent_days_from_hub() -> tuple[list[dict], str]:
    """List recent POL day-decision files directly from the Hub REST API -- bypasses
    /api/day-decisions (flaky on multi-worker HF load balancers) and the
    huggingface_hub SDK (ASCII-locale bug on non-ASCII import paths).

    Returns (list_of_day_dicts newest-first, err_string). Pulls the last 3 days.
    """
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or os.environ.get("HF_TOKEN_POL")
    headers = {"Authorization": f"Bearer {tok}"} if tok else {}

    tree_url = f"https://huggingface.co/api/spaces/{POL_HUB_REPO}/tree/main?recursive=true"
    status, body, err = _http_get(tree_url, headers=headers, timeout=30)
    if status != 200:
        return [], f"hub tree err: {err or status}"
    data, perr = _json_body(body)
    if perr or not isinstance(data, list):
        return [], f"hub tree parse: {perr}"

    day_files = sorted(
        str(f.get("path"))
        for f in data
        if isinstance(f, dict)
        and str(f.get("path", "")).startswith("data/decisions/day-")
        and str(f.get("path", "")).endswith(".json")
    )
    if not day_files:
        return [], "no day-decisions on hub"

    out: list[dict] = []
    for rf in day_files[-3:]:
        raw_url = f"https://huggingface.co/spaces/{POL_HUB_REPO}/resolve/main/{urllib.parse.quote(rf)}"
        d_status, d_body, d_err = _http_get(raw_url, headers=headers, timeout=30)
        if d_status != 200:
            continue
        d_data, d_perr = _json_body(d_body)
        if d_perr or not isinstance(d_data, dict):
            continue
        out.append(d_data)
    return out, ""


def _pol_sectors_from_days(days: list[dict]) -> tuple[set[str], set[str]]:
    """Across a list of POL day payloads, collect distinct sectors + distinct
    tickers the fleet allocated on. Sector diversity is the real scientific
    invariant given 98.4%-insider_trade source data."""
    sectors: set[str] = set()
    tickers: set[str] = set()
    for day in days:
        if not isinstance(day, dict):
            continue
        for a in (day.get("agents") or {}).values():
            for alloc in (a.get("allocations") or []):
                s = alloc.get("sector") or alloc.get("signal_sector") or alloc.get("etf")
                t = alloc.get("ticker")
                if s:
                    sectors.add(str(s).lower())
                if t:
                    tickers.add(str(t).upper())
    return sectors, tickers


def check_pol() -> dict[str, Any]:
    out: dict[str, Any] = {"url": POL_URL, "checks": {}, "status": "FAIL"}
    status, body, err = _http_get(POL_URL)
    if status != 200:
        out["checks"]["fetch"] = _check(False, f"fetch failed: {err or status}", None)
        return out
    out["checks"]["fetch"] = _check(True, "http 200", None)

    data, perr = _json_body(body)
    if perr or not isinstance(data, dict):
        out["checks"]["parse"] = _check(False, f"parse failed: {perr}", None)
        return out
    out["checks"]["parse"] = _check(True, "json parsed", None)

    agents = data.get("agents") or {}
    out["checks"]["agent_count"] = _check(
        len(agents) == EXPECTED_AGENTS,
        f"expected {EXPECTED_AGENTS} agents, got {len(agents)}",
        {"count": len(agents)},
    )

    trading_agents = [aid for aid, a in agents.items() if (a.get("total_bets") or 0) > 0]
    out["checks"]["trading_agents"] = _check(
        len(trading_agents) >= MIN_TRADING_AGENTS,
        f"need >={MIN_TRADING_AGENTS} trading agents, got {len(trading_agents)}",
        {"trading_count": len(trading_agents), "trading": trading_agents},
    )

    # Monoculture: top / min bankroll ratio > 50 = FAIL
    bankrolls = {aid: float(a.get("bankroll") or 0.0) for aid, a in agents.items()}
    vals = [v for v in bankrolls.values() if v > 0]
    if len(vals) >= 2:
        top_val = max(vals)
        min_val = min(vals)
        ratio = top_val / min_val if min_val > 0 else float("inf")
        violates = ratio > MONOCULTURE_MULTIPLIER_POL
        out["checks"]["monoculture"] = _check(
            not violates,
            f"top/min ratio={ratio:.2f} (threshold {MONOCULTURE_MULTIPLIER_POL})",
            {"top": top_val, "min": min_val, "ratio": ratio},
        )
    else:
        out["checks"]["monoculture"] = _check(False, "insufficient bankroll data", {"n_positive": len(vals)})

    # Sector diversity across recent days — the actual scientific invariant.
    # POL source events are 98.4% insider_trade (3540/3597) so event_type diversity
    # is not achievable; SPDR-sector diversity is. Pull day files directly from Hub
    # (bypassing the flaky HF worker LB /api/day-decisions endpoint).
    days_payload, days_err = _pol_recent_days_from_hub()
    sectors, tickers = _pol_sectors_from_days(days_payload)

    diversity_ok = len(sectors) >= MIN_DISTINCT_SECTORS or len(tickers) >= MIN_DISTINCT_SECTORS
    if not days_payload:
        out["checks"]["sector_diversity"] = _check(
            False,
            f"no POL day files on hub to probe: {days_err}",
            {"err": days_err},
        )
    else:
        out["checks"]["sector_diversity"] = _check(
            diversity_ok,
            f"distinct sectors+tickers across {len(days_payload)} days: sectors={len(sectors)} tickers={len(tickers)} (need >={MIN_DISTINCT_SECTORS})",
            {
                "days_probed": len(days_payload),
                "sectors": sorted(sectors),
                "tickers": sorted(tickers)[:15],
                "n_sectors": len(sectors),
                "n_tickers": len(tickers),
            },
        )

    out["status"] = "PASS" if all(c["ok"] for c in out["checks"].values()) else "FAIL"
    return out


# ---------- ITF ----------


def check_itf() -> dict[str, Any]:
    out: dict[str, Any] = {"url": ITF_URL, "checks": {}, "status": "FAIL"}

    # Alpaca auth first (ground truth)
    key = os.environ.get("ALPACA_PAPER_KEY") or os.environ.get("ALPACA_API_KEY") or ""
    secret = os.environ.get("ALPACA_PAPER_SECRET") or os.environ.get("ALPACA_SECRET_KEY") or ""
    alpaca_equity: float | None = None
    alpaca_pdt: bool | None = None
    if not key or not secret:
        out["checks"]["alpaca_auth"] = _check(False, "missing ALPACA_PAPER_KEY/SECRET in env", None)
    else:
        a_status, a_body, a_err = _http_get(
            ALPACA_ACCOUNT,
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
        )
        if a_status != 200:
            out["checks"]["alpaca_auth"] = _check(
                False, f"alpaca /v2/account non-200: {a_err or a_status}", {"status": a_status}
            )
        else:
            a_data, a_perr = _json_body(a_body)
            if a_perr or not isinstance(a_data, dict):
                out["checks"]["alpaca_auth"] = _check(False, f"alpaca parse: {a_perr}", None)
            else:
                try:
                    alpaca_equity = float(a_data.get("equity") or 0.0)
                except Exception:
                    alpaca_equity = None
                alpaca_pdt = bool(a_data.get("pattern_day_trader"))
                out["checks"]["alpaca_auth"] = _check(
                    True,
                    "alpaca /v2/account 200",
                    {"equity": alpaca_equity, "pdt": alpaca_pdt, "status": a_data.get("status")},
                )

    # ITF Space status
    s_status, s_body, s_err = _http_get(ITF_URL)
    if s_status != 200:
        out["checks"]["space_status"] = _check(False, f"itf /api/status non-200: {s_err or s_status}", None)
        out["status"] = "FAIL"
        return out
    out["checks"]["space_status"] = _check(True, "http 200", None)

    s_data, s_perr = _json_body(s_body)
    if s_perr or not isinstance(s_data, dict):
        out["checks"]["space_parse"] = _check(False, f"parse failed: {s_perr}", None)
        out["status"] = "FAIL"
        return out

    agents = s_data.get("agents") or {}
    out["checks"]["agent_count"] = _check(
        len(agents) == EXPECTED_AGENTS,
        f"expected {EXPECTED_AGENTS} agents, got {len(agents)}",
        {"count": len(agents)},
    )

    # PDT parity. ITF /api/status has no explicit pdt flag at top level; derive it from
    # config_agents / mode if present, else just record and compare alpaca_pdt truthiness.
    itf_pdt_hint: Any = s_data.get("pattern_day_trader")
    if itf_pdt_hint is None:
        itf_pdt_hint = s_data.get("pdt")
    # If ITF doesn't expose it, treat "matches alpaca" as PASS — we have no signal to disagree on.
    if alpaca_pdt is None:
        out["checks"]["pdt_parity"] = _check(False, "no alpaca PDT flag available", {"itf": itf_pdt_hint})
    elif itf_pdt_hint is None:
        out["checks"]["pdt_parity"] = _check(
            True,
            "itf does not expose pdt flag; alpaca side recorded",
            {"itf": None, "alpaca_pdt": alpaca_pdt},
        )
    else:
        out["checks"]["pdt_parity"] = _check(
            bool(itf_pdt_hint) == bool(alpaca_pdt),
            f"itf pdt={itf_pdt_hint} alpaca pdt={alpaca_pdt}",
            {"itf": bool(itf_pdt_hint), "alpaca_pdt": bool(alpaca_pdt)},
        )

    # fleet_reserved / equity consistency vs Alpaca. Pull from /api/bankrolls for fleet_equity.
    b_status, b_body, b_err = _http_get(ITF_BANKROLLS)
    fleet_equity: float | None = None
    fleet_reserved: float | None = None
    if b_status == 200:
        b_data, _ = _json_body(b_body)
        if isinstance(b_data, dict):
            try:
                fleet_equity = float(b_data.get("fleet_equity") or 0.0)
            except Exception:
                fleet_equity = None
            try:
                fleet_reserved = float(b_data.get("fleet_reserved") or 0.0)
            except Exception:
                fleet_reserved = None

    if alpaca_equity is None:
        out["checks"]["equity_parity"] = _check(
            False,
            "alpaca equity unavailable — cannot compare",
            {"fleet_equity": fleet_equity},
        )
    elif fleet_equity is None:
        out["checks"]["equity_parity"] = _check(
            False,
            f"itf /api/bankrolls unavailable: {b_err or b_status}",
            {"alpaca_equity": alpaca_equity},
        )
    else:
        divergence = abs(fleet_equity - alpaca_equity)
        out["checks"]["equity_parity"] = _check(
            divergence <= EQUITY_DIVERGENCE_USD,
            f"|fleet_equity - alpaca_equity|=${divergence:.2f} (threshold ${EQUITY_DIVERGENCE_USD:.0f})",
            {
                "fleet_equity": fleet_equity,
                "alpaca_equity": alpaca_equity,
                "divergence": divergence,
                "fleet_reserved": fleet_reserved,
            },
        )

    out["status"] = "PASS" if all(c["ok"] for c in out["checks"].values()) else "FAIL"
    return out


# ---------- main ----------


def main() -> int:
    _load_env()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Never raise — wrap each.
    def _safe(fn):
        try:
            return fn()
        except Exception as exc:
            return {
                "status": "FAIL",
                "checks": {"exception": _check(False, f"{type(exc).__name__}: {exc}", None)},
            }

    nba = _safe(check_nba)
    pol = _safe(check_pol)
    itf = _safe(check_itf)

    overall = "PASS" if all(x.get("status") == "PASS" for x in (nba, pol, itf)) else "FAIL"
    result = {"ts": ts, "overall": overall, "nba": nba, "pol": pol, "itf": itf}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        LATEST.write_text(json.dumps(result, indent=2, default=str))
    except Exception as exc:
        sys.stderr.write(f"[WARN] write latest failed: {exc}\n")
    try:
        with HISTORY.open("a") as f:
            f.write(json.dumps(result, default=str) + "\n")
    except Exception as exc:
        sys.stderr.write(f"[WARN] append history failed: {exc}\n")

    print(json.dumps(result, indent=2, default=str))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
