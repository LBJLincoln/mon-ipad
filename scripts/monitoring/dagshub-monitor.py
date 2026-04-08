#!/usr/bin/env python3
"""
Nomos42 DagsHub Infrastructure Monitor
========================================
Monitors all HF Spaces, VM system metrics, websites, and services.
Logs to DagsHub (if DAGSHUB_TOKEN set) and always to local JSON/CSV.

Run via cron every 30 min:
    20,50 * * * * python3 /home/termius/mon-ipad/scripts/monitoring/dagshub-monitor.py

Endpoints monitored (27 total):
    - 10 NBA Evolution Islands (S10-S19)
    - 4 Political Alpha Islands (P1-P4)
    - 9 Department Council Spaces (D1-D9)
    - 2 Services (dashboard, Bloomberg API)
    - VM system metrics (CPU, RAM, disk)

DagsHub auth: export DAGSHUB_TOKEN=<your-token> in .env.local
Falls back to local-only JSON logging if DagsHub is unavailable.

NOTE: dagshub import takes ~14s on this VM (1vCPU/969MB), so it is loaded
lazily AFTER probing to keep total runtime under 60s.
"""

import csv
import json
import os
import shutil
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# ---------- paths ---------------------------------------------------------
BASE = Path(__file__).resolve().parents[2]  # mon-ipad root
STATUS_DIR = BASE / "data" / "monitoring"
STATUS_FILE = STATUS_DIR / "dagshub-status.json"
HISTORY_DIR = STATUS_DIR / "history"
METRICS_CSV = STATUS_DIR / "metrics.csv"

STATUS_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# ---------- constants -----------------------------------------------------
PROBE_TIMEOUT = 8       # seconds per HTTP probe
MAX_WORKERS = 10        # parallel probe threads
CPU_SAMPLE_SEC = 0.5    # CPU measurement sample window

DAGSHUB_OWNER = "LBJLincoln"
DAGSHUB_REPO = "nomos42-monitor"


# ---------- endpoint definitions ------------------------------------------

NBA_SPACES = {
    "S10_exploit":      "https://nomos42-nba-quant.hf.space/",
    "S11_explore":      "https://nomos42-nba-quant-2.hf.space/",
    "S12_extra_trees":  "https://nomos42-nba-evo-3.hf.space/",
    "S13_catboost":     "https://nomos42-nba-evo-4.hf.space/",
    "S14_lightgbm":     "https://nomos42-nba-evo-5.hf.space/",
    "S15_wide":         "https://nomos42-nba-evo-6.hf.space/",
    "S16_gradient":     "https://lbjlincoln26-nba-evo-s16.hf.space/",
    "S17_ensemble":     "https://lbjlincoln26-nba-evo-s17.hf.space/",
    "S18_cat_brier":    "https://testforge42-nba-evo-s18.hf.space/",
    "S19_ultra_wide":   "https://testforge42-nba-evo-s19.hf.space/",
}

POLITICAL_SPACES = {
    "P1_exploit":       "https://nomos42-political-alpha.hf.space/",
    "P2_explore":       "https://nomos42-political-alpha-2.hf.space/",
    "P3_political3":    "https://lbjlincoln-political-alpha-3.hf.space/",
    "P4_political4":    "https://lbjlincoln-political-alpha-4.hf.space/",
}

COUNCIL_SPACES = {
    "D1_research":      "https://lbjlincoln-nomos-dept-d1-research.hf.space/",
    "D2_engineering":   "https://lbjlincoln-nomos-dept-d2-engineering.hf.space/",
    "D3_evolution":     "https://lbjlincoln26-nomos-dept-d3-evolution.hf.space/",
    "D4_product":       "https://lbjlincoln26-nomos-dept-d4-product.hf.space/",
    "D5_business":      "https://nomos42-nomos-dept-d5-business.hf.space/",
    "D6_evaluation":    "https://nomos42-nomos-dept-d6-evaluation.hf.space/",
    "D7_infra":         "https://testforge42-nomos-dept-d7-infra.hf.space/",
    "D8_finance":       "https://testforge42-nomos-dept-d8-finance.hf.space/",
    "D9_cross_repo":    "https://testforge42-nomos-dept-d9-cross-repo.hf.space/",
}

SERVICES = {
    "dashboard":        "https://nomos42.com/",
    "bloomberg_api":    "http://localhost:8042/",
}

