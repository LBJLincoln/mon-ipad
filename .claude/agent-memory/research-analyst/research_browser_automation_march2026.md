---
name: Browser Automation for HF Spaces — March 2026 Research
description: Headless browser options for autonomous AI agents on HuggingFace Spaces: Playwright/Docker, browser-as-a-service, LLM+browser frameworks, MCP tools
type: reference
---

# Headless Browser Automation on HF Spaces (March 2026)

## HF Space Hardware (Free Tier)
- RAM: 16 GB, CPU: 2 cores, Disk: 50 GB (ephemeral, not persistent)
- Persistent storage: paid upgrade only
- Docker Spaces: fully supported, user controls Dockerfile

## Approach 1: Playwright in Docker Space (self-hosted, zero cost)
- Works: Docker Space on HF, Dockerfile uses official Playwright image
- Official image: `mcr.microsoft.com/playwright:v1.58.2-noble`
- Minimal Dockerfile:
  ```dockerfile
  FROM mcr.microsoft.com/playwright:v1.58.2-noble
  RUN pip install playwright
  RUN playwright install chromium
  CMD ["python", "scraper.py"]
  ```
- Run flags needed locally: `--init --ipc=host`
- On HF Spaces: no `--ipc=host` flag control, but Docker image handles it
- Alpine NOT supported (musl vs glibc conflict)
- Known issue: Playwright binary missing if using standard Gradio SDK (not Docker)
- Fix: always use Docker SDK on HF, not Gradio SDK, when Playwright is needed

## Approach 2: Playwright vs Puppeteer vs Selenium (2026 verdict)
- **Playwright** = winner for containers. WebSocket CDP, fastest, official Docker image, multi-browser, Python+JS
- **Puppeteer** = Chrome-only, JS-only, no official Docker image. Use only if Node.js-primary stack
- **Selenium** = slowest (WebDriver overhead), but most language support. Legacy choice only
- For AI agent scraping on HF Space: Playwright + Python is the clear pick

## Approach 3: Browser-as-a-Service (BaaS) — Free Tiers 2026
| Service | Free Tier | Notes |
|---------|-----------|-------|
| Steel.dev | 100 browser-hours/month | Open source, self-hostable Docker image, best for AI agents |
| Browserbase | 1 browser-hour/month | Very limited, optimized for Playwright sessions |
| Browserless | 1,000 units/month | Cloud Chrome, CAPTCHA solving, REST + WS API |
| ScrapingBee | 1,000 API credits | No CC required, simpler API |
| Scrapfly | $9/mo entry | No true free tier |

- **Steel.dev** is the strongest option: open-source, Docker self-host, 100h/mo free, Python SDK, built for AI agents. GitHub: steel-dev/steel-browser

## Approach 4: LLM Agent + Browser Frameworks
- **browser-use** (84.6k stars): Top pick. Python, Claude/Gemini/OpenAI/Ollama. Natural language tasks → browser actions. Has Dockerfile. Free if using Gemini free tier or Ollama
- **Stagehand** (21k stars): TypeScript, hybrid code+AI approach (`act()`, `extract()`, `observe()`)
- **LaVague**: Selenium-backed, older, less maintained
- **Crawl4AI**: Playwright-based crawler optimized for LLM output (clean Markdown). Lightweight, pure Python, free

## Approach 5: MCP Tools (callable remotely)
- **Firecrawl MCP**: 8 tools (scrape, crawl, search, extract, map). Rate-limited free tier. Best for structured extraction
- **Bright Data MCP**: Highest success rate (76.8% in 2026 benchmarks), anti-bot bypass, paid
- **Browserless MCP skill**: Cloud Chrome via Claude Code skill
- **Chrome DevTools MCP** (github.com/ChromeDevTools/chrome-devtools-mcp): Open source, connects to local/remote Chrome via CDP
- **Cloudflare Browser Rendering MCP**: Via Composio integration

## Recommended Architecture for Nomos42 NBA Data Scraping
1. **Primary**: Crawl4AI on HF Space Docker for simple HTML pages (no JS). Zero cost, runs in-process
2. **For JS-heavy pages**: Playwright in same Docker container (16GB RAM is plenty for 1-2 Chrome instances)
3. **Anti-bot / production**: Steel.dev cloud (100h/month free covers ~3 scrapes/hour continuously)
4. **LLM-guided navigation**: browser-use + Gemini free tier (10 req/min) when need to parse dynamic dashboards

## Implementation Note for Nomos42
- Add to existing HF Space Dockerfile: `RUN playwright install chromium --with-deps`
- NBA odds sources (Action Network, The Odds API) mostly have public APIs — prefer API over scraping when available
- Scraping use case: backup odds when API is down, referee tendencies from NBA.com, injury reports from team sites
