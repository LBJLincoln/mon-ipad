# AI Agent SDK & Framework Landscape — March 2026

> Research compiled: 2026-03-25
> Context: NBA Quant AI (Nomos42) — evaluating agent infrastructure for autonomous prediction pipeline

---

## Executive Summary

The agent SDK landscape has consolidated dramatically in early 2026. Three clear tiers have emerged:
1. **Native execution SDKs** (Claude Agent SDK, OpenAI Agents SDK) — own the tool loop
2. **Orchestration frameworks** (LangGraph, Google ADK) — graph-based coordination of multiple agents
3. **Role-based shortcuts** (CrewAI, PydanticAI) — productivity-first, less control

The biggest news: AutoGen is effectively dead (maintenance mode), CrewAI and LangGraph are both at ~45k stars, and Google ADK just hit 2.0 alpha with graph-based execution. Anthropic renamed Claude Code SDK to **Claude Agent SDK** — signaling it's no longer just for coding.

---

## 1. Claude Agent SDK (Anthropic)

**What it is:** The Claude Code SDK renamed and expanded. Powers Claude Code itself. Exposes the same agent loop, tools, and context management as a library you can call programmatically in Python and TypeScript.

**GitHub:** `anthropic-ai/claude-agent-sdk-python` — **5.7k stars**, 381 commits
**Install:** `pip install claude-agent-sdk` (Python) | `npm install @anthropic-ai/claude-agent-sdk`
**Latest:** Renamed from Claude Code SDK (breaking change: migrate via migration guide)
**Maturity:** Production-ready. Powers Claude Code in production for millions of users.

**Key Features:**
- `query()` async generator: single-function entry point for most use cases
- `ClaudeSDKClient`: bidirectional, interactive sessions with turn-by-turn control
- Built-in tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion
- **Hooks system**: PreToolUse, PostToolUse, Stop, SessionStart, SessionEnd, UserPromptSubmit — intercept/block/transform agent behavior via callbacks
- **Subagents**: spawn isolated agents with their own context, tools, and instructions; tracked via `parent_tool_use_id`
- **Sessions**: resume or fork sessions across multiple exchanges; `resume=session_id`
- **MCP integration**: native `mcp_servers={}` config for any MCP server (Playwright, Supabase, etc.)
- **Skills & slash commands**: filesystem-based capability definitions in `.claude/skills/*.md`
- In-process MCP servers (pure Python functions, no subprocess overhead)
- Supports Amazon Bedrock, Google Vertex AI, Azure AI Foundry as backend

**Multi-Agent Pattern:**
```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async for msg in query(
    prompt="Run research and market analysis in parallel",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Bash", "Agent"],
        agents={
            "research": AgentDefinition(description="NBA research", prompt="...", tools=["WebSearch"]),
            "market": AgentDefinition(description="Odds analysis", prompt="...", tools=["Bash"])
        }
    )
):
    ...
```

**NBA Quant Relevance: HIGH**
- Our entire Karpathy loop already runs on this. The Agent SDK IS our autonomous brain.
- New StopFailure hook (v0.1.50) for rate limit handling is directly actionable.
- Session resume enables multi-turn research cycles without context loss.
- In-process MCP for Supabase would eliminate subprocess overhead in research agents.

---

## 2. Google ADK (Agent Development Kit)

**What it is:** Open-source, code-first Python/TypeScript/Go/Java toolkit for building, evaluating, and deploying AI agents. Optimized for Gemini but model-agnostic via LiteLLM.

**GitHub:** `google/adk-python` — **18.6k stars**
**Install:** `pip install google-adk`
**Latest:** v1.27.4 (2026-03-24), ADK 2.0.0 Alpha (2026-03-18)
**Maturity:** Stable v1.x, 2.0 alpha available. Bi-weekly release cadence.

