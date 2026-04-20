"""
nomos-browser-qa — pixel-world + dashboard visual QA HF Space.

Runs Playwright directly for low-level DOM assertions (cheap + deterministic),
plus browser-use agent for any higher-level nav tasks if needed.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import traceback
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
    DATA_DIR = Path("/tmp/nomos-browser-qa")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

QA_DIR = DATA_DIR / "qa-runs"
QA_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY")

PIXEL_WORLD_URL = os.environ.get(
    "PIXEL_WORLD_URL", "https://nomos42-pixel-world.static.hf.space"
)
DASHBOARD_BASE = os.environ.get("DASHBOARD_URL", "https://nomosdashboard.vercel.app")
DASHBOARD_ROUTES = ["/nba", "/political", "/world"]
DASHBOARD_PRICING = "/pricing"

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------
PLAYWRIGHT_AVAILABLE = False
PLAYWRIGHT_IMPORT_ERROR: str | None = None
try:
    from playwright.async_api import async_playwright  # type: ignore

    PLAYWRIGHT_AVAILABLE = True
except Exception as e:  # pragma: no cover
    PLAYWRIGHT_IMPORT_ERROR = f"{type(e).__name__}: {e}"

BROWSER_USE_AVAILABLE = False
BROWSER_USE_IMPORT_ERROR: str | None = None
try:
    from browser_use import Agent as BrowserAgent  # type: ignore  # noqa: F401

    BROWSER_USE_AVAILABLE = True
except Exception as e:  # pragma: no cover
    BROWSER_USE_IMPORT_ERROR = f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class QAPixelRequest(BaseModel):
    url: str | None = None
    min_sprites: int = Field(default=40, ge=1)
    capture_screenshot: bool = True
    timeout_s: int = Field(default=45, ge=5, le=180)


class QADashboardRequest(BaseModel):
    base_url: str | None = None
    routes: list[str] | None = None
    check_pricing: bool = True
    timeout_s: int = Field(default=60, ge=5, le=240)


class QARun(BaseModel):
    kind: str
    passed: bool
    ts: str
    details: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_run(run: QARun) -> Path:
    safe_ts = run.ts.replace(":", "").replace("-", "")[:15]
    path = QA_DIR / f"{run.kind}-{safe_ts}.json"
    path.write_text(run.model_dump_json(indent=2))
    return path


async def _new_browser():
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            f"playwright unavailable: {PLAYWRIGHT_IMPORT_ERROR}"
        )
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    return pw, browser, ctx


async def _shutdown(pw, browser):
    with _suppress():
        await browser.close()
    with _suppress():
        await pw.stop()


class _suppress:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return True


# ---------------------------------------------------------------------------
# Pixel QA
# ---------------------------------------------------------------------------
async def _qa_pixel_impl(req: QAPixelRequest) -> QARun:
    url = req.url or PIXEL_WORLD_URL
    ts = datetime.now(timezone.utc).isoformat()
    details: dict[str, Any] = {"url": url}
    passed = False

    pw = browser = None
    try:
        pw, browser, ctx = await _new_browser()
        page = await ctx.new_page()

        console_errors: list[str] = []
        page.on(
            "console",
            lambda msg: console_errors.append(f"{msg.type}: {msg.text}")
            if msg.type in {"error", "warning"}
            else None,
        )
        page.on("pageerror", lambda err: console_errors.append(f"pageerror: {err}"))

        await page.goto(url, wait_until="load", timeout=req.timeout_s * 1000)
        # Give the pixel world time to animate in.
        await asyncio.sleep(3)

        # Count sprites: common selectors used in pixel-world builds.
        sprite_count = 0
        for sel in [
            "[data-sprite]",
            ".agent-sprite",
            ".sprite",
            "canvas",
            ".pixel-agent",
        ]:
            try:
                count = await page.locator(sel).count()
                sprite_count = max(sprite_count, count)
            except Exception:
                pass

        # HP-bar heuristic
        hp_count = 0
        for sel in [".hp-bar", "[data-hp]", ".health"]:
            try:
                hp_count = max(hp_count, await page.locator(sel).count())
            except Exception:
                pass

        # DOM size as a liveness fallback when selectors unknown.
        try:
            dom_size = await page.evaluate("document.querySelectorAll('*').length")
        except Exception:
            dom_size = 0

        screenshot_b64 = None
        if req.capture_screenshot:
            try:
                shot = await page.screenshot(full_page=True, type="png")
                screenshot_b64 = base64.b64encode(shot).decode("ascii")[:40000]
            except Exception as e:
                details["screenshot_error"] = str(e)

        real_errors = [
            e for e in console_errors if "error" in e.lower() and "warning" not in e.lower()
        ]

        details.update(
            sprite_count=sprite_count,
            hp_bar_count=hp_count,
            dom_size=dom_size,
            console_errors=real_errors[:20],
            console_warnings=[e for e in console_errors if "warning" in e.lower()][:10],
            screenshot_b64_preview=screenshot_b64,
        )

        passed = (
            sprite_count >= req.min_sprites or dom_size >= 200
        ) and len(real_errors) == 0

    except Exception as e:
        details["error"] = f"{type(e).__name__}: {e}"
        details["traceback"] = traceback.format_exc()[-2000:]
    finally:
        if pw and browser:
            await _shutdown(pw, browser)

    run = QARun(kind="pixel", passed=passed, ts=ts, details=details)
    _write_run(run)
    return run


# ---------------------------------------------------------------------------
# Dashboard QA
# ---------------------------------------------------------------------------
async def _qa_dashboard_impl(req: QADashboardRequest) -> QARun:
    base = (req.base_url or DASHBOARD_BASE).rstrip("/")
    routes = req.routes or DASHBOARD_ROUTES
    ts = datetime.now(timezone.utc).isoformat()
    details: dict[str, Any] = {"base_url": base, "routes": routes}
    per_route: dict[str, Any] = {}
    passed = True

    pw = browser = None
    try:
        pw, browser, ctx = await _new_browser()

        for route in routes:
            full = f"{base}{route}"
            page = await ctx.new_page()
            console_errors: list[str] = []
            page.on(
                "pageerror", lambda err, _c=console_errors: _c.append(f"pageerror: {err}")
            )
            page.on(
                "console",
                lambda msg, _c=console_errors: _c.append(f"{msg.type}: {msg.text}")
                if msg.type == "error"
                else None,
            )
            try:
                resp = await page.goto(full, wait_until="load", timeout=req.timeout_s * 1000)
                status = resp.status if resp else None
                title = await page.title()
                dom_size = await page.evaluate("document.querySelectorAll('*').length")
            except Exception as e:
                per_route[route] = {"error": f"{type(e).__name__}: {e}"}
                passed = False
                await page.close()
                continue

            route_passed = (
                status is not None and status < 400 and len(console_errors) == 0
            )
            if not route_passed:
                passed = False

            per_route[route] = {
                "status": status,
                "title": title,
                "dom_size": dom_size,
                "console_errors": console_errors[:15],
                "passed": route_passed,
            }
            await page.close()

        # Pricing page (optional)
        if req.check_pricing:
            pricing_url = f"{base}{DASHBOARD_PRICING}"
            page = await ctx.new_page()
            pricing_info: dict[str, Any] = {"url": pricing_url}
            try:
                resp = await page.goto(
                    pricing_url, wait_until="load", timeout=req.timeout_s * 1000
                )
                status = resp.status if resp else None
                body = await page.content()
                has_stripe = (
                    "stripe.com" in body.lower()
                    or "buy.stripe" in body.lower()
                    or "checkout.stripe" in body.lower()
                )
                pricing_info.update(
                    status=status, has_stripe_link=has_stripe, body_len=len(body)
                )
            except Exception as e:
                pricing_info["error"] = f"{type(e).__name__}: {e}"
            finally:
                await page.close()
            details["pricing"] = pricing_info

    except Exception as e:
        details["error"] = f"{type(e).__name__}: {e}"
        details["traceback"] = traceback.format_exc()[-2000:]
        passed = False
    finally:
        if pw and browser:
            await _shutdown(pw, browser)

    details["per_route"] = per_route
    run = QARun(kind="dashboard", passed=passed, ts=ts, details=details)
    _write_run(run)
    return run


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="nomos-browser-qa", version="0.1.0")
BOOT_TS = datetime.now(timezone.utc).isoformat()


@app.get("/")
def root():
    return {"service": "nomos-browser-qa", "status": "ok", "boot": BOOT_TS}


@app.get("/api/status")
def status():
    return {
        "service": "nomos-browser-qa",
        "boot_ts": BOOT_TS,
        "now_ts": datetime.now(timezone.utc).isoformat(),
        "playwright_available": PLAYWRIGHT_AVAILABLE,
        "playwright_import_error": PLAYWRIGHT_IMPORT_ERROR,
        "browser_use_available": BROWSER_USE_AVAILABLE,
        "browser_use_import_error": BROWSER_USE_IMPORT_ERROR,
        "providers": {"anthropic": bool(ANTHROPIC_KEY), "google": bool(GOOGLE_KEY)},
        "pixel_world_url": PIXEL_WORLD_URL,
        "dashboard_base": DASHBOARD_BASE,
        "qa_runs_cached": len(list(QA_DIR.glob("*.json"))),
    }


@app.get("/api/latest-qa")
def latest_qa():
    runs: list[dict] = []
    paths = sorted(QA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
    for p in paths:
        try:
            data = json.loads(p.read_text())
            # Scrub heavy screenshots from summary
            if isinstance(data.get("details"), dict):
                data["details"].pop("screenshot_b64_preview", None)
            runs.append(data)
        except Exception as e:  # pragma: no cover
            runs.append({"file": p.name, "error": str(e)})
    return {"runs": runs, "count": len(runs)}


@app.post("/api/qa-pixel", response_model=QARun)
async def qa_pixel(req: QAPixelRequest):
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(503, f"playwright unavailable: {PLAYWRIGHT_IMPORT_ERROR}")
    return await _qa_pixel_impl(req)


@app.post("/api/qa-dashboard", response_model=QARun)
async def qa_dashboard(req: QADashboardRequest):
    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(503, f"playwright unavailable: {PLAYWRIGHT_IMPORT_ERROR}")
    return await _qa_dashboard_impl(req)