# 4 GPU websites × multi-account (public landing probes — we cannot auth
# without exposing tokens, but a 200 landing proves DNS + TLS + platform up).
GPU_PLATFORMS = {
    "kaggle_lbjlincoln":    "https://www.kaggle.com/",
    "colab_lbjlincoln":     "https://colab.research.google.com/",
    "colab_aurelien":       "https://colab.research.google.com/",
    "lightning_main":       "https://lightning.ai/",
    "lightning_secondary":  "https://lightning.ai/",
    "modal_main":           "https://modal.com/",
}


# ---------- probe functions -----------------------------------------------

def probe_url(url: str, timeout: int = PROBE_TIMEOUT) -> dict:
    """Probe a URL and return status code + latency."""
    start = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "Nomos42-Monitor/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((time.time() - start) * 1000, 1)
            return {"status": resp.status, "latency_ms": latency_ms, "ok": True}
    except urllib.error.HTTPError as e:
        latency_ms = round((time.time() - start) * 1000, 1)
        return {"status": e.code, "latency_ms": latency_ms, "ok": e.code < 500}
    except urllib.error.URLError as e:
        latency_ms = round((time.time() - start) * 1000, 1)
        return {"status": 0, "latency_ms": latency_ms, "ok": False,
                "error": str(e.reason)[:80]}
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 1)
        return {"status": 0, "latency_ms": latency_ms, "ok": False,
                "error": str(e)[:80]}


def probe_hf(label: str, url: str) -> tuple:
    """Probe HF Space + optional /api/status. Returns (label, result_dict)."""
    result = probe_url(url)
    # Only try /api/status if main probe succeeded
    if result["ok"]:
        api_url = url.rstrip("/") + "/api/status"
        try:
            req = urllib.request.Request(api_url, method="GET")
            req.add_header("User-Agent", "Nomos42-Monitor/1.0")
            with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, dict):
                    for key in ["generation", "best_brier", "population_size",
                                "current_brier", "iteration", "status"]:
                        if key in data:
                            result[key] = data[key]
        except Exception:
            pass
    return (label, result)


def probe_svc(label: str, url: str) -> tuple:
    """Probe a service URL. Returns (label, result_dict)."""
    return (label, probe_url(url))


def get_vm_metrics() -> dict:
    """Collect VM system metrics."""
    m = {}

    # CPU (short sample)
    try:
        with open("/proc/stat") as f:
            l1 = f.readline()
        time.sleep(CPU_SAMPLE_SEC)
        with open("/proc/stat") as f:
            l2 = f.readline()
        v1 = [int(x) for x in l1.split()[1:]]
        v2 = [int(x) for x in l2.split()[1:]]
        m["cpu_pct"] = round(100.0 * (1.0 - (v2[3] - v1[3]) / max(sum(v2) - sum(v1), 1)), 1)
    except Exception:
        m["cpu_pct"] = -1

    # RAM
    try:
        with open("/proc/meminfo") as f:
            mi = {}
            for line in f:
                p = line.split()
                if len(p) >= 2:
                    mi[p[0].rstrip(":")] = int(p[1])
        total = mi.get("MemTotal", 0)
        avail = mi.get("MemAvailable", 0)
        used = total - avail
        m["ram_total_mb"] = round(total / 1024, 1)
        m["ram_used_mb"] = round(used / 1024, 1)
        m["ram_pct"] = round(100.0 * used / max(total, 1), 1)
    except Exception:
        m["ram_pct"] = -1

    # Disk
    try:
        u = shutil.disk_usage("/")
        m["disk_total_gb"] = round(u.total / (1024**3), 1)
        m["disk_used_gb"] = round(u.used / (1024**3), 1)
        m["disk_free_gb"] = round(u.free / (1024**3), 1)
        m["disk_pct"] = round(100.0 * u.used / max(u.total, 1), 1)
    except Exception:
        m["disk_pct"] = -1

    # Load
    try:
        l1, l5, l15 = os.getloadavg()
        m["load_1m"] = round(l1, 2)
        m["load_5m"] = round(l5, 2)
        m["load_15m"] = round(l15, 2)
    except Exception:
        pass

    # Uptime
    try:
        with open("/proc/uptime") as f:
            m["uptime_hours"] = round(float(f.readline().split()[0]) / 3600, 1)
    except Exception:
        pass

    return m


# ---------- parallel probing ----------------------------------------------