**Key Features:**
- **ADK 2.0 Alpha — Graph-based execution engine**: deterministic flows with routing, fan-out/fan-in, loops, retry, state management, dynamic nodes, human-in-the-loop, nested workflows
- **Task API**: structured agent-to-agent delegation (multi-turn, single-turn controlled output, mixed patterns)
- Rich tool ecosystem: pre-built tools, custom functions, OpenAPI specs, MCP tools
- Multi-agent hierarchical coordination
- Built-in dev UI for testing and debugging
- Agent evaluation via CLI tools
- Session rewind capability (2026)
- Vertex AI Code Execution Sandbox integration
- **A2A protocol native support** — coordinates with A2A for cross-framework agent communication
- Deploy to Cloud Run or Vertex AI Agent Engine
- TypeScript SDK added (separate repo)

**NBA Quant Relevance: MEDIUM**
- Good if you want to build a Gemini-backed research subagent as alternative to Claude.
- ADK's graph execution in 2.0 is conceptually similar to LangGraph — worth watching.
- Not directly useful given "Claude Code and Google only" constraint — but Google backend via Vertex AI is supported.
- Agent evaluation framework could benchmark our Karpathy loop quality.

---

## 3. A2A Protocol (Agent2Agent, Google / Linux Foundation)

**What it is:** Open protocol enabling communication and interoperability between AI agents from different vendors/frameworks. Originally Google-initiated, now donated to Linux Foundation.

**GitHub:** `a2aproject/A2A` — actively maintained
**Spec:** `a2a-protocol.org/latest/` — currently v0.3
**Maturity:** v0.3 (stable interface). Linux Foundation ownership signals long-term commitment.
**Industry support:** 50+ partners including Atlassian, Box, LangChain, PayPal, SAP, ServiceNow

**Key Features:**
- Cross-framework agent coordination (Claude agents talking to Gemini agents, etc.)
- v0.3: gRPC support, security card signing, extended Python SDK client support
- Complements MCP (MCP = tools/context, A2A = agent-to-agent delegation)
- CrewAI 1.10.1 has native A2A support
- Google ADK has native A2A support

**NBA Quant Relevance: LOW (now), MEDIUM (future)**
- Not immediately useful — our agents are all Claude-based.
- Future value: if we wanted a Gemini-based data scraping agent talking to Claude prediction agent.
- Worth monitoring as it could enable mixed-model research pipelines.

---

## 4. OpenAI Agents SDK

**What it is:** Lightweight, provider-agnostic Python framework for multi-agent workflows. Open-sourced March 2025, active development through 2026.

**GitHub:** `openai/openai-agents-python` — **20.3k stars**, 3.3k forks, 75 releases
**Install:** `pip install openai-agents`
**Latest:** v0.13.0 (2026-03-23)
**Maturity:** Production-stable (v0.x semantic but widely deployed)

**Key Features:**
- Agents with instructions, tools, guardrails, handoffs
- Agent-as-tool and handoff patterns for delegation
- Built-in guardrails for input/output validation
- Human-in-the-loop mechanisms
- Sessions: automatic conversation history management
- Tracing: built-in debug/optimize via dashboard
- **Voice agents**: gpt-realtime-1.5 with full agent features
- **Provider-agnostic**: works with 100+ LLMs via LiteLLM
- RealtimeRunner for SIP protocol (voice/telephony)
- Python 3.14 compatibility
- Supports OpenAI Responses API (stateful) and Chat Completions

**NBA Quant Relevance: LOW**
- We explicitly use Claude Code only (no external LLMs per user decision).
- Provider-agnostic nature is interesting but not actionable in our context.
- The tracing/observability pattern is worth stealing for our own pipeline.

---

## 5. MCP Ecosystem (Model Context Protocol)

**What it is:** Open standard for connecting LLMs to external tools, data, and systems. Created by Anthropic Nov 2024, donated to Linux Foundation (via AAIF) Dec 2025. Now co-governed with Block, OpenAI, and others.

**Official Registry:** `registry.modelcontextprotocol.io`
**Community Directory:** `mcp-awesome.com` — 1200+ servers
**GitHub:** `modelcontextprotocol/servers` — reference implementations
**Spec:** `modelcontextprotocol.io/specification/2025-11-25` (latest)
**Maturity:** Production-standard. Every major AI vendor supports it (Anthropic, OpenAI, Google).

**Key Developments (2026):**

