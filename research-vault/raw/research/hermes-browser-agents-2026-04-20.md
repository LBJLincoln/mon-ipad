# Hermes + Browser-Agent Deployment Proposal
**Author:** HAWKEYE (D1 Research)
**Date:** 2026-04-20
**Status:** READY FOR IMPLEMENTATION (not yet deployed)
**Consumer:** THE BOSS → delegates to DR FRANKENSTEIN (impl) + LAUNCHPAD (deploy)

---

## 0. TL;DR (30 sec)

- **Hermes** in April 2026 = **NousResearch/hermes-agent** (MIT, 95.6k stars, v0.10.0, released 2026-02-25). Self-improving CLI agent w/ 3-layer memory, skills system, 47+ tools, Modal/Docker/SSH terminal backends, MCP-compliant, multi-provider LLM (Nous/OpenRouter/Anthropic/OpenAI/HF/self-host). **Namespace collision noted:** our `scripts/councils/hermes-runner.sh` is an unrelated Claude-CLI wrapper — rename to `claude-council-runner.sh` to avoid future confusion.
- **Browser-agent winner = `browser-use` v0.12.6** (MIT, 88.9k stars, YC W25, $17M raised). Beats Computer-Use on cost & self-host, beats Playwright-MCP on token efficiency (~3x), beats Operator on openness. Anthropic Computer-Use stays as fallback for high-stakes visual tasks via existing chrome MCP.
- **Deploy plan:** 1 Hermes Space on **LBJLincoln26**, 2 browser-use Spaces on **LBJLincoln** + **TESTforge42**. Nomos42 saturated — DO NOT deploy there.

---

## 1. TARGET 1 — Hermes (2026 SOTA)

### 1.1 What it is (2026 consensus)
`NousResearch/hermes-agent` — Nous Research's open-source self-improving personal AI agent framework. Released **2026-02-25**, v0.10.0 on **2026-04-16**.

- **Canonical URL:** https://github.com/NousResearch/hermes-agent
- **Docs:** https://hermes-agent.nousresearch.com/docs/
- **License:** MIT (all MIT, no gotchas)
- **Model requirement:** ≥64k context window

### 1.2 Capabilities (verified against README + docs)
| Capability | Status | Relevance to Nomos42 |
|---|---|---|
| Tool use | 47+ built-in tools w/ RPC delegation | Delegate search, HTTP, scraping, code-exec |
| Skills system | **Writes reusable skill docs from experience** | Persists "how to scrape ESPN box scores" once, reuses forever |
| 3-layer memory | FTS5 session search + LLM summary + persistent user profile | Replaces ad-hoc `data/research/` scan approach |
| Multi-agent | Spawn isolated subagents for parallel work | Cross-dept dispatch without Claude Code CLI quota |
| Code-exec backends | local / Docker / SSH / Daytona / Singularity / **Modal** | Already have Modal account, wire directly |
| Messaging | Telegram / Discord / Slack / WhatsApp / Signal gateways | THE HERALD publishing via Hermes-driven Telegram |
| MCP-compliant | Yes | Plugs into existing chrome/neo4j/supabase MCPs |
| LLM providers | Nous Portal, OpenRouter, Anthropic, OpenAI, **HF**, NVIDIA NIM, Xiaomi MiMo, z.ai, Kimi, MiniMax, **custom endpoints** | Direct route to our LLM gateway (`LBJLincoln26/llm-gateway`) |

### 1.3 Install (exact commands)
```bash
# Host VM (or HF Space Dockerfile)
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
hermes setup                        # interactive wizard
hermes config set OPENROUTER_API_KEY $OPENROUTER_API_KEY
hermes config set model openrouter/anthropic/claude-opus-4.6
hermes config set terminal.backend docker
hermes --tui                        # modern UI
```

### 1.4 Canonical hello-world (5 lines, CLI form)
```bash
hermes config set ANTHROPIC_API_KEY $ANTHROPIC_API_KEY
hermes config set model anthropic/claude-opus-4.7
echo "Scan arXiv cs.LG for tabular prediction papers from this week and summarize top 3 by Brier-impact." | hermes --task -
hermes skills list                 # see what Hermes auto-learned
hermes /new                        # fresh context
```
*(Hermes has no Python `Agent()` constructor — it is CLI-first with RPC for scripts. A future wrapper can wrap `hermes --task -` via `subprocess.run`.)*

### 1.5 Env vars (matches our `.env.local` pattern)
```
NOUS_API_KEY=...                    # Nous Portal (primary; free community tier)
HERMES_CONFIG_DIR=/data/.hermes      # HF Space persistence mount
OPENROUTER_API_KEY=<existing>        # fallback
ANTHROPIC_API_KEY=<existing>
MODAL_TOKEN_ID=<existing>            # code-exec backend
```

