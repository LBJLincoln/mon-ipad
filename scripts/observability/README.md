# LLM Observability for Nomos42

**Cycle 14 Tier 1 (Apr 7 2026)**. OpenLIT client + dual sinks (sqlite-otel
on VM, Phoenix on brother's laptop). No Docker, no Postgres, no SaaS.

## The problem

Trading Floor v5 makes ~200 LLM calls per game night across 5+ providers
(Groq, OpenRouter, Cohere, Cerebras, HF Router, OpenAI, xAI, Google).
Before this shipped, every call was invisible: if Groq started rate-limiting
or Qwen returned garbage JSON, we only noticed when end-of-night PnL looked
weird — sometimes days later. Zero traces, zero token accounting, zero
per-model latency.

## The architecture

```
  scripts/arena/trading-floor-v5.py
           │
           │ openlit.init() monkey-patches every OpenAI-compat client
           │ at import time. Each call emits an OTLP span.
           ▼
  http://localhost:4318/v1/traces   (set via OTEL_EXPORTER_OTLP_ENDPOINT)
           │
           ▼
  sqlite-otel binary (Go, ~30 MB RAM)
  writes to ~/data/traces.db
           │
           ▼
  cron queries for 429s and pipes to @Nomos42Bot
```

**Optional second sink** (richer UI, runs on brother's laptop via Tailscale):

```
  traders POST to http://<laptop-tailnet>:6006/v1/traces
           ▼
  Phoenix (pip install arize-phoenix, ~2 GB RAM — fits on laptop, not VM)
  UI at http://<laptop-tailnet>:6006
  SQLite default, no Postgres
```

Both sinks can run simultaneously by setting the OTLP endpoint to a local
proxy that forks spans — the simplest pattern is to run sqlite-otel on the
VM and **also** set Phoenix's URL in the env so OpenLIT tees to both. In
practice we usually pick one at a time; sqlite-otel is always on (it's the
cron-readable primary), and Phoenix gets started when we actively want the
UI.

## Files

| File | Runs on | Purpose |
|---|---|---|
| `start-otel-sink.sh` | VM | Start the sqlite-otel binary as a background process, idempotent |
| `laptop-phoenix-bootstrap.sh` | **laptop** | Install + start Phoenix on :6006, bound to 0.0.0.0 so Tailscale can reach it |
| `README.md` | — | This file |

## First-time bootstrap

### On the VM (sqlite-otel, always-on)

```bash
mkdir -p ~/.local/bin
curl -L https://github.com/RedShiftVelocity/sqlite-otel/releases/latest/download/sqlite-otel-linux-amd64 \
    -o ~/.local/bin/sqlite-otel
chmod +x ~/.local/bin/sqlite-otel
bash scripts/observability/start-otel-sink.sh
```

Add to cron to auto-restart on reboot/crash:

```
@reboot bash /home/termius/mon-ipad/scripts/observability/start-otel-sink.sh
*/15 * * * * pgrep -f sqlite-otel > /dev/null || bash /home/termius/mon-ipad/scripts/observability/start-otel-sink.sh
```

### On the laptop (Phoenix, on-demand)

```bash
# Copy the bootstrap script to the laptop via Tailscale/scp
# Then on the laptop:
bash laptop-phoenix-bootstrap.sh install    # one-time
bash laptop-phoenix-bootstrap.sh start      # launches :6006
```

Grab the laptop's Tailscale IP with `tailscale ip -4`. On the VM, point
OpenLIT at Phoenix:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://<laptop-tailnet-ip>:6006/v1/traces
```

Then run traders; open `http://<laptop-tailnet-ip>:6006` in a browser
(or port-forward over Tailscale to the iPad).

## Queries you'll actually run

```sql
-- Model usage + latency distribution (last 24h)
SELECT
    json_extract(attributes, '$.gen_ai.request.model') AS model,
    COUNT(*) AS calls,
    AVG(end_time - start_time) / 1e6 AS avg_ms,
    SUM(CAST(json_extract(attributes, '$.gen_ai.usage.output_tokens') AS INTEGER)) AS out_tokens
FROM spans
WHERE start_time > (strftime('%s','now') - 86400) * 1000000000
GROUP BY model
ORDER BY calls DESC;

-- Rate-limit alarms (any 429 in last 30 min)
SELECT name, status_code, status_message, start_time
FROM spans
WHERE status_code = 'ERROR'
  AND status_message LIKE '%429%'
  AND start_time > (strftime('%s','now') - 1800) * 1000000000;
```

The second query is what the cron alert wires to `@Nomos42Bot`.

## Why not other tools

| Tool | Why rejected |
|---|---|
| Arize Phoenix on VM | Self-host needs 2 GB RAM, VM has 969 MB. Runs fine on laptop. |
| Langfuse | Requires Postgres + Docker. Adds a stateful service. |
| Helicone | SaaS only. |
| OpenObserve | Rust binary, designed for multi-tenant cloud. Heavier than sqlite-otel. |
| Stockyard | Acts as a proxy in the request path — adds latency + failure point. |
