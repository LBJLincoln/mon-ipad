#!/usr/bin/env python3
"""
Monitor HF Trading Floor Experiment
Checks process status, HF Space runtime, result files, and system resources.
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ────────────────────────────────────────────────────────────────────
REPO_ROOT       = Path("/home/termius/mon-ipad")
ENV_FILE        = REPO_ROOT / ".env.local"
LOG_FILE        = REPO_ROOT / "logs/hf-trading-floor-run.log"
DATA_DIR        = REPO_ROOT / "data/arena"
RESULTS_GLOB    = "hf-trading-floor-results*"
TARGET_PID      = 1012872

SPACES_TO_CHECK = [
    {
        "label": "LBJLincoln26/nba-llm-trading-floor (active client)",
        "api_url": "https://huggingface.co/api/spaces/LBJLincoln26/nba-llm-trading-floor/runtime",
        "space_url": "https://lbjlincoln26-nba-llm-trading-floor.hf.space",
        "token_env": "HF_TOKEN_NBA",
    },
    {
        "label": "Nomos42/hf-llm-trading-floor",
        "api_url": "https://huggingface.co/api/spaces/Nomos42/hf-llm-trading-floor/runtime",
        "space_url": "https://nomos42-hf-llm-trading-floor.hf.space",
        "token_env": "HF_TOKEN_LLM",
    },
]

# ─── Helpers ───────────────────────────────────────────────────────────────────

def load_env():
    """Source .env.local and inject exports into os.environ."""
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            # Strip surrounding quotes
            val = val.strip('"').strip("'")
            key = key.strip()
            if key and val:
                os.environ.setdefault(key, val)


def hf_api_get(url: str, token: str) -> dict:
    """GET from HF API, return parsed JSON or error dict."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def get_process_info(pid: int) -> dict:
    """Return process info dict for given PID via /proc."""
    proc_dir = Path(f"/proc/{pid}")
    if not proc_dir.exists():
        return {"alive": False}

    info: dict = {"alive": True, "pid": pid}

    # uptime from /proc/PID/stat (field 22 = starttime in clock ticks)
    try:
        stat_text  = proc_dir.joinpath("stat").read_text()
        # find closing paren to skip process name which may contain spaces
        paren_end  = stat_text.rfind(")")
        fields     = stat_text[paren_end + 2:].split()
        starttime  = int(fields[19])       # field 22 is index 19 after the comm field
        clk_tck    = os.sysconf("SC_CLK_TCK")
        boot_secs  = float(Path("/proc/uptime").read_text().split()[0])
        system_uptime = time.time() - boot_secs
        proc_start = system_uptime + (starttime / clk_tck)
        elapsed    = time.time() - proc_start
        h, rem     = divmod(int(elapsed), 3600)
        m, s       = divmod(rem, 60)
        info["uptime"] = f"{h:d}h {m:02d}m {s:02d}s"
        info["elapsed_secs"] = elapsed
    except Exception:
        info["uptime"] = "unknown"
        info["elapsed_secs"] = 0

    # memory from /proc/PID/status
    try:
        status_text = proc_dir.joinpath("status").read_text()
        for line in status_text.splitlines():
            if line.startswith("VmRSS:"):
                kb = int(line.split()[1])
                info["mem_mb"] = round(kb / 1024, 1)
                break
    except Exception:
        info["mem_mb"] = 0

    # command snippet
    try:
        cmdline = proc_dir.joinpath("cmdline").read_bytes().decode(errors="replace")
        parts   = cmdline.replace("\x00", " ").split()
        info["cmd"] = " ".join(parts[:4]) + ("..." if len(parts) > 4 else "")
    except Exception:
        info["cmd"] = "?"

    return info