### MCP Tool Search (NEW — March 2026)
Lazy loading: Claude Code only fetches the specific tool needed, not all tool definitions upfront.
- Token usage drops from ~134k to ~5k (85% reduction) when >10% of context is tool definitions
- Switches to lightweight search index automatically

### MCP Elicitation (NEW)
MCP servers can now request structured input mid-task (form fields, browser URL).
`Elicitation` and `ElicitationResult` hooks to intercept/override responses.

### Notable MCP Servers for NBA Quant:
| Server | Use Case |
|--------|---------|
| Supabase MCP (official) | NBA database queries, experiment tracking |
| Playwright MCP (Microsoft) | Browser automation for odds scraping |
| GitHub MCP (official) | Deploy to HF Spaces, manage repos |
| Neo4j MCP (official) | Knowledge graph queries |
| Brave Search MCP | Real-time web research |
| Firecrawl MCP | Structured web scraping |
| PostgreSQL MCP | Direct DB connections |
| Filesystem MCP | Local file operations |

**2026 Roadmap Pain Points Being Fixed:**
- Authentication: OAuth 2.0 support being standardized (previously each server rolled its own)
- Multi-tenant: better isolation for enterprise deployments
- Streaming: long-running tool calls with progress updates
- Schema validation: stricter input/output typing

**NBA Quant Relevance: HIGH (already using)**
- Supabase MCP, Neo4j MCP, HuggingFace MCP already deployed.
- MCP Tool Search is a direct win for our research agents (reduces token burn).
- Playwright MCP would enable autonomous odds scraping without custom code.

---

## 6. LangGraph vs CrewAI vs AutoGen: 2026 State

### LangGraph (LangChain AI)
**GitHub:** `langchain-ai/langgraph` — **44.6k stars**
**Maturity:** Production. Used by Klarna, Replit, and major enterprises.
**Design:** Graph-based state machines with explicit control flow.

**Strengths:**
- Durable execution: agents survive failures, resume exactly where left off
- Fine-grained state management: inspect/modify state at any execution point
- Human-in-the-loop: interrupt at any node for approval
- LangSmith observability: best-in-class tracing with replay from any point
- Parallel node execution: 2.2x faster than CrewAI benchmarks
- Production battle-tested: longest track record in enterprise

**Weaknesses:**
- Steepest learning curve: requires understanding graph theory (nodes, edges, state schemas)
- Most verbose: 3-4x more boilerplate than CrewAI for equivalent workflows

**Best for:** Production stateful systems requiring reliability guarantees and deep observability.

---

### CrewAI
**GitHub:** `crewAIInc/crewAI` — **45.9k stars** (neck-and-neck with LangGraph)
**Latest:** v1.10.1 (native MCP + A2A support)
**Maturity:** Production. 12 million daily agent executions.
**Design:** Role-based agents (role, goal, backstory) within a "crew."

**Strengths:**
- Fastest time-to-production: 40% faster to deploy than LangGraph
- YAML config: readable, low-boilerplate agent definitions
- Native MCP and A2A (v1.10.1)
- Most beginner-friendly
- Lightest dependency footprint (no LangChain dependency)
- Active development (not maintenance mode)

**Weaknesses:**
- Less control over execution flow vs LangGraph
- Debugging harder when things go wrong
- State management less explicit

**Best for:** Standard business workflows, quick prototypes, time-to-production priority.

---

### AutoGen (Microsoft) — MAINTENANCE MODE
**Status:** Microsoft has retired AutoGen in favor of Microsoft Agent Framework (MAF).
**AutoGen** now receives only bug fixes and security patches — no new features.

**Microsoft Agent Framework (MAF):**
- Reached Release Candidate (Feb 19, 2026) for both .NET and Python
- GA targeted Q1 2026
- Unifies AutoGen + Semantic Kernel
- Adds session-based state management, type safety, filters, telemetry
- Target: enterprise-grade (compliance, governance focus)

**NBA Quant Relevance: SKIP** — Don't start new projects on AutoGen. MAF is .NET-heavy, enterprise-focused, not sports-quant oriented.

---