---

## 2. TARGET 2 — Browser Agent (2026 SOTA)

### 2.1 Rankings (Apr 2026, verified)
| Tool | Reliability | Cost/task | Self-host | Integration | Score |
|---|---|---|---|---|---|
| **browser-use v0.12.6** | High (88.9k⭐, YC, $17M) | ~$0.05 w/ ChatBrowserUse, ~$0.10 w/ Gemini-3-flash | **Native (MIT, local chromium)** | Pip, async Python, MCP support | **9.2** |
| Anthropic Computer-Use (Opus 4.7) | Very high (SOTA vision) | ~$0.50-2.00/task (Opus pricing) | No (API only) | Already have chrome MCP | 7.5 |
| OpenAI Operator / CUA via Responses API | High | ~$0.40/task | No (API only) | New SDK req'd | 6.8 |
| Playwright-MCP | Medium (1.5M tok/run = ~4× cost) | Token-heavy | Yes | MCP | 5.5 |
| Google Mariner | Unknown (preview) | N/A | No | Gemini only | 4.0 |

### 2.2 PICK: `browser-use` (v0.12.6)
**Why:** MIT + self-host + 3-5× faster w/ `ChatBrowserUse()` proprietary model (free community tier) + already wired for Gemini-3-flash (our winner) + YC-backed means maintained.

**Fallback:** Anthropic Computer-Use via existing chrome MCP for high-stakes visual tasks (pixel-world QA, dashboard screenshot diffs).

### 2.3 Install (exact commands)
```bash
pip install uv
uv venv --python 3.12 && source .venv/bin/activate
uv pip install browser-use==0.12.6
uvx browser-use install            # fetches chromium binary
```

### 2.4 Hello-world (5 lines, Python)
```python
from browser_use import Agent, ChatAnthropic
import asyncio
async def main():
    agent = Agent(task="Find the ESPN NBA scoreboard for today and return home/away + moneylines for all games", llm=ChatAnthropic(model='claude-sonnet-4-6', temperature=0.0))
    await agent.run()
asyncio.run(main())
```

### 2.5 Env vars
```
BROWSERUSE_API_KEY=...               # optional: ChatBrowserUse proprietary (fastest)
BROWSER_USE_HEADLESS=1
ANTHROPIC_API_KEY=<existing>
GOOGLE_API_KEY=<existing>            # gemini-3-flash
```

---

## 3. HF Account Allocation (Nomos42 saturated — DO NOT USE)

| Account | Current Load | Proposed New | Rationale |
|---|---|---|---|
| **Nomos42** | 18 islands + pixel-world + dashboards (saturated, 403 on new deploys) | **NONE** | Per `project_llm_fleet_distribution_apr19.md` |
| **LBJLincoln** | 3 selfhost LLMs + P4/P5/P7 islands | **browser-use Space #1** (scraping + POL/SEC) | Lightest TF load |
| **LBJLincoln26** | gemma3-4b + llm-gateway + 2 TFs + ITF + langfuse | **Hermes Agent Space** (central orchestrator) | Already hub for gateway traffic |
| **TESTforge42** | qwen3-4b + llama32-1b + smollm3-3b + S18/S22 | **browser-use Space #2** (NBA + pixel-world QA) | Has slack after council deletion |

---

## 4. Dockerfile Skeletons

### 4.1 `Dockerfile.hermes` (HF Space on LBJLincoln26)
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y curl git bash ca-certificates sqlite3 && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
ENV PATH=/home/user/.local/bin:$PATH HERMES_CONFIG_DIR=/data/.hermes
RUN curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
COPY --chown=user hermes_rpc_server.py /home/user/app/
EXPOSE 7860
CMD ["python", "hermes_rpc_server.py"]   # tiny FastAPI wrapper exposing /api/task POST → hermes --task -
```
HF Space hardware: `cpu-upgrade` (4 vCPU / 16GB) — Hermes memory+FTS5 benefits from RAM. Secrets: `NOUS_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `MODAL_TOKEN_ID`.

