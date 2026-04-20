"""
nomos-browser-nba — NBA line scraper HF Space.

Endpoints:
  GET  /api/status              — liveness + provider availability
  POST /api/scrape-nba-lines    — run browser-use agent across {sources}
  GET  /api/latest-lines        — last cached scrape from /data/lines-latest.json

browser-use 0.12.6 + Playwright base. LLM chain:
  1. ChatAnthropic(claude-sonnet-4-6)   if ANTHROPIC_API_KEY
  2. ChatGoogle(gemini-3-flash)          fallback
"""
from __future__ import annotations

import asyncio
import json
import os
import traceback
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths / env
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    DATA_DIR = Path("/tmp/nomos-browser-nba")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

LATEST_LINES = DATA_DIR / "lines-latest.json"
HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY")
BROWSERUSE_KEY = os.environ.get("BROWSERUSE_API_KEY")

# ---------------------------------------------------------------------------
# Lazy browser-use imports — Space must boot even if a dep is broken.
# ---------------------------------------------------------------------------
BROWSER_USE_AVAILABLE = False
BROWSER_USE_IMPORT_ERROR: str | None = None
try:
    from browser_use import Agent as BrowserAgent  # type: ignore
    try:
        from browser_use import ChatAnthropic  # type: ignore
    except Exception:
        ChatAnthropic = None  # type: ignore
    try:
        from browser_use import ChatGoogle  # type: ignore
    except Exception:
        ChatGoogle = None  # type: ignore
    BROWSER_USE_AVAILABLE = True
except Exception as e:  # pragma: no cover — best-effort import
    BROWSER_USE_IMPORT_ERROR = f"{type(e).__name__}: {e}"

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
SOURCE_URLS = {
    "espn": "https://www.espn.com/nba/scoreboard",
    "bbref": "https://www.basketball-reference.com/leagues/NBA_2026_games.html",
    "vegasinsider": "https://www.vegasinsider.com/nba/odds/las-vegas/",
}


class ScrapeRequest(BaseModel):
    sources: list[str] = Field(default_factory=lambda: ["espn"])
    date: str | None = Field(default=None, description="YYYY-MM-DD, default today UTC")
    max_seconds: int = Field(default=180, ge=30, le=600)


class GameLine(BaseModel):
    home: str
    away: str
    ml_home: float | None = None
    ml_away: float | None = None
    spread: float | None = None
    total: float | None = None
    injuries: list[str] = Field(default_factory=list)
    source: str
    fetched_at: str


class ScrapeResponse(BaseModel):
    games: list[GameLine]
    date: str
    sources_attempted: list[str]
    sources_succeeded: list[str]
    errors: dict[str, str] = Field(default_factory=dict)
    raw_outputs: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# LLM selection
# ---------------------------------------------------------------------------
def _pick_llm():
    """Return a browser-use LLM instance, or None if nothing configured."""
    if not BROWSER_USE_AVAILABLE:
        return None
    if ANTHROPIC_KEY and ChatAnthropic is not None:
        try:
            return ChatAnthropic(model="claude-sonnet-4-6", temperature=0.0)
        except Exception:
            pass
    if GOOGLE_KEY and ChatGoogle is not None:
        try:
            return ChatGoogle(model="gemini-3-flash", temperature=0.0)
        except Exception:
            pass
    # Last-chance: try ChatGoogle with default model
    if GOOGLE_KEY and ChatGoogle is not None:
        with suppress(Exception):
            return ChatGoogle(model="gemini-2.5-flash", temperature=0.0)
    return None


def _task_for_source(source: str, date: str) -> str:
    base = SOURCE_URLS.get(source)
    if not base:
        raise ValueError(f"unknown source: {source}")
    return (
        f"Navigate to {base}. For NBA games scheduled on {date}, extract for each game: "
        "home team, away team, moneyline home, moneyline away, spread (home-favored negative), "
        "total (over/under), and any listed injury notes. Return ONLY a JSON array with keys "
        "home, away, ml_home, ml_away, spread, total, injuries (list of strings). "
        "If a field is unavailable leave it null. Do not include commentary."
    )