### PydanticAI (Rising)
**GitHub:** `pydantic/pydantic-ai` — **15.4k stars** (fast growth)
**Latest:** v1.x (Production/Stable as of March 18, 2026)
**Design:** Type-safe agent framework built on Pydantic validation.

**Strengths:**
- Fully type-safe: errors caught at write-time, not runtime
- Durable execution: survives API failures and restarts
- Human-in-the-loop: flag tool calls for approval
- Clean, Pythonic API
- Model-agnostic: Claude, Gemini, OpenAI, Ollama

**NBA Quant Relevance: LOW (now)** — type safety is valuable but we're not building user-facing APIs where schema validation matters most. Monitor.

---

## 7. Claude Code: Hooks, Skills & Remote Triggers

### Hooks (12 lifecycle events)
Hooks fire at specific points in Claude Code's execution. Three handler types:
1. **Command hooks**: shell commands receiving JSON via stdin
2. **Prompt hooks**: single-turn Claude model evaluation
3. **Agent hooks**: full subagents with tool access

**Available Hook Events:**
- `PreToolUse` — intercept before any tool call
- `PostToolUse` — log/audit after tool execution
- `Stop` — fires when agent completes
- `StopFailure` (NEW v0.1.50) — fires on API errors (rate limit, auth failure)
- `SessionStart` / `SessionEnd`
- `UserPromptSubmit`
- And 6 more context/state events

**HTTP Hooks (Remote Triggers):**
Send hook events to a remote web server instead of local scripts.
- Enables team-wide policy enforcement servers
- Our trigger at `trig_01BS3ixBvt2uKHY9p5EemcgD` uses this pattern

### Skills
Defined in `.claude/skills/SKILL.md`. Progressive disclosure architecture:
- Metadata (always loaded) → core instructions (on-demand) → supplementary files → executable Python
- Work across Claude.ai, Claude Code CLI, and Agent SDK
- Complement to MCP (Skills = complex workflows, MCP = tool connectivity)

### SDK Features (Agent SDK)
- `ClaudeAgentOptions.hooks={}` — programmatic hook registration
- `HookMatcher(matcher="Bash", hooks=[callback])` — regex-based tool matching
- `session_id` capture and `resume=session_id` — persistent sessions

**NBA Quant Relevance: HIGH (already using)**
- Missing hook: `StopFailure` for rate limit logging (v0.1.50 actionable today)
- Context monitor hook at 40%/30%/15% remaining is still not implemented
- Skills for `/karpathy-loop`, `/tony-bloom`, `/progress-10pct` are live

---

## 8. Browser Automation Agents

### Stagehand (Browserbase) — v3 (February 2026)
**GitHub:** `browserbase/stagehand`
**What:** TypeScript SDK built on Playwright with AI-native primitives: `act()`, `extract()`, `observe()`
**v3 changes:** Complete rewrite. Directly uses Chrome DevTools Protocol (CDP), bypasses Playwright's automation layer. **44% faster** than v2.
**Best for:** Hybrid workflows (Playwright for predictable steps + AI for the ambiguous 20%)

### Browser-Use
**GitHub:** `browser-use/browser-use` — **50k+ stars** (one of fastest-growing AI OSS projects)
**What:** Full autonomous agent loop. LLM decides what to click, type, scroll. Python.
**Best for:** Complex multi-step tasks requiring true autonomy (e.g., autonomous odds scraping from multiple bookmakers)

### Playwright MCP (Microsoft)
**Install:** `npx @playwright/mcp@latest`
**What:** Official MCP server wrapping Playwright for browser automation.
**Best for:** Direct integration into Claude Agent SDK pipelines via `mcp_servers={"playwright": {...}}`

### Comparison Matrix:
| Tool | Stars | Language | AI Control | Speed | Best For |
|------|-------|----------|------------|-------|---------|
| Browser-Use | 50k+ | Python | Full autonomous | Slow (per-step LLM) | Complex research tasks |
| Stagehand v3 | ~8k | TypeScript | Surgical (act/extract) | Fast (CDP direct) | Hybrid prod workflows |
| Playwright MCP | N/A | Any (MCP) | Via Claude | Fast | Claude SDK integration |
| Playwright raw | 67k | Multi | None | Fastest | Deterministic scraping |