def tail_log(path: Path, n: int = 12) -> list[str]:
    if not path.exists():
        return []
    try:
        result = subprocess.run(
            ["tail", "-n", str(n), str(path)],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.splitlines()
    except Exception:
        return []


def system_resources() -> dict:
    """Return memory and disk usage."""
    res = {}
    try:
        mem_info = Path("/proc/meminfo").read_text()
        mem = {}
        for line in mem_info.splitlines():
            k, _, v = line.partition(":")
            mem[k.strip()] = int(v.strip().split()[0]) if v.strip() else 0
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        used  = total - avail
        res["mem_total_mb"] = round(total / 1024, 0)
        res["mem_used_mb"]  = round(used  / 1024, 0)
        res["mem_pct"]      = round(used / total * 100, 1) if total else 0
    except Exception:
        pass

    try:
        df = subprocess.run(
            ["df", "-h", str(REPO_ROOT)],
            capture_output=True, text=True, timeout=5,
        )
        for line in df.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 5:
                res["disk_total"]  = parts[1]
                res["disk_used"]   = parts[2]
                res["disk_avail"]  = parts[3]
                res["disk_pct"]    = parts[4]
                break
    except Exception:
        pass

    return res


def try_gradio_status(space_url: str) -> str:
    """Try a lightweight GET on the space root or info endpoint."""
    endpoints = ["/info", "/", ""]
    for ep in endpoints:
        try:
            url = space_url.rstrip("/") + ep
            req = urllib.request.Request(url, headers={"User-Agent": "monitor/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    body = resp.read(512).decode(errors="replace")
                    if "gradio" in body.lower() or "trading" in body.lower():
                        return f"HTTP 200 ({ep or '/'})"
                    return f"HTTP 200 ({ep or '/'}) — non-Gradio response"
                return f"HTTP {resp.status} ({ep or '/'})"
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code} ({ep or '/'})"
        except Exception:
            pass
    return "unreachable"


# ─── Output helpers ─────────────────────────────────────────────────────────────

SEP = "─" * 60

def header(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)

def row(label: str, value: str, width: int = 26):
    print(f"  {label:<{width}} {value}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    load_env()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"\n{'═' * 60}")
    print(f"  HF Trading Floor — Experiment Monitor")
    print(f"  {now}")
    print(f"{'═' * 60}")

    # ── 1. Process status ────────────────────────────────────────────────────
    header("1. PROCESS STATUS (PID 1012872)")
    pinfo = get_process_info(TARGET_PID)
    if pinfo["alive"]:
        row("Status:", "ALIVE")
        row("PID:", str(TARGET_PID))
        row("Uptime:", pinfo.get("uptime", "?"))
        row("Memory (RSS):", f"{pinfo.get('mem_mb', 0)} MB")
        row("Command:", pinfo.get("cmd", "?"))
        elapsed = pinfo.get("elapsed_secs", 0)
        if elapsed > 0:
            # rough progress: full season ~8h = 28800s
            est_total = 8 * 3600
            pct = min(100.0, elapsed / est_total * 100)
            row("Est. progress:", f"~{pct:.0f}% (assuming 8h total)")
    else:
        row("Status:", "DEAD / NOT FOUND")
        row("Note:", "Process may have finished or been killed")

    # ── 2. Log tail ──────────────────────────────────────────────────────────
    header("2. PROCESS LOG (last 12 lines)")
    lines = tail_log(LOG_FILE)
    if lines:
        for line in lines:
            print(f"  {line}")
    else:
        if LOG_FILE.exists():
            print(f"  (log exists but is empty: {LOG_FILE})")
        else:
            print(f"  (no log file at {LOG_FILE})")

    # ── 3. HF Space runtime ──────────────────────────────────────────────────
    header("3. HF SPACE RUNTIME STATUS")
    for space in SPACES_TO_CHECK:
        token = os.environ.get(space["token_env"], "")
        print(f"\n  [{space['label']}]")
        if not token:
            row("  Token:", f"{space['token_env']} not found in env")
            continue
        data = hf_api_get(space["api_url"], token)
        if "error" in data:
            row("  Runtime:", f"ERROR — {data['error']}")
        else:
            stage      = data.get("stage", "?")
            hw_current = data.get("hardware", {}).get("current", "?")
            hw_req     = data.get("hardware", {}).get("requested", "?")
            replicas   = data.get("replicas", {}).get("current", "?")
            gc_timeout = data.get("gcTimeout", "?")
            domains    = [d.get("domain", "") for d in data.get("domains", [])]
            row("  Stage:", stage)
            row("  Hardware:", f"{hw_current} (requested: {hw_req})")
            row("  Replicas:", str(replicas))
            row("  GC timeout:", f"{gc_timeout}s ({int(gc_timeout)//3600}h)" if isinstance(gc_timeout, int) else str(gc_timeout))
            if domains:
                row("  Domains:", ", ".join(domains))
            # try gradio reachability
            space_status = try_gradio_status(space["space_url"])
            row("  HTTP probe:", space_status)

    # ── 4. Result files ──────────────────────────────────────────────────────
    header("4. RESULT FILES")
    results = sorted(DATA_DIR.glob(RESULTS_GLOB)) if DATA_DIR.exists() else []
    if results:
        for rf in results:
            size_kb = round(rf.stat().st_size / 1024, 1)
            mtime   = datetime.fromtimestamp(rf.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            row(rf.name, f"{size_kb} KB — modified {mtime}")
            # Try to parse and show summary
            try:
                with open(rf) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    if "status" in data:
                        row("  └ status:", str(data["status"])[:80])
                    if "elapsed_hours" in data:
                        row("  └ elapsed:", f"{data['elapsed_hours']}h")
                    if "leaderboard" in data and isinstance(data["leaderboard"], dict):
                        lb = data["leaderboard"]
                        row("  └ leaderboard keys:", ", ".join(list(lb.keys())[:6]))
                    if "games_processed" in data:
                        row("  └ games_processed:", str(data["games_processed"]))
            except Exception:
                pass
    else:
        row("Result files:", "none found matching hf-trading-floor-results*")
        row("Data dir:", str(DATA_DIR))

    # ── 5. System resources ──────────────────────────────────────────────────
    header("5. SYSTEM RESOURCES")
    res = system_resources()
    if res:
        if "mem_total_mb" in res:
            row("RAM total:", f"{res['mem_total_mb']:.0f} MB")
            row("RAM used:", f"{res['mem_used_mb']:.0f} MB ({res['mem_pct']}%)")
        if "disk_total" in res:
            row("Disk total:", res["disk_total"])
            row("Disk used:", f"{res['disk_used']} ({res['disk_pct']})")
            row("Disk avail:", res["disk_avail"])
    else:
        row("Resources:", "could not read")

    # ── 6. Quick summary ─────────────────────────────────────────────────────
    header("6. SUMMARY")
    proc_status = "ALIVE" if pinfo["alive"] else "DEAD"
    uptime_str  = pinfo.get("uptime", "?") if pinfo["alive"] else "—"

    print(f"  Process {TARGET_PID}:   {proc_status} (uptime: {uptime_str})")
    space_statuses = []
    for space in SPACES_TO_CHECK:
        token = os.environ.get(space["token_env"], "")
        if token:
            data = hf_api_get(space["api_url"], token)
            stage = data.get("stage", data.get("error", "?"))
        else:
            stage = "no-token"
        space_statuses.append(f"{space['label'].split('/')[0].split(' ')[0]}/{space['label'].split('/')[1].split(' ')[0]}={stage}")
    print(f"  HF Spaces:       {', '.join(space_statuses)}")
    print(f"  Result files:    {len(results)} found")
    if res.get("mem_pct"):
        print(f"  VM memory:       {res['mem_pct']}% used")

    print(f"\n{'═' * 60}\n")


if __name__ == "__main__":
    main()