# ---------------------------------------------------------------------------
# Browser-use runner
# ---------------------------------------------------------------------------
async def _run_source(source: str, date: str, max_seconds: int) -> tuple[list[dict], str]:
    """Run browser-use agent against one source, return (games, raw_output)."""
    if not BROWSER_USE_AVAILABLE:
        raise RuntimeError(f"browser-use not importable: {BROWSER_USE_IMPORT_ERROR}")
    llm = _pick_llm()
    if llm is None:
        raise RuntimeError("no LLM provider configured (set ANTHROPIC_API_KEY or GOOGLE_API_KEY)")

    task = _task_for_source(source, date)
    agent = BrowserAgent(task=task, llm=llm)

    try:
        result = await asyncio.wait_for(agent.run(), timeout=max_seconds)
    except asyncio.TimeoutError:
        raise RuntimeError(f"timeout after {max_seconds}s on source={source}")

    raw = str(result) if result is not None else ""
    # Best-effort JSON extraction from the agent's final message.
    games = _extract_json_games(raw)
    return games, raw[:4000]


def _extract_json_games(raw: str) -> list[dict]:
    """Pull the first JSON array from raw text. Returns [] on failure."""
    if not raw:
        return []
    # Look for the outermost [...] block.
    start = raw.find("[")
    while start != -1:
        depth = 0
        for i in range(start, len(raw)):
            c = raw[i]
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    blob = raw[start : i + 1]
                    try:
                        parsed = json.loads(blob)
                        if isinstance(parsed, list):
                            return parsed
                    except Exception:
                        break
                    break
        start = raw.find("[", start + 1)
    return []


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="nomos-browser-nba", version="0.1.0")

BOOT_TS = datetime.now(timezone.utc).isoformat()


@app.get("/")
def root():
    return {"service": "nomos-browser-nba", "status": "ok", "boot": BOOT_TS}


@app.get("/api/status")
def status():
    return {
        "service": "nomos-browser-nba",
        "boot_ts": BOOT_TS,
        "now_ts": datetime.now(timezone.utc).isoformat(),
        "browser_use_available": BROWSER_USE_AVAILABLE,
        "browser_use_import_error": BROWSER_USE_IMPORT_ERROR,
        "providers": {
            "anthropic": bool(ANTHROPIC_KEY),
            "google": bool(GOOGLE_KEY),
            "browseruse_managed": bool(BROWSERUSE_KEY),
        },
        "sources_supported": list(SOURCE_URLS.keys()),
        "data_dir": str(DATA_DIR),
        "latest_cached": LATEST_LINES.exists(),
    }


@app.get("/api/latest-lines")
def latest_lines():
    if not LATEST_LINES.exists():
        return {"games": [], "note": "no scrape has been cached yet"}
    try:
        return json.loads(LATEST_LINES.read_text())
    except Exception as e:
        raise HTTPException(500, f"cache read failed: {e}")


@app.post("/api/scrape-nba-lines", response_model=ScrapeResponse)
async def scrape_nba_lines(req: ScrapeRequest):
    date = req.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    attempted: list[str] = []
    succeeded: list[str] = []
    errors: dict[str, str] = {}
    raw_outputs: dict[str, str] = {}
    games: list[GameLine] = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for src in req.sources:
        attempted.append(src)
        if src not in SOURCE_URLS:
            errors[src] = "unknown source"
            continue
        try:
            rows, raw = await _run_source(src, date, req.max_seconds)
            raw_outputs[src] = raw
            for row in rows:
                try:
                    games.append(
                        GameLine(
                            home=str(row.get("home", "")).strip(),
                            away=str(row.get("away", "")).strip(),
                            ml_home=_coerce_float(row.get("ml_home")),
                            ml_away=_coerce_float(row.get("ml_away")),
                            spread=_coerce_float(row.get("spread")),
                            total=_coerce_float(row.get("total")),
                            injuries=[str(x) for x in row.get("injuries", []) if x],
                            source=src,
                            fetched_at=fetched_at,
                        )
                    )
                except Exception as e:
                    errors.setdefault(src, f"row parse: {e}")
            succeeded.append(src)
        except Exception as e:
            errors[src] = f"{type(e).__name__}: {e}"
            traceback.print_exc()

    resp = ScrapeResponse(
        games=games,
        date=date,
        sources_attempted=attempted,
        sources_succeeded=succeeded,
        errors=errors,
        raw_outputs=raw_outputs,
    )

    # Persist cache
    try:
        payload = resp.model_dump()
        LATEST_LINES.write_text(json.dumps(payload, indent=2))
        (HISTORY_DIR / f"{date}-{fetched_at.replace(':', '').replace('-', '')[:15]}.json").write_text(
            json.dumps(payload, indent=2)
        )
    except Exception as e:  # pragma: no cover
        print(f"[warn] cache write failed: {e}")

    return resp


def _coerce_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None