def probe_all() -> dict:
    """Probe all endpoints in parallel. Returns categorized results."""
    nba = {}
    pol = {}
    council = {}
    svc = {}
    gpu = {}

    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for label, url in NBA_SPACES.items():
            futures[pool.submit(probe_hf, label, url)] = ("nba", label)
        for label, url in POLITICAL_SPACES.items():
            futures[pool.submit(probe_hf, label, url)] = ("pol", label)
        for label, url in COUNCIL_SPACES.items():
            futures[pool.submit(probe_hf, label, url)] = ("council", label)
        for label, url in SERVICES.items():
            futures[pool.submit(probe_svc, label, url)] = ("svc", label)
        for label, url in GPU_PLATFORMS.items():
            futures[pool.submit(probe_svc, label, url)] = ("gpu", label)

        buckets = {"nba": nba, "pol": pol, "council": council,
                   "svc": svc, "gpu": gpu}

        for future in as_completed(futures, timeout=60):
            cat, fallback_label = futures[future]
            try:
                label, result = future.result(timeout=10)
            except Exception as e:
                label = fallback_label
                result = {"status": 0, "latency_ms": 0, "ok": False,
                          "error": f"thread error: {str(e)[:60]}"}

            buckets[cat][label] = result

    return buckets


# ---------- CSV logging (always works, no deps) ---------------------------

def log_metrics_csv(flat_metrics: dict, step: int):
    """Append a row to metrics.csv. Create header if file is new."""
    file_exists = METRICS_CSV.exists() and METRICS_CSV.stat().st_size > 0
    keys = sorted(flat_metrics.keys())

    with open(METRICS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["step"] + keys)
        if not file_exists:
            writer.writeheader()
        row = {"step": step}
        row.update(flat_metrics)
        writer.writerow(row)


# ---------- DagsHub logging (lazy import) ---------------------------------

def log_to_dagshub(flat_metrics: dict, step: int):
    """Try to log to DagsHub. Returns True on success."""
    token = os.environ.get("DAGSHUB_TOKEN", "")
    if not token:
        return False

    try:
        import dagshub
        dagshub.auth.add_app_token(token)
        dagshub.init(
            repo_name=DAGSHUB_REPO,
            repo_owner=DAGSHUB_OWNER,
            mlflow=False,
        )
        logger = dagshub.DAGsHubLogger(
            metrics_path=str(METRICS_CSV),
            hparams_path=str(STATUS_DIR / "params.yml"),
            should_log_hparams=True,
            eager_logging=True,
        )
        logger.log_hyperparams({
            "monitor_version": "1.1",
            "total_endpoints": (len(NBA_SPACES) + len(POLITICAL_SPACES)
                                + len(COUNCIL_SPACES) + len(SERVICES)
                                + len(GPU_PLATFORMS)),
        })
        logger.log_metrics(flat_metrics, step_num=step)
        logger.save()
        logger.close()
        print(f"[dagshub] Remote logged {len(flat_metrics)} metrics")
        return True
    except Exception as e:
        print(f"[dagshub] Remote logging failed: {e}")
        return False


# ---------- main ----------------------------------------------------------

