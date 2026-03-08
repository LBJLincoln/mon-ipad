# SOTA COMPARISON 2026 — Our Approach vs Industry Best Practices

> Generated: 2026-03-08 | Research Session 87
> 10 topics researched across 100+ sources

---

## EXECUTIVE SUMMARY

| Category | Our Level | SOTA Level | Gap | Priority |
|----------|-----------|------------|-----|----------|
| Claude Code setup | **Advanced** (top 10%) | Expert | Small | LOW |
| Self-healing pipelines | **Basic** (3-failure stop) | Autonomous repair agents | Large | HIGH |
| Autonomous agents | **Experimental** (daemons) | Production harnesses | Medium | MEDIUM |
| Monetisation | **Live** (Stripe, 14 products) | Service+SaaS hybrid | Medium | HIGH |
| Eval & metrics | **Basic** (accuracy only) | 7-metric Ragas + LLM-judge | Large | CRITICAL |
| Reranking | **None** | Cohere Rerank 3.5 (+23-30%) | Critical | CRITICAL |
| CRAG / corrective RAG | **None** | Self-correcting loops | Large | HIGH |
| Hooks & automation | **None** | Full lifecycle hooks | Large | HIGH |
| Multi-agent orchestration | **Partial** (Task delegation) | Swarm orchestration | Medium | MEDIUM |
| Competitor tools | Claude Code only | Gemini CLI (free 1M ctx) | Awareness | LOW |

**Bottom line**: We are SOTA on Claude Code configuration (CLAUDE.md, skills, MCP) and evaluation scale (61K+ questions). We are behind on self-healing, reranking, corrective RAG, hooks, and comprehensive metrics. The 3 highest-impact gaps are: (1) Cohere Rerank 3.5, (2) CRAG corrective routing, (3) lifecycle hooks.

---

## 1. CLAUDE CODE BEST PRACTICES

### What SOTA teams do in 2026
- CLAUDE.md under 200 lines, monorepo-aware (ancestor/descendant loading)
- `.claude/rules/` for domain-specific patterns (progressive disclosure)
- `.claude/commands/` for reusable workflows (/new-feature, /deploy, /test-all)
- `.claudeignore` to reduce noise and focus context
- Plan Mode before every complex task (separate research from implementation)
- Failing tests first to give Claude a clear target
- Full stack traces in prompts (75% better diagnostic accuracy)
- Feature-specific sub-agents via skills, not generic "backend engineer" agents
- HTTP hooks for lifecycle automation (pre-commit checks, post-tool notifications)
- rulesync tool to unify rules across Claude Code, Gemini CLI, and Cursor

### What WE do
- CLAUDE.md: 200+ lines, comprehensive (infrastructure, pipelines, commands) -- GOOD
- 17 custom skills in `.claude/commands/` -- EXCELLENT (top 5% of users)
- MCP servers: 6 configured (neo4j, pinecone, supabase, cohere, jina, huggingface) -- EXCELLENT
- Task delegation: Opus for decisions, Sonnet for execution, Haiku for exploration -- GOOD
- State files: PROJECT-STATE.md, DEBUG-PLAYBOOK.md, PROCESS-RUNBOOKS.md -- EXCELLENT
- Session start/end skills with auto-memory -- ADVANCED

### What WE DON'T do yet
- **NO hooks configured** -- Missing the entire lifecycle automation layer
- **NO .claudeignore** -- Context includes everything (noise)
- **NO Plan Mode discipline** -- Not enforced in skills
- **NO rulesync** -- Rules only work in Claude Code, not portable
- **NO sub-agent specialization** -- Skills are general-purpose, not feature-scoped

### VERDICT: **Advanced (top 10%)** -- but missing hooks (the #1 new feature of 2026)

### Actions
1. **Add hooks** (HIGH): Pre-commit credential scan, post-tool logging, auto-metrics update
2. **Add .claudeignore** (LOW): Exclude node_modules, .git, large datasets, monetisation/packages
3. **Enforce Plan Mode** (MEDIUM): Add "always plan first" instruction to CLAUDE.md

---

## 2. HOW ANTHROPIC USES CLAUDE CODE INTERNALLY

### Key findings
- 60-100 internal versions released per day
- Engineers push ~5 PRs/day (vs industry 1-2/day)
- Claude Cowork was mostly built BY Claude Code
- Claude Code reads CLAUDE.md, identifies relevant files, explains dependencies
- 80% reduction in research time (1h -> 10-20min)
- Internal debate about releasing tool publicly (competitive advantage)

