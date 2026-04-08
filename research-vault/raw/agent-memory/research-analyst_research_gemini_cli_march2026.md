---
name: Gemini CLI Research March 2026
description: Practical findings on running Gemini CLI as autonomous agent on HF Spaces and cloud platforms — authentication, Docker, free tier limits, vs Claude Code
type: project
---

## Gemini CLI as Autonomous Agent Brain — Practical Findings (March 2026)

**What it is:** Open-source AI agent from Google (`npm install -g @google/gemini-cli`), analogous to Claude Code. Runs in terminal, has file/shell/web tools, supports MCP servers, has headless scripting mode.

## Authentication for Headless Use

**Best option for free tier:** Google account OAuth (1,000 req/day, 60 req/min, Gemini Flash model)
- Problem: OAuth requires browser on first login — NOT headless-friendly out of the box
- Workaround: authenticate interactively once, tokens persist on disk; then run headless
- Server fix: curl-based callback workaround documented at community.latenode.com

**Pure headless (no browser ever):** Gemini API key via GEMINI_API_KEY env var
- Only 250 req/day on free tier, 10 req/min
- Limitation: Flash model only (not Pro), no Google Search grounding on free

**Enterprise headless:** Vertex AI service account via GOOGLE_APPLICATION_CREDENTIALS
- Requires paid GCP project

## Free Tier Limits (as of March 2026)

| Auth method | Daily limit | RPM | Model |
|---|---|---|---|
| Google account | 1,000 req/day | 60 | Flash |
| API key (free) | 250 req/day | 10 | Flash |
| Vertex AI Express | 90-day trial | varies | Pro |

**Important:** Dec 2025 Google slashed free API limits by 50-80%. Gemini 2.5 Pro on paid tier dropped from 10k to 300 req/day.

## HuggingFace Spaces Deployment

**Verdict: Technically feasible but with friction.**

Dockerfile configuration:
```dockerfile
FROM node:20-slim
RUN npm install -g @google/gemini-cli
ENV NO_COLOR=true
ENV GEMINI_API_KEY=your_key_here
ENTRYPOINT ["gemini", "--non-interactive"]
```

Key issue: 1,000 req/day Google account tier requires pre-cached OAuth tokens — need to bake them into Docker image or mount as volume. Not clean for HF Spaces.

Cleaner path: use GEMINI_API_KEY as HF Space secret (250 req/day limit, Flash only).

HuggingFace MCP integration: Gemini CLI supports HF MCP server at `https://huggingface.co/mcp` natively — can query Hub, upload models, manage datasets from within agent.

## Headless Mode Flags

```bash
# Basic headless
gemini -p "Your prompt here" --output-format json

# Pipe input
cat file.py | gemini -p "Analyze this" --output-format json

# Auto-approve actions (YOLO mode)
gemini -p "Do task" --yolo

# Non-interactive mode
gemini --non-interactive -p "..."
```

Plan Mode (v0.34.0, March 2026): enabled by default, breaks complex tasks systematically.

## Modal.com / Lightning.ai

No specific Gemini CLI integrations documented for Modal or Lightning.ai. Google Cloud Run is the native serverless target (MCP server for Cloud Run deployment exists). Modal and Lightning would work since both support Docker/arbitrary Python — just `npm install gemini-cli` in the container.

## Gemini CLI vs Claude Code for Our Use Case

| Dimension | Gemini CLI | Claude Code |
|---|---|---|
| Autonomy | Good (Plan Mode) | Excellent (Agent Teams) |
| Free calls/day | 1,000 (Flash, Google acct) | N/A — per-token billing |
| Headless | Yes (with API key) | Yes (remote triggers) |
| Multi-agent | Via ADK integration | Agent Teams (native) |
| Complex tasks | Needs nudging | More autonomous |
| Cost for complex run | Sometimes higher (fragmented) | Predictable |
| MCP support | Native | Native |
| HF integration | Via MCP server | No native HF MCP |

## Practical Verdict for Nomos42

**Can we use it on HF Spaces?** Yes, with caveats:
- Free tier: 250 req/day via API key (Flash model) — enough for light research tasks
- 1,000 req/day requires Google OAuth tokens baked in — messy
- Flash model is capable for web search + summarization but not complex reasoning

**Best use case:** Supplementary research agent running on VM or Modal (not HF Spaces where CPU-only is a constraint anyway since Gemini CLI is CPU-light). Schedule as cron job with GEMINI_API_KEY env var.

**Why:** Claude Code is primary brain (Sonnet 4.6). Gemini CLI could serve as a second free web-search agent for research cycles, parallel to Claude Code, if we need to conserve Claude API budget. The HuggingFace MCP integration is a unique capability Claude Code lacks natively.

**Not recommended:** Running Gemini CLI as primary orchestrator — it needs more manual nudging than Claude Code for complex multi-step tasks.