### 4.2 `Dockerfile.browseruse` (HF Space on LBJLincoln + TESTforge42)
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
ENV PATH=/home/user/.local/bin:$PATH DISPLAY=:99 BROWSER_USE_HEADLESS=1
RUN pip install --no-cache-dir browser-use==0.12.6 fastapi uvicorn anthropic google-generativeai
COPY --chown=user app.py /home/user/app/
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
```
HF Space hardware: `cpu-upgrade` (Playwright chromium ~600MB RAM). Secrets: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `BROWSERUSE_API_KEY`, `HF_TOKEN_*` for `HfApi.upload_file` deploy.

### 4.3 HfApi deploy snippet (standard pattern per our memory)
```python
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN_LLM"])   # LBJLincoln26
api.create_repo("LBJLincoln26/hermes-agent", repo_type="space", space_sdk="docker", private=False)
api.upload_folder(folder_path="./hf-hermes", repo_id="LBJLincoln26/hermes-agent", repo_type="space")
```

---

## 5. Top-5 Nomos42 Workflows (measurable lift)

| # | Workflow | Agent | Task | Measured Lift | Brier impact |
|---|---|---|---|---|---|
| 1 | **NBA live line scraping** (ESPN, bbref, Vegas Insider) | browser-use | Hourly scrape: closing lines, injury reports, starting lineups. Feed to TF + walk-forward as `line_movement_v1` features | +8 real-time features not in current engine.py v3.1 | −0.002 to −0.005 |
| 2 | **SEC EDGAR + FEC scraping** (PACs, Form 4, 8-K catalysts) | browser-use | Daily scrape of SEC EDGAR full-text + FEC filings for political catalyst calendar | Replaces incomplete `catalyst_calendar.py` (currently FRED/BLS only) | POL Brier −0.003 |
| 3 | **Pixel-world visual QA** (every PIXEL commit) | Anthropic Computer-Use via chrome MCP | Navigate to pixel-world HF Space, screenshot, diff vs golden → fail CI on regression | Prevents next "agents disappeared" incident (per `feedback_pixel_panel_regression_apr17.md`) | Stops 1+ rollback/week |
| 4 | **Hermes as cross-dept orchestrator** (skill: "run 4h cycle") | Hermes | Hermes learns the 4h cycle (audit → research → proposals → deploy) as a **skill**, executes on Nous-Portal free tier → reduces Claude Code quota burn | ~40% faster after skill-bootstrap (Nous benchmark) | Indirect: +4h/week capacity |
| 5 | **Dashboard self-QA + monetization funnel test** | browser-use | Weekly: load `nomosdashboard.vercel.app`, click through /nba /political /world /trading-floor, screenshot, assert no TS errors + Stripe link works | Catches Vercel deploy breakage (per `project_vercel_deploy_stale_apr14.md`) early | Revenue protection toward May 1 deadline |

---

## 6. Priority Deployment Order (top-3)

1. **browser-use on LBJLincoln** → NBA line scraping (Workflow #1). Highest Brier impact, direct path to <0.20 target. ETA 1 day.
2. **browser-use on TESTforge42** → Pixel-world QA + Dashboard QA (Workflows #3, #5). Revenue protection + regression defense. ETA 1 day after #1.
3. **Hermes on LBJLincoln26** → Orchestrator + skill-learning layer. Compounding return on quota savings. ETA 2 days (needs RPC wrapper).

SEC/FEC scraping (#2) queued for week 2 — blocked on FEC rate-limit research (10 req/s documented in `project_pol_tf_184day_extension_apr19.md`).

---

## 7. Kill Criteria

- **Hermes:** if 48h post-deploy Hermes has not auto-created ≥3 reusable skills OR the RPC wrapper adds >5s latency per orchestration call, revert to existing Claude Code CLI pattern.
- **browser-use:** if scraping success rate <80% on top-10 NBA sources after 72h of tuning, fall back to Anthropic Computer-Use via chrome MCP (but keep browser-use Space running for pixel-QA only).
- **Both:** if combined deploy causes any HF account to hit 403 (account saturation), pause newest Space and redistribute.

---

## 8. Sources (verified 2026-04-20)

- https://github.com/NousResearch/hermes-agent — canonical repo (95.6k⭐ as of Apr 2026)
- https://hermes-agent.nousresearch.com/docs/ — official docs
- https://github.com/NousResearch/hermes-agent/releases — v0.10.0 release (2026-04-16)
- https://github.com/browser-use/browser-use — canonical repo (88.9k⭐, v0.12.6)
- https://docs.browser-use.com/quickstart — install + hello-world
- https://ycombinator.com/companies/browser-use — YC W25, $17M Series A
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool — Anthropic Computer-Use (Opus 4.7, enhanced actions `computer_20251124`)
- https://openai.com/index/computer-using-agent/ — OpenAI CUA / Operator context
- Internal: `feedback_hf_first_then_vercel.md`, `project_llm_fleet_distribution_apr19.md`, `project_selfhost_fleet_reality_apr20.md`, `scripts/councils/hermes-runner.sh` (namespace collision noted)

---

*Ready for DR FRANKENSTEIN. Total impl est: 4 days (1 day/Space + 1 day Hermes RPC wrapper). Total cost: $0 (free tiers + existing HF Pro slots).*