### Our comparison
- We commit every 15-20 min (good cadence, ~1100+ commits)
- We use Claude Code to pilot 7 repos (similar to their multi-repo usage)
- We don't have the PR velocity they do (we work solo, they're a team)
- We DO use Claude Code for code generation, debugging, architecture -- aligned with their usage

### VERDICT: **Aligned with Anthropic's patterns** -- we're using it as intended

---

## 3. SELF-HEALING CI/CD

### SOTA 2026 patterns
- **Pipeline Doctor / Interceptor**: Failure triggers "Repair Agent" with log access + commit rights
- **Log Doctor agents**: Parse errors, recognize missing deps, auto-add and rebuild
- **Analyze -> Patch -> Verify -> Propose loop**: Controlled self-healing with human gate
- **LLM-as-a-Judge**: Secondary model evaluates primary agent's output (not hard-coded strings)
- **Elastic's self-healing**: Fixed 24 broken PRs in first month, saved 20 dev days
- **MTTR reduction**: 70-80% improvement with self-healing
- **Dagger**: Self-healing CI pipelines with AI agents (open-source framework)
- **Screenshot + DOM analysis**: AI reads visual output to diagnose UI failures

### What WE have
- `self-heal` skill: Manual trigger, basic diagnostic
- "3+ regressions -> REVERT" rule
- "Auto-stop on 3 failures" rule
- DEBUG-PLAYBOOK.md with 75+ fixes (knowledge base for human-guided repair)
- No automated repair loop
- No CI/CD pipeline at all (manual eval + manual deploy)

### What WE'RE MISSING
- **No Analyze->Patch->Verify->Propose loop** -- Our self-heal skill doesn't auto-fix
- **No LLM-as-a-Judge** -- We use fuzzy string match for accuracy (primitive)
- **No CI/CD pipeline** -- Everything is manual (eval, deploy, sync)
- **No failure-triggered agents** -- No hooks that spawn repair agents on pipeline failure
- **No screenshot/DOM analysis** -- Website issues require manual inspection

### VERDICT: **Basic** -- We have knowledge (playbook) but no automation

### Actions
1. **Implement hooks-based self-heal** (HIGH): Hook on n8n failure -> spawn diagnostic agent
2. **Add LLM-as-a-Judge** (CRITICAL): Replace fuzzy match with LLM evaluation
3. **Create minimal CI** (MEDIUM): GitHub Actions that run quick-test on push
4. **Dagger integration** (LOW): Consider for future CI pipeline

---

## 4. AUTONOMOUS CODING AGENTS

### SOTA 2026 landscape
- **SWE-agent 1.0** (Claude 3.5): 47% SWE-Bench Lite, 57.6% Verified
- **OpenHands + CodeAct v2.1**: 42% Lite, 52.4% Verified (enterprise-ready, web UI)
- **AutoCodeRover-v2.0**: 37.33% Lite, 45% Verified (autonomous program improvement)
- **Devin**: $500/month, most autonomous, enterprise positioning
- **GPT-5**: Only 21% on SWE-EVO (harder benchmark) vs 65% on SWE-Bench Verified
- **Claude Code (Sonnet 4.6)**: 79.6% SWE-bench -- HIGHEST of all
- **Terminal-native agents**: Biggest shift of 2026 (from IDE plugins to CLI)
- **Agent harnesses**: 2026 = "year of agent harnesses" (production-grade autonomous coding)

### What WE have
- Claude Code Opus 4.6 as primary agent (SOTA model)
- Task delegation to Sonnet 4.5 and Haiku 4.5
- Autonomous daemons on Codespaces (monetisation + testing loops)
- OpenClaw bot on Telegram (@Nomos42Bot)
- 17 custom skills for specialized workflows

### What WE'RE MISSING
- **No agent harness** -- Our daemons are bash scripts, not production harnesses
- **No human-in-the-loop gate** -- Daemons run unsupervised with no approval flow
- **No parallel agent teams** -- We run one agent at a time (VM RAM limit)
- **No SWE-bench evaluation** -- We don't benchmark our agent's coding ability

### VERDICT: **Experimental** -- We have the right model but need production harness

### Actions
1. **Claude Agent SDK** (HIGH): Replace bash daemons with SDK-based agents
2. **Human-in-the-loop** (MEDIUM): Telegram approval flow before commits
3. **Multi-agent on Codespace** (MEDIUM): Run parallel agents where RAM allows

---

## 5. AI AGENT MONETISATION