**NBA Quant Relevance: HIGH**
- **Playwright MCP** is the immediate win: drop into our Agent SDK via `mcp_servers` for odds page scraping
- **Browser-Use** for autonomous multi-bookmaker odds harvesting (no code, just natural language goals)
- Current odds scraping is cron-based and brittle — browser agents would make it resilient

---

## 9. Free GPU Options (March 2026)

| Platform | Free GPU | VRAM | Session Limit | Notes |
|----------|---------|------|--------------|-------|
| Google Colab | T4 | 15 GB | ~12h with keepalive | Best for our use (Kaggle BROKEN) |
| HF ZeroGPU | H200 | 141 GB | 25 min/day (PRO $9/mo) | 30x faster — apply at huggingface.co/zero-gpu-explorers |
| Kaggle | Dual T4 | 30 GB | 12h | BROKEN for our account |
| Lightning AI | Various | ~16 GB | 22h/month | Good for structured dev |
| Amazon SageMaker Studio Lab | T4 equiv | 15 GB | Long sessions | No AWS account needed |
| Paperspace Gradient | M4000 | 8 GB | 6h | Free community tier |
| Saturn Cloud | Various | ~16 GB | 30h/month | |

**Paid (best value):**
- RunPod: A6000 @$0.27/hr, A100 @$0.78/hr (~3-4x cheaper than Colab Pro)
- Vast.ai: spot market, can get H100 <$1/hr during off-peak

**NBA Quant Recommendations:**
- Primary: Colab T4 (current, working)
- Upgrade path: HF ZeroGPU H200 PRO tier ($9/mo) for S14/S15 Nomos42 spaces
- For Colab GPU evolution: `nba_evolution_gpu.ipynb` already configured

---

## 10. LangGraph + Claude Agent SDK Integration Pattern

The highest-value architectural finding from this research: **LangGraph as orchestration skeleton + Claude Agent SDK as execution engine inside nodes.**

```python
# Pattern: LangGraph node wrapping Claude Agent SDK
from langgraph.graph import StateGraph
from claude_agent_sdk import query, ClaudeAgentOptions

async def research_node(state):
    results = []
    async for msg in query(
        prompt=f"Research NBA prediction techniques for: {state['topic']}",
        options=ClaudeAgentOptions(allowed_tools=["WebSearch", "WebFetch"])
    ):
        if hasattr(msg, "result"):
            results.append(msg.result)
    return {"research": results}

async def market_node(state):
    async for msg in query(
        prompt=f"Analyze odds movement for: {state['games']}",
        options=ClaudeAgentOptions(allowed_tools=["Bash"])
    ):
        ...

graph = StateGraph(...)
graph.add_node("research", research_node)
graph.add_node("market", market_node)
graph.add_edge("research", "market")  # or parallel
```

**Benefits for Karpathy Loop:**
- Parallel research + market analysis simultaneously (currently sequential)
- Durable checkpointing: if Claude API rate-limits, LangGraph resumes from last checkpoint
- LangSmith tracing: full visibility into what each subagent found
- 2.2x faster overall cycle time via parallelization
- Human-in-the-loop: interrupt before writing to HF Space config

---

## Framework Decision Matrix for NBA Quant

| Need | Best Choice | Reasoning |
|------|------------|-----------|
| Autonomous research cycle | Claude Agent SDK | Already integrated, native tools |
| Orchestrating 4+ subagents | LangGraph + Agent SDK | Durable, parallel, observable |
| Browser odds scraping | Playwright MCP | Drop-in via mcp_servers |
| Complex autonomous scraping | Browser-Use | Natural language goals |
| Cross-vendor agent coordination | A2A Protocol | Future, when multi-model |
| Type-safe prediction API | PydanticAI | If we build a public API |
| Quick new workflow prototyping | CrewAI | Fastest time-to-prototype |

---

## Actionable Recommendations (Ranked by ROI)

### Immediate (< 1 hour each)
1. **StopFailure hook**: Add to all 4 agent scripts. Rate limit errors now silently fail. Native in Agent SDK v0.1.50.
2. **MCP Tool Search**: Already in Claude Code (automatic). Verify our research agents aren't preloading 100+ tools unnecessarily.
3. **Playwright MCP for odds**: Add `"playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}` to market-analyst agent for live odds page access.