def run_monitor():
    """Run full monitoring sweep."""
    wall_start = time.time()
    ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    step_num = int(ts.timestamp())

    print(f"=== Nomos42 Monitor -- {ts_str} ===")

    # Phase 1: Probe all endpoints in parallel + VM metrics
    total_endpoints = (len(NBA_SPACES) + len(POLITICAL_SPACES) + len(COUNCIL_SPACES)
                       + len(SERVICES) + len(GPU_PLATFORMS))
    print(f"\n[Probing {total_endpoints} endpoints...]")
    probes = probe_all()
    vm = get_vm_metrics()

    probe_time = round(time.time() - wall_start, 1)
    print(f"[Probes done in {probe_time}s]")

    # Phase 2: Build results + flat metrics
    results = {
        "timestamp": ts_str,
        "nba_spaces": probes["nba"],
        "political_spaces": probes["pol"],
        "council_spaces": probes["council"],
        "services": probes["svc"],
        "gpu_platforms": probes["gpu"],
        "vm": vm,
        "summary": {},
    }
    flat = {}

    def print_group(title, data, prefix):
        up = 0
        print(f"\n[{title}]")
        for label in sorted(data.keys()):
            s = data[label]
            tag = "OK" if s["ok"] else "DOWN"
            extras = ""
            for k in ("generation", "best_brier"):
                if k in s:
                    extras += f" {k}={s[k]}"
            print(f"  {label}: {s['status']} ({tag}) {s['latency_ms']}ms{extras}")
            flat[f"{prefix}_{label}_status"] = s["status"]
            flat[f"{prefix}_{label}_latency_ms"] = s["latency_ms"]
            flat[f"{prefix}_{label}_ok"] = 1 if s["ok"] else 0
            for k in ("generation", "best_brier"):
                if k in s:
                    flat[f"{prefix}_{label}_{k}"] = s[k]
            if s["ok"]:
                up += 1
        return up

    nba_up = print_group("NBA Evolution Islands", probes["nba"], "nba")
    pol_up = print_group("Political Alpha Islands", probes["pol"], "pol")
    council_up = print_group("Department Councils", probes["council"], "council")
    svc_up = print_group("Services", probes["svc"], "svc")
    gpu_up = print_group("GPU Platforms (multi-account)", probes["gpu"], "gpu")

    # VM
    print("\n[VM]")
    for k, v in vm.items():
        flat[f"vm_{k}"] = v
        print(f"  {k}: {v}")

    # Summary
    total_spaces = len(NBA_SPACES) + len(POLITICAL_SPACES) + len(COUNCIL_SPACES)
    total_up = nba_up + pol_up + council_up
    total_svc = len(SERVICES)

    total_gpu = len(GPU_PLATFORMS)
    overall_up = total_up + svc_up + gpu_up
    overall_total = total_spaces + total_svc + total_gpu

    summary = {
        "nba_up": nba_up, "nba_total": len(NBA_SPACES),
        "political_up": pol_up, "political_total": len(POLITICAL_SPACES),
        "council_up": council_up, "council_total": len(COUNCIL_SPACES),
        "services_up": svc_up, "services_total": total_svc,
        "gpu_up": gpu_up, "gpu_total": total_gpu,
        "spaces_up": total_up, "spaces_total": total_spaces,
        "uptime_pct": round(100.0 * overall_up / max(overall_total, 1), 1),
        "vm_cpu_pct": vm.get("cpu_pct", -1),
        "vm_ram_pct": vm.get("ram_pct", -1),
        "vm_disk_pct": vm.get("disk_pct", -1),
        "health": (
            "GREEN" if total_up >= total_spaces * 0.8 and svc_up >= 1
            else "YELLOW" if total_up >= total_spaces * 0.5
            else "RED"
        ),
    }
    results["summary"] = summary
    flat["spaces_up"] = total_up
    flat["spaces_total"] = total_spaces
    flat["uptime_pct"] = summary["uptime_pct"]

    print(f"\n[Summary]")
    print(f"  NBA: {nba_up}/{len(NBA_SPACES)} | Political: {pol_up}/{len(POLITICAL_SPACES)} | "
          f"Councils: {council_up}/{len(COUNCIL_SPACES)} | Services: {svc_up}/{total_svc} | "
          f"GPU: {gpu_up}/{total_gpu}")
    print(f"  Overall: {overall_up}/{overall_total} ({summary['uptime_pct']}%)")
    print(f"  Health: {summary['health']}")
    print(f"  VM: CPU {vm.get('cpu_pct', '?')}% | RAM {vm.get('ram_pct', '?')}% | Disk {vm.get('disk_pct', '?')}%")

    # Phase 3: Persist locally (always)
    STATUS_FILE.write_text(json.dumps(results, indent=2, default=str))
    log_metrics_csv(flat, step_num)
    print(f"\n[local] JSON: {STATUS_FILE}")
    print(f"[local] CSV:  {METRICS_CSV}")

    # Timestamped history
    history_file = HISTORY_DIR / f"monitor-{ts.strftime('%Y-%m-%d_%H%M')}.json"
    history_file.write_text(json.dumps(results, indent=2, default=str))

    # Prune (keep 48 = 24h)
    hfiles = sorted(HISTORY_DIR.glob("monitor-*.json"))
    if len(hfiles) > 48:
        for old in hfiles[:-48]:
            old.unlink()
        print(f"[local] Pruned {len(hfiles) - 48} old history files")

    # Phase 4: DagsHub remote logging (lazy, optional, ~14s import)
    token = os.environ.get("DAGSHUB_TOKEN", "")
    if token:
        print("\n[dagshub] DAGSHUB_TOKEN found, attempting remote logging...")
        dagshub_ok = log_to_dagshub(flat, step_num)
        results["dagshub_connected"] = dagshub_ok
    else:
        print("\n[dagshub] No DAGSHUB_TOKEN. Set it in .env.local for remote logging.")
        results["dagshub_connected"] = False

    elapsed = round(time.time() - wall_start, 1)
    print(f"\n=== Monitor complete ({elapsed}s) ===")
    return results


if __name__ == "__main__":
    run_monitor()