### SOTA 2026 strategies
- **Market**: $7.63B (2025) -> $182.97B (2033), 49.6% CAGR
- **40% enterprise apps** will embed AI agents by end 2026
- **Service-based**: $2K-10K/month with 5-15 clients (highest margin)
- **SaaS/subscription**: $500-1000/month recurring per client
- **Hybrid pricing**: Base fee + per-task variable (most popular in 2026)
- **Outcome-based**: % of cost savings or revenue generated
- **Productize from consulting**: 10th client becomes standardized product
- **10x more demand than supply** in 2026

### What WE have
- 14 Stripe products live ($27-$497 range)
- Sales page deployed on GitHub Pages
- ZIP packages (6 sanitized)
- Distribution posts written (6 platforms)
- Telegram sales bot
- One-time purchase model only

### What WE'RE MISSING
- **No recurring revenue** -- All products are one-time purchases
- **No service/consulting tier** -- Missing the $2K-10K/month segment
- **No outcome-based pricing** -- No "pay for results" option
- **No client pipeline** -- No lead generation system
- **No demo/trial** -- No free tier to convert prospects
- **No community** -- No Discord/Slack for buyers

### VERDICT: **Live but primitive** -- Products exist but no recurring revenue engine

### Actions
1. **Add SaaS tier** (HIGH): Monthly RAG-as-a-Service for SMBs ($500-2K/month)
2. **Add consulting page** (HIGH): "Deploy Multi-RAG for your enterprise" offering
3. **Free demo** (MEDIUM): Let prospects test RAG pipeline with their data
4. **Build community** (MEDIUM): Discord for buyers, share updates, upsell

---

## 6. CONSISTENT MEASURABLE PROGRESS

### SOTA practices
- **15% sprint time** allocated to productivity improvements
- **Retrospectives** at heart of continuous improvement
- **Velocity tracking** per sprint
- **Cycle time** monitoring for process optimization
- **Defect rate** (defects per KLOC) for quality
- **Run experiments, not just track metrics** -- Most effective approach
- **5% defect reduction / 10% delivery improvement** as concrete targets

### What WE have
- `progress-10pct` skill targeting weakest metric
- Phase-based evaluation (200 -> 1K -> 10K -> 100K questions)
- Session-based tracking (84 sessions, 1100+ commits)
- Accuracy as primary metric per pipeline
- PROJECT-STATE.md updated after milestones

### What WE'RE MISSING
- **No sprint cadence** -- Sessions are ad-hoc, not time-boxed
- **No velocity tracking** -- We count commits but not value delivered
- **No retrospective process** -- session-end captures state but doesn't analyze
- **No experiment framework** -- Changes are intuitive, not hypothesis-driven
- **Only 1/7 metrics tracked** (accuracy only, missing faithfulness/recall/precision/relevancy/hallucination/latency)

### VERDICT: **Partial** -- Good intuition-based progress, no systematic framework

### Actions
1. **Implement Ragas metrics** (CRITICAL): 7 enterprise metrics, not just accuracy
2. **Weekly retrospective** (MEDIUM): Add to session-end skill
3. **Experiment log** (LOW): Track hypothesis -> change -> result -> keep/revert

---

## 7. CLAUDE.md / CURSOR RULES BEST PRACTICES

### SOTA 2026 patterns
- CLAUDE.md = "short contract" (role, goal, constraints, uncertainty handling)
- ~150-200 instructions max for frontier models
- **Progressive disclosure**: Skills load context on-demand, not all at once
- **Domain rules in `.claude/rules/`**: Separate from main CLAUDE.md
- **.claudeignore**: Reduce noise, keep context focused
- **Feature-specific sub-agents**: Not generic roles
- **Avoid over-engineering instruction**: "Only changes directly requested"
- **Test-first methodology**: Failing tests before implementation
- **Agent-rules repo** (steipete): Cross-tool rules (Claude Code + Cursor)
- **Awesome Claude Code Toolkit**: 135 agents, 35 skills, 42 commands, 120 plugins, 19 hooks

### What WE have (our CLAUDE.md analysis)
- 200+ lines (at the upper limit -- good density)
- 9 sections (identity, quick start, state files, rules, infra, pipelines, commands, repos, docs)
- 10 core rules (well-structured, actionable)
- Pipeline-specific configuration (webhooks, IDs, batch sizes)
- LLM model catalog with costs
- Command reference with examples
- 17 custom skills with auto-detection

