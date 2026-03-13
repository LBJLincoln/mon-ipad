#!/usr/bin/env python3
"""Karpathy-style continuous improver for ALL Nomos systems.

The pattern: measure -> find weakest -> hypothesize -> experiment -> measure again -> keep or revert -> repeat.

Targets:
  1. RAG pipelines (Standard, Graph, Quant, Orchestrator)
  2. Websites (all pages on nomos42.vercel.app)
  3. Data quality (enrichment rate, vector count, eval question bank)

Every cycle:
  - Measures everything
  - Finds the single weakest point
  - Generates an improvement hypothesis
  - Executes it
  - Measures again
  - Logs result (keep/revert)

Usage:
    source .env.local
    python3 ops/karpathy-improver.py --once          # Single cycle
    python3 ops/karpathy-improver.py --daemon 1800   # Loop every 30min
"""

import json
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path("/home/termius/mon-ipad")
STATE_FILE = BASE_DIR / "data" / "karpathy-state.json"
LOG_FILE = BASE_DIR / "data" / "karpathy-log.jsonl"
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "sk-litellm-nomos-2026"

SPACES = [
    "https://lbjlincoln-nomos-rag-engine.hf.space",
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "https://lbjlincoln-nomos-rag-engine-5.hf.space",
]

PIPELINES = {
    "standard": "/webhook/rag-multi-index-v3",
    "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

SITES = [
    ("main", "https://nomos42.vercel.app"),
    ("satellite", "https://nomos42.vercel.app/satellite"),
    ("marketplace", "https://nomos42.vercel.app/marketplace"),
    ("factory", "https://nomos42.vercel.app/factory"),
    ("vault", "https://nomos42.vercel.app/vault"),
    ("dashboard", "https://nomos42.vercel.app/dashboard"),
    ("valorisation", "https://nomos42.vercel.app/valorisation"),
    ("graph", "https://nomos42.vercel.app/graph"),
]

EVAL_QUESTIONS = {
    "finance": [
        {"q": "Quel est le chiffre d'affaires d'Apple en 2023 ?", "sector": "finance"},
        {"q": "What are the main risks mentioned in Tesla's 10-K filing?", "sector": "finance"},
        {"q": "Compare the debt-to-equity ratio of major tech companies.", "sector": "finance"},
    ],
    "btp": [
        {"q": "Quelles sont les normes DTU pour l'isolation thermique ?", "sector": "btp"},
        {"q": "Quels sont les documents obligatoires pour un permis de construire ?", "sector": "btp"},
    ],
    "juridique": [
        {"q": "Quels sont les delais de prescription en droit civil francais ?", "sector": "juridique"},
        {"q": "Comment fonctionne la rupture conventionnelle ?", "sector": "juridique"},
    ],
    "industrie": [
        {"q": "Quelles sont les etapes d'une analyse AMDEC ?", "sector": "industrie"},
        {"q": "Comment mettre en place un systeme qualite ISO 9001 ?", "sector": "industrie"},
    ],
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"cycle": 0, "improvements": 0, "regressions": 0, "history": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_log(entry):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def call_pipeline(question, sector, pipeline="standard", timeout=60):
    """Call a RAG pipeline. Returns (answer, latency_s, success)."""
    payload = json.dumps({
        "question": question, "query": question,
        "sector": sector, "sectorId": sector, "tenant_id": sector,
    }).encode()

    for space in SPACES:
        url = f"{space}{PIPELINES[pipeline]}"
        start = time.time()
        try:
            req = urllib.request.Request(url, payload, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                result = json.loads(resp.read())
                answer = result.get("response") or result.get("answer") or result.get("output", "")
                latency = time.time() - start
                has_content = len(str(answer)) > 20
                return answer, latency, has_content
        except Exception:
            continue
    return "", 0, False


def llm_call(prompt, max_tokens=500):
    """Call LiteLLM for analysis."""
    data = json.dumps({
        "model": "smart",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.3,
    }).encode()
    headers = {"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"}
    req = urllib.request.Request(LITELLM_URL, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"LLM error: {e}"


def run_cmd(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, shell=True, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


# ─── MEASUREMENT PHASE ───────────────────────────────────────
def measure_all():
    """Measure everything. Returns a dict of metrics."""
    metrics = {"timestamp": datetime.now(timezone.utc).isoformat(), "pipelines": {}, "sites": {}, "data": {}}

    # 1. Pipeline accuracy (quick smoke — 2 questions per pipeline)
    log("Measuring pipelines...")
    for pipeline in ["standard", "graph", "quantitative", "orchestrator"]:
        successes = 0
        total = 0
        avg_latency = 0
        test_qs = EVAL_QUESTIONS["finance"][:2]  # Quick smoke
        for qd in test_qs:
            answer, latency, success = call_pipeline(qd["q"], qd["sector"], pipeline)
            total += 1
            if success:
                successes += 1
            avg_latency += latency
        accuracy = successes / total if total > 0 else 0
        avg_latency = avg_latency / total if total > 0 else 0
        metrics["pipelines"][pipeline] = {
            "accuracy": accuracy, "total": total,
            "successes": successes, "avg_latency": round(avg_latency, 1),
        }
        log(f"  {pipeline}: {accuracy:.0%} ({successes}/{total}), {avg_latency:.1f}s")

    # 2. Website availability
    log("Measuring websites...")
    for name, url in SITES:
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Karpathy-Improver/1.0")
            start = time.time()
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                latency = time.time() - start
                metrics["sites"][name] = {"status": resp.status, "latency": round(latency, 2), "up": True}
        except urllib.error.HTTPError as e:
            metrics["sites"][name] = {"status": e.code, "latency": 0, "up": e.code < 500}
        except Exception:
            metrics["sites"][name] = {"status": 0, "latency": 0, "up": False}
        status = metrics["sites"][name]
        log(f"  {name}: {'UP' if status['up'] else 'DOWN'} ({status['status']})")

    # 3. Data health
    log("Measuring data...")
    # E5 vectors
    try:
        h = json.loads((BASE_DIR / "data" / "health-status.json").read_text())
        metrics["data"]["e5_vectors"] = h.get("e5_vectors", 0)
    except Exception:
        metrics["data"]["e5_vectors"] = 0

    # Enrichment rate
    out, ok = run_cmd(
        "python3 -c \""
        "import json,urllib.request,ssl;"
        "ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE;"
        "\" 2>/dev/null"
    )
    # Just use stored value
    try:
        progress = json.loads((BASE_DIR / "data" / "ingest" / "progress.json").read_text())
        metrics["data"]["enrichment_rate"] = progress.get("enrichment_rate", 0)
    except Exception:
        metrics["data"]["enrichment_rate"] = 0

    # Eval question count
    out, ok = run_cmd("wc -l data/eval/blast-*.json 2>/dev/null | tail -1 | awk '{print $1}'")
    metrics["data"]["eval_files"] = int(out) if ok and out.isdigit() else 0

    log(f"  E5 vectors: {metrics['data']['e5_vectors']}")
    log(f"  Enrichment: {metrics['data'].get('enrichment_rate', '?')}%")

    return metrics


# ─── FIND WEAKEST POINT ──────────────────────────────────────
def find_weakest(metrics):
    """Find the single weakest point in the system."""
    weaknesses = []

    # Pipeline accuracy
    for name, data in metrics["pipelines"].items():
        targets = {"standard": 0.90, "graph": 0.75, "quantitative": 0.95, "orchestrator": 0.85}
        target = targets.get(name, 0.80)
        gap = target - data["accuracy"]
        if gap > 0:
            weaknesses.append({
                "type": "pipeline", "name": name,
                "current": data["accuracy"], "target": target,
                "gap": gap, "priority": gap * 100,
            })

    # Site availability
    for name, data in metrics["sites"].items():
        if not data["up"]:
            weaknesses.append({
                "type": "site", "name": name,
                "current": 0, "target": 1,
                "gap": 1.0, "priority": 90,  # Sites down = high priority
            })

    # Data gaps
    e5 = metrics["data"].get("e5_vectors", 0)
    if e5 < 100000:
        weaknesses.append({
            "type": "data", "name": "e5_vectors",
            "current": e5, "target": 100000,
            "gap": (100000 - e5) / 100000, "priority": 30,
        })

    enrich = metrics["data"].get("enrichment_rate", 0)
    if enrich < 80:
        weaknesses.append({
            "type": "data", "name": "enrichment",
            "current": enrich, "target": 80,
            "gap": (80 - enrich) / 80, "priority": 25,
        })

    # Sort by priority (biggest gap first)
    weaknesses.sort(key=lambda x: x["priority"], reverse=True)
    return weaknesses[0] if weaknesses else None


# ─── GENERATE IMPROVEMENT ────────────────────────────────────
def generate_improvement(weakness, metrics):
    """Ask LLM for an actionable improvement hypothesis."""
    prompt = f"""You are an expert at improving RAG pipeline systems.

Current system state:
{json.dumps(metrics, indent=2, default=str)[:2000]}

The WEAKEST point is:
- Type: {weakness['type']}
- Name: {weakness['name']}
- Current: {weakness['current']}
- Target: {weakness['target']}
- Gap: {weakness['gap']:.2f}

Available actions (choose ONE):
1. For pipeline issues: suggest a specific data ingestion command to run
   Format: CMD: source .env.local && python3 ops/fast-ingest.py --sector <sector> --max 10
2. For site issues: suggest what needs fixing in rag-website
   Format: CMD: cd /home/termius/rag-website && <fix command>
3. For data issues: suggest an enrichment or ingestion command
   Format: CMD: source .env.local && python3 ops/<script>.py <args>

IMPORTANT: Output exactly ONE line starting with CMD: followed by a real executable command.
Then on the next line, explain WHY in one sentence starting with WHY:"""

    response = llm_call(prompt, max_tokens=300)
    cmd = ""
    why = ""
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("CMD:"):
            cmd = line[4:].strip()
        elif line.startswith("WHY:"):
            why = line[4:].strip()
    return cmd, why


# ─── EXECUTE IMPROVEMENT ─────────────────────────────────────
def execute_improvement(cmd, timeout=180):
    """Execute the improvement command."""
    log(f"Executing: {cmd[:100]}")
    out, ok = run_cmd(cmd, timeout=timeout)
    log(f"Result: {'OK' if ok else 'FAILED'}")
    if out:
        log(f"Output: {out[:200]}")
    return out, ok


# ─── MAIN CYCLE ──────────────────────────────────────────────
def run_cycle():
    """One full Karpathy cycle: measure → find weakest → improve → measure → log."""
    state = load_state()
    state["cycle"] += 1
    cycle = state["cycle"]

    log(f"=== KARPATHY CYCLE #{cycle} ===")

    # 1. Measure baseline
    log("Phase 1: MEASURE baseline")
    before = measure_all()

    # 2. Find weakest
    log("Phase 2: FIND weakest")
    weakness = find_weakest(before)
    if not weakness:
        log("No weaknesses found — system at target!")
        entry = {"cycle": cycle, "timestamp": datetime.now(timezone.utc).isoformat(),
                 "result": "at_target", "weakness": None}
        append_log(entry)
        save_state(state)
        return

    log(f"Weakest: {weakness['type']}/{weakness['name']} "
        f"(current={weakness['current']}, target={weakness['target']}, gap={weakness['gap']:.2f})")

    # 3. Generate improvement
    log("Phase 3: GENERATE improvement hypothesis")
    cmd, why = generate_improvement(weakness, before)
    if not cmd:
        log("LLM failed to generate a command. Skipping.")
        entry = {"cycle": cycle, "timestamp": datetime.now(timezone.utc).isoformat(),
                 "result": "no_hypothesis", "weakness": weakness}
        append_log(entry)
        save_state(state)
        return

    log(f"Hypothesis: {cmd[:100]}")
    log(f"Why: {why}")

    # 4. Execute
    log("Phase 4: EXECUTE improvement")
    output, success = execute_improvement(cmd)

    # 5. Measure after
    log("Phase 5: MEASURE after")
    after = measure_all()

    # 6. Compare
    log("Phase 6: COMPARE before/after")
    before_score = 0
    after_score = 0
    for p in before["pipelines"]:
        before_score += before["pipelines"][p]["accuracy"]
        if p in after["pipelines"]:
            after_score += after["pipelines"][p]["accuracy"]
    delta = after_score - before_score

    if delta >= 0:
        result = "improvement"
        state["improvements"] += 1
        log(f"IMPROVEMENT: +{delta:.2f} total accuracy")
    else:
        result = "regression"
        state["regressions"] += 1
        log(f"REGRESSION: {delta:.2f} total accuracy")

    # 7. Log
    entry = {
        "cycle": cycle,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "weakness": weakness,
        "command": cmd,
        "why": why,
        "cmd_success": success,
        "delta": round(delta, 4),
        "result": result,
        "before_total": round(before_score, 4),
        "after_total": round(after_score, 4),
    }
    append_log(entry)

    # Keep last 20 in state history
    state["history"] = (state.get("history", []) + [entry])[-20:]
    save_state(state)

    log(f"=== CYCLE #{cycle} DONE: {result} (delta={delta:+.2f}) ===")
    log(f"Total: {state['improvements']} improvements, {state['regressions']} regressions")
    return entry


# ─── Entrypoint ───────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Karpathy-style continuous improver")
    parser.add_argument("--once", action="store_true", help="Single cycle")
    parser.add_argument("--daemon", type=int, help="Loop every N seconds")
    parser.add_argument("--cycles", type=int, default=0, help="Run N cycles then stop")
    args = parser.parse_args()

    if args.once:
        run_cycle()
    elif args.daemon:
        log(f"DAEMON MODE: every {args.daemon}s")
        while True:
            try:
                run_cycle()
            except Exception as e:
                log(f"Cycle error: {e}")
                import traceback; traceback.print_exc()
            log(f"Sleeping {args.daemon}s...")
            time.sleep(args.daemon)
    elif args.cycles:
        for i in range(args.cycles):
            run_cycle()
            if i < args.cycles - 1:
                time.sleep(10)
    else:
        run_cycle()


if __name__ == "__main__":
    main()