### Short-term (< 1 day)
4. **Context monitor hook**: Implement graduated warnings at 40%/30%/15% context remaining. Prevents research cycles that silently truncate.
5. **Browser-Use for odds harvesting**: Replace brittle cron `nba-daily-odds.py` with a natural-language browser agent: "Collect NBA game odds from DraftKings, FanDuel, BetMGM, return JSON."
6. **HF ZeroGPU PRO** ($9/mo): Upgrade S14/S15 Nomos42 from Colab T4 to H200. 30x speedup on evolution cycles.

### Medium-term (< 1 week)
7. **LangGraph integration**: Wrap Karpathy loop nodes in LangGraph for parallel execution + durable checkpointing. Expected: 2x faster cycle, zero lost research from rate limits.
8. **In-process Supabase MCP**: Replace subprocess MCP calls with in-process Python functions. Eliminates IPC overhead for high-frequency experiment queries.

---

## Sources

- [Claude Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Claude Agent SDK Python GitHub](https://github.com/anthropics/claude-agent-sdk-python)
- [Building Agents with Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [Google ADK Python GitHub](https://github.com/google/adk-python)
- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [ADK 2.0 Alpha — TypeScript](https://developers.googleblog.com/introducing-agent-development-kit-for-typescript-build-ai-agents-with-the-power-of-a-code-first-approach/)
- [A2A Protocol GitHub](https://github.com/a2aproject/A2A)
- [A2A Google Cloud Blog Upgrade](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade)
- [Linux Foundation A2A Launch](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents)
- [OpenAI Agents SDK Docs](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK GitHub Releases](https://github.com/openai/openai-agents-python/releases)
- [MCP Servers GitHub](https://github.com/modelcontextprotocol/servers)
- [Official MCP Registry](https://registry.modelcontextprotocol.io/)
- [Awesome MCP Servers 1200+](https://mcp-awesome.com/)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [LangGraph 2026 Decision Guide](https://dev.to/linou518/the-2026-ai-agent-framework-decision-guide-langgraph-vs-crewai-vs-pydantic-ai-b2h)
- [CrewAI GitHub](https://github.com/crewAIInc/crewAI)
- [Microsoft AutoGen Retirement / MAF Launch](https://venturebeat.com/ai/microsoft-retires-autogen-and-debuts-agent-framework-to-unify-and-govern)
- [Microsoft Agent Framework Overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [PydanticAI GitHub](https://github.com/pydantic/pydantic-ai)
- [CrewAI vs LangGraph vs AutoGen 2026](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen)
- [LangGraph vs CrewAI vs AutoGen March 2026](https://docs.bswen.com/blog/2026-03-16-langgraph-crewai-autogen-comparison/)
- [Claude Code Hooks Guide 2026](https://code.claude.com/docs/en/hooks-guide)
- [Claude Code Hooks 12 Events Reference](https://www.pixelmojo.io/blogs/claude-code-hooks-production-quality-ci-cd-patterns)
- [Awesome Claude Code (skills, hooks, commands)](https://github.com/hesreallyhim/awesome-claude-code)
- [Stagehand v3](https://www.browserbase.com/blog/stagehand-v3)
- [Browser-Use vs Stagehand 2026](https://www.skyvern.com/blog/browser-use-vs-stagehand-which-is-better/)
- [AI Browser Automation 2026 Top 6](https://awesomeagents.ai/tools/best-ai-browser-automation-tools-2026/)
- [Best Free Cloud GPU 2026](https://iotbyhvm.ooo/best-free-cloud-gpu-platforms-in-2026-google-colab-kaggle-and-more/)
- [Top Colab Alternatives March 2026](https://www.thundercompute.com/blog/colab-alternatives-for-cheap-deep-learning-in-2025)
- [Anthropic MCP Upgrades Jan 2026](https://www.opensourceforu.com/2026/01/anthropic-upgrades-open-source-mcp-to-scale-tool-rich-ai-agents/)