### What WE do BETTER than most
- **State file system**: PROJECT-STATE.md + DEBUG-PLAYBOOK.md is more sophisticated than most
- **6 MCP servers**: More integrations than typical setups
- **17 skills**: More than 95% of Claude Code users
- **Multi-model delegation**: Opus/Sonnet/Haiku routing is SOTA
- **Session management**: Start/end skills with memory persistence

### What WE'RE MISSING
- **No `.claude/rules/` directory** -- All rules in CLAUDE.md (monolithic)
- **No `.claudeignore`** -- Context pollution from irrelevant files
- **No hooks** -- 0/19 recommended hooks
- **No progressive disclosure** -- All context loaded at once
- **CLAUDE.md slightly over 200 lines** -- Could be trimmed

### VERDICT: **Top 10%** in content quality, **bottom 50%** in architecture (no hooks, no rules dir, no ignore)

### Actions
1. **Create `.claude/rules/`** (MEDIUM): Split pipeline rules, MCP rules, eval rules
2. **Create `.claudeignore`** (LOW): Quick win for context quality
3. **Add hooks** (HIGH): The single biggest gap in our setup
4. **Trim CLAUDE.md** (LOW): Move detailed tables to linked files

---

## 8. GEMINI CLI

### Capabilities (March 2026)
- **Open-source** (Apache 2.0), terminal-native
- **1M token context window** (Gemini 2.5 Pro, free)
- **Free tier**: 60 req/min, 1000 req/day (personal Google account)
- **Gemini 3 Flash**: Outperforms 2.5 Pro, 3x faster, fraction of cost
- **Built-in tools**: Google Search grounding, file ops, shell commands, web fetch
- **MCP support**: Compatible with our MCP servers
- **GEMINI.md**: Project-specific context file (like CLAUDE.md)
- **Multimodal**: Images, PDFs, hand-drawn sketches as input
- **ReAct loop**: Same agentic pattern as Claude Code

### Relevance to us
- **Competitor awareness**: Gemini CLI is free and powerful
- **Potential backup**: If Claude Code subscription lapses
- **Not a replacement**: Claude Code Opus 4.6 >> Gemini for our use case
- **rulesync**: Tool exists to unify rules across Claude Code + Gemini CLI + Cursor

### VERDICT: **Monitor, don't switch** -- Gemini CLI is impressive but Claude Code is superior for our workflow

---

## 9. OPENCLAW

### Current state (March 2026)
- **163K GitHub stars**, MIT license
- **5,700+ community skills** marketplace
- **50+ messaging channels** (WhatsApp, Telegram, Slack, Discord, etc.)
- **Native MCP support** -- compatible with our MCP servers
- **Local-first**: Data stays on your hardware
- **Voice wake and talk mode**
- **Live Canvas**: Agent-driven visual workspace
- **First-class tools**: Browser, canvas, nodes, cron, sessions
- **Companion apps**: macOS, iOS, Android

### What WE have
- OpenClaw running on Codespace with Gemini 2.5 Flash
- Telegram bot (@Nomos42Bot) connected
- Trinity-large-preview as fallback model

### What WE'RE MISSING
- **Not using 5,700+ skills** -- We only use basic chat
- **No PolyClaw** (Polymarket trading skill)
- **No cron jobs** -- Not using OpenClaw's built-in scheduling
- **Not leveraging multi-channel** -- Only Telegram, could add Discord/WhatsApp
- **Model cache issues** -- Still fighting agent cache bugs

### VERDICT: **Underutilized** -- We have it running but use <1% of its capabilities

### Actions
1. **Explore skill marketplace** (MEDIUM): Find RAG, analytics, or sales skills
2. **Add Discord channel** (LOW): Multi-channel presence for customers
3. **Set up cron tasks** (MEDIUM): Automated monitoring via OpenClaw

---

## 10. POLYMARKET TRADING BOTS

### Current state (March 2026)
- **Polymarket Agents**: Official developer framework for AI trading
- **PolyClaw**: OpenClaw skill for autonomous Polymarket trading
- **$115K in one week**: Best documented OpenClaw bot performance
- **$40M+ arbitrage profits**: Documented Apr 2024 - Apr 2025
- **50+ CLI endpoints** for programmatic trading
- **MCP integration**: Connect AI agents for autonomous trading
- **Most traders not profitable**: Only minority achieve consistency
- **Compressed margins**: Competition has squeezed arbitrage opportunities

### Relevance to us
- **Revenue diversification**: Alternative to product sales
- **Risk**: Most bots lose money; only arbitrage strategies consistently profit
- **Technical feasibility**: We have OpenClaw + MCP + Claude Code (all required components)
- **Capital required**: Need crypto wallet + initial capital

