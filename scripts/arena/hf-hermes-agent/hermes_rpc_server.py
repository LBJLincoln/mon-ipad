"""
nomos-hermes-agent — FastAPI RPC wrapper over NousResearch/hermes-agent CLI.

If the `hermes` binary is not installed (HF builder blocked the installer),
the server still boots and returns a structured stub response so that callers
can detect degradation without crashing.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths / env
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _persistent_data = True
except PermissionError:
    DATA_DIR = Path("/tmp/nomos-hermes")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _persistent_data = False

HERMES_CONFIG_DIR = Path(os.environ.get("HERMES_CONFIG_DIR", str(DATA_DIR / ".hermes")))
try:
    HERMES_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    HERMES_CONFIG_DIR = Path("/tmp/.hermes")
    HERMES_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_DIR = DATA_DIR / "tasks"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

NOUS_KEY = os.environ.get("NOUS_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODAL_TOKEN_ID = os.environ.get("MODAL_TOKEN_ID")


def _find_hermes_binary() -> str | None:
    """Locate the hermes CLI across common install paths."""
    if (path := shutil.which("hermes")):
        return path
    candidates = [
        Path.home() / ".local/bin/hermes",
        Path("/home/user/.local/bin/hermes"),
        Path("/usr/local/bin/hermes"),
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    return None


HERMES_BIN = _find_hermes_binary()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class TaskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=32_000)
    model: str | None = None
    timeout_s: int = Field(default=180, ge=10, le=900)


class TaskResponse(BaseModel):
    ok: bool
    stub: bool
    prompt_preview: str
    model_used: str | None
    stdout: str
    stderr: str
    duration_s: float
    ts: str
    warning: str | None = None


class SkillsResponse(BaseModel):
    ok: bool
    stub: bool
    stdout: str
    stderr: str


# ---------------------------------------------------------------------------
# Command runner
# ---------------------------------------------------------------------------
async def _run_hermes(args: list[str], input_text: str | None, timeout: int) -> tuple[str, str, int]:
    if HERMES_BIN is None:
        return "", "hermes binary not installed", 127

    env = os.environ.copy()
    env["HERMES_CONFIG_DIR"] = str(HERMES_CONFIG_DIR)

    proc = await asyncio.create_subprocess_exec(
        HERMES_BIN,
        *args,
        stdin=asyncio.subprocess.PIPE if input_text is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(
                input=input_text.encode("utf-8") if input_text is not None else None
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        return "", f"hermes timed out after {timeout}s", 124

    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        proc.returncode or 0,
    )


def _stub_response(prompt: str, model: str | None, warning: str) -> TaskResponse:
    return TaskResponse(
        ok=False,
        stub=True,
        prompt_preview=prompt[:200],
        model_used=model,
        stdout=json.dumps(
            {
                "stub": True,
                "echo": prompt[:500],
                "note": "hermes CLI not installed in this image — returning structured stub",
            },
            indent=2,
        ),
        stderr="",
        duration_s=0.0,
        ts=datetime.now(timezone.utc).isoformat(),
        warning=warning,
    )


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="nomos-hermes-agent", version="0.1.0")
BOOT_TS = datetime.now(timezone.utc).isoformat()


@app.get("/")
def root():
    return {"service": "nomos-hermes-agent", "status": "ok", "boot": BOOT_TS}


@app.get("/api/status")
def status():
    return {
        "service": "nomos-hermes-agent",
        "boot_ts": BOOT_TS,
        "now_ts": datetime.now(timezone.utc).isoformat(),
        "hermes_bin": HERMES_BIN,
        "binary_missing": HERMES_BIN is None,
        "persistent_data": _persistent_data,
        "config_dir": str(HERMES_CONFIG_DIR),
        "data_dir": str(DATA_DIR),
        "providers": {
            "nous": bool(NOUS_KEY),
            "openrouter": bool(OPENROUTER_KEY),
            "anthropic": bool(ANTHROPIC_KEY),
            "modal": bool(MODAL_TOKEN_ID),
        },
        "history_count": len(list(HISTORY_DIR.glob("*.json"))),
    }


@app.post("/api/task", response_model=TaskResponse)
async def run_task(req: TaskRequest):
    ts = datetime.now(timezone.utc).isoformat()
    if HERMES_BIN is None:
        resp = _stub_response(
            req.prompt,
            req.model,
            warning="hermes binary not installed — install script failed at build time",
        )
        _persist_task(req, resp)
        return resp

    args: list[str] = []
    if req.model:
        args += ["--model", req.model]
    args += ["--task", "-"]

    start = datetime.now(timezone.utc)
    stdout, stderr, rc = await _run_hermes(args, req.prompt, req.timeout_s)
    duration = (datetime.now(timezone.utc) - start).total_seconds()

    resp = TaskResponse(
        ok=rc == 0,
        stub=False,
        prompt_preview=req.prompt[:200],
        model_used=req.model,
        stdout=stdout[:20000],
        stderr=stderr[:5000],
        duration_s=duration,
        ts=ts,
        warning=None if rc == 0 else f"hermes exited rc={rc}",
    )
    _persist_task(req, resp)
    return resp


@app.post("/api/skills", response_model=SkillsResponse)
async def list_skills():
    if HERMES_BIN is None:
        return SkillsResponse(
            ok=False,
            stub=True,
            stdout=json.dumps({"stub": True, "skills": []}),
            stderr="hermes binary not installed",
        )
    stdout, stderr, rc = await _run_hermes(["skills", "list"], None, 30)
    return SkillsResponse(ok=rc == 0, stub=False, stdout=stdout, stderr=stderr)


def _persist_task(req: TaskRequest, resp: TaskResponse) -> None:
    try:
        safe_ts = resp.ts.replace(":", "").replace("-", "")[:15]
        path = HISTORY_DIR / f"task-{safe_ts}.json"
        path.write_text(
            json.dumps(
                {"request": req.model_dump(), "response": resp.model_dump()}, indent=2
            )
        )
    except Exception as e:  # pragma: no cover
        print(f"[warn] task persistence failed: {e}")