### VERDICT: **Interesting but risky** -- Better to focus on RAG monetisation first

### Actions
1. **Paper trading first** (LOW): Test with simulated capital
2. **Only if revenue goals unmet** (CONDITIONAL): Pivot to trading if product sales stall

---

## CRITICAL GAPS RANKED BY IMPACT

| # | Gap | Impact on Project | Effort | ROI |
|---|-----|-------------------|--------|-----|
| 1 | **Cohere Rerank 3.5** | +23-30% retrieval precision, direct accuracy boost | LOW (MCP tool ready) | **EXTREME** |
| 2 | **CRAG corrective routing** | Filter irrelevant retrievals, biggest Graph pipeline win | MEDIUM | **HIGH** |
| 3 | **LLM-as-a-Judge eval** | Replace fuzzy match, enterprise-grade metrics | MEDIUM | **HIGH** |
| 4 | **Lifecycle hooks** | Auto credential scan, auto metrics, failure alerts | LOW | **HIGH** |
| 5 | **Ragas 7-metric eval** | From 1/7 to 7/7 enterprise metrics | MEDIUM | **HIGH** |
| 6 | **Claude Agent SDK** | Replace bash daemons with production harnesses | MEDIUM | **MEDIUM** |
| 7 | **SaaS recurring revenue** | Monthly income vs one-time sales | HIGH | **HIGH** |
| 8 | **Self-healing CI loop** | Auto-fix pipeline failures | HIGH | **MEDIUM** |
| 9 | **.claudeignore + rules/** | Context quality improvement | LOW | **LOW** |
| 10 | **OpenClaw skill exploration** | Leverage 5,700 existing skills | LOW | **LOW** |

---

## WHAT WE ALREADY DO THAT'S SOTA

1. **17 custom skills** -- More than 95% of Claude Code users
2. **6 MCP server integrations** -- Neo4j, Pinecone, Supabase, Cohere, Jina, HuggingFace
3. **Multi-model delegation** -- Opus/Sonnet/Haiku routing (Anthropic's own recommended pattern)
4. **61,661 evaluation questions** from 18 SOTA benchmarks -- Massive scale
5. **State file architecture** -- PROJECT-STATE.md + DEBUG-PLAYBOOK.md is sophisticated
6. **Self-hosted embeddings** -- Independence from API providers
7. **9 HF Spaces** -- Robust n8n infrastructure
8. **1,100+ commits** in 84 sessions -- High velocity
9. **Session management skills** -- Structured start/end with memory persistence
10. **LiteLLM proxy** with 9 model aliases -- Professional model management

---

## RECOMMENDED NEXT 3 ACTIONS (This Session)

### Action 1: Add Cohere Rerank 3.5 to Standard pipeline
- MCP tool `mcp__cohere__cohere_rerank` already configured
- Expected: +23-30% retrieval precision
- Effort: 1-2 hours (update n8n workflow to add rerank step after retrieval)
- This is the single highest-ROI improvement available

### Action 2: Add lifecycle hooks
```json
// .claude/settings.json addition
"hooks": {
  "PreCommit": [{"command": "git diff --cached | grep -iE 'sk-or-|pcsk_|jV_zGdx|sbp_|hf_|jina_|ghp_' && echo 'CREDENTIAL LEAK' && exit 1 || exit 0"}],
  "PostSession": [{"command": "python3 eval/generate_status.py"}],
  "OnError": [{"command": "echo \"$(date): $ERROR\" >> /tmp/claude-errors.log"}]
}
```
- Effort: 30 minutes
- Automates credential scanning (currently manual rule #3)

### Action 3: Create .claudeignore
```
node_modules/
.git/
monetisation/packages/
datasets/
*.zip
*.tar.gz
```
- Effort: 5 minutes
- Immediate context quality improvement

---

## Sources

- [Claude Code Best Practices (Official)](https://code.claude.com/docs/en/best-practices)
- [50 Claude Code Tips (Geeky Gadgets)](https://www.geeky-gadgets.com/claude-code-tips-2/)
- [Claude Code Tips: 10 Productivity Workflows (F22 Labs)](https://www.f22labs.com/blogs/10-claude-code-productivity-tips-for-every-developer/)
- [How Anthropic Teams Use Claude Code (PDF)](https://www-cdn.anthropic.com/58284b19e702b49db9302d5b6f135ad8871e7658.pdf)
- [How Claude Code is Built (Pragmatic Engineer)](https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built)
- [Self-Healing CI/CD Architecture (Optimum Partners)](https://optimumpartners.com/insight/how-to-architect-self-healing-ci/cd-for-agentic-ai/)
- [Self-Healing CI Pipelines with AI Agents (Dagger)](https://dagger.io/blog/automate-your-ci-fixes-self-healing-pipelines-with-ai-agents)
- [Self-Correcting Monorepos with Claude (Elastic)](https://www.elastic.co/search-labs/blog/ci-pipelines-claude-ai-agent)
- [Beyond the Red Build (Medium)](https://ghidersa-mihaela.medium.com/beyond-the-red-build-9a506a829323)
- [Best AI Coding Agents 2026 (PlayCode)](https://playcode.io/blog/best-ai-coding-agents-2026)
- [OpenHands vs SWE-Agent (Local AI Master)](https://localaimaster.com/blog/openhands-vs-swe-agent)
- [AI Coding Landscape 2026 (ToolShelf)](https://toolshelf.dev/blog/ai-coding-landscape-2026)
- [Building Agents with Claude Agent SDK (Anthropic)](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [AI Agent Monetisation 2026 (Snaplama)](https://www.snaplama.com/blog/how-to-earn-money-from-ai-agents-in-2026-complete-monetization-strategy-guide)
- [SaaS/AI Pricing Models 2026 (Monetizely)](https://www.getmonetizely.com/blogs/the-2026-guide-to-saas-ai-and-agentic-pricing-models)
- [Pricing AI Agents Playbook (Chargebee)](https://www.chargebee.com/blog/pricing-ai-agents-playbook/)
- [15 AI Agent Startup Ideas $1M+ (Presta)](https://wearepresta.com/ai-agent-startup-ideas-2026-15-profitable-opportunities-to-launch-now/)
- [Writing a Good CLAUDE.md (HumanLayer)](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [Claude Code Best Practices: 15 Tips (aiorg.dev)](https://aiorg.dev/blog/claude-code-best-practices)
- [Awesome Claude Code (GitHub)](https://github.com/hesreallyhim/awesome-claude-code)
- [Agent Rules (steipete/GitHub)](https://github.com/steipete/agent-rules)
- [Everything Claude Code (GitHub)](https://github.com/affaan-m/everything-claude-code)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Gemini CLI (Google)](https://developers.google.com/gemini-code-assist/docs/gemini-cli)
- [Gemini CLI GitHub](https://github.com/google-gemini/gemini-cli)
- [Gemini 3 Flash in Gemini CLI](https://developers.googleblog.com/gemini-3-flash-is-now-available-in-gemini-cli/)
- [OpenClaw Official](https://openclaw.ai/)
- [OpenClaw 2026 Guide (AlphaTechFinance)](https://alphatechfinance.com/productivity-app/openclaw-ai-agent-2026-guide/)
- [OpenClaw Explained (Medium)](https://medium.com/@cenrunzhe/openclaw-explained-how-the-hottest-agent-framework-works-and-why-data-teams-should-pay-attention-69b41a033ca6)
- [Polymarket Agents (GitHub)](https://github.com/Polymarket/agents)
- [Polymarket Trading Bots 2026 (Medium)](https://medium.com/@stevenn.hansen/best-polymarket-trading-bots-for-automated-prediction-market-strategies-in-2026-bf06df02823b)
- [OpenClaw Polymarket Bot (FlyPix)](https://flypix.ai/openclaw-polymarket-trading/)
- [Cohere Rerank 3.5 (AWS)](https://aws.amazon.com/blogs/machine-learning/cohere-rerank-3-5-is-now-available-in-amazon-bedrock-through-rerank-api/)
- [Best Reranker Models for RAG 2026 (BSWEN)](https://docs.bswen.com/blog/2026-02-25-best-reranker-models/)
- [CRAG Paper (arXiv:2401.15884)](https://arxiv.org/abs/2401.15884)
- [Agentic RAG Self-Correcting (Let's Data Science)](https://www.letsdatascience.com/blog/agentic-rag-self-correcting-retrieval)
- [Tiny-Critic RAG (arXiv)](https://arxiv.org/html/2603.00846)
- [Claude Code Multi-Agent (Shipyard)](https://shipyard.build/blog/claude-code-multi-agent/)
- [Claude Code to AI OS Blueprint (DEV Community)](https://dev.to/jan_lucasandmann_bb9257c/claude-code-to-ai-os-blueprint-skills-hooks-agents-mcp-setup-in-2026-46gg)
