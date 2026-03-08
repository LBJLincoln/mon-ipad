# MCP + RAG Integration Playbook
## Connect AI Assistants Directly to Your RAG Pipelines

> Built from production experience connecting Claude Code, Cursor, and custom agents to a 4-pipeline RAG system serving 61K+ queries at 87.5-95.2% accuracy.

---

## What You Get

### 1. MCP Server Architecture for RAG (Chapter 1-3)
- **Complete MCP server implementation** in TypeScript and Python
- 4 server patterns: read-only retrieval, read-write with ingestion, multi-pipeline routing, streaming results
- Connection patterns for Claude Desktop, Claude Code, Cursor, Windsurf, and custom clients
- Production config templates (stdio, SSE, HTTP streaming)

### 2. RAG Tool Design Patterns (Chapter 4-6)
- **12 MCP tool definitions** optimized for RAG operations:
  - `search_documents` — semantic search with metadata filtering
  - `query_knowledge_graph` — Cypher query generation + execution
  - `run_sql_query` — natural language to SQL with guardrails
  - `ingest_document` — chunking + embedding + indexing pipeline
  - `evaluate_answer` — LLM-as-judge quality scoring
  - `get_pipeline_status` — health checks across all pipelines
  - Plus 6 more specialized tools
- Input/output schema design for maximum LLM compatibility
- Error handling patterns that help the AI self-correct

### 3. Multi-Pipeline MCP Router (Chapter 7-9)
- **Intent-based routing** across Standard, Graph, Quantitative, and Agentic pipelines
- Query classification prompts that achieve 94% routing accuracy
- Fallback chains and graceful degradation
- Context window management for large retrieval results
- Streaming responses for real-time UX

### 4. Security & Access Control (Chapter 10-11)
- Authentication patterns for MCP servers (API keys, OAuth, mTLS)
- Rate limiting and quota management per client
- Input sanitization against prompt injection via MCP tools
- Audit logging for compliance (who queried what, when)
- Multi-tenant isolation in MCP tool responses

### 5. Production Deployment (Chapter 12-14)
- Docker deployment with health checks
- Kubernetes manifests for scaled MCP servers
- Monitoring: latency histograms, error rates, token usage per tool
- Cost tracking per MCP client and tool invocation
- Blue-green deployment for zero-downtime updates

### 6. Real-World Integration Examples (Chapter 15-17)
- **Claude Code + RAG**: AI coding assistant that searches your codebase AND your knowledge base
- **Cursor + RAG**: IDE integration for documentation-aware code generation
- **Custom chatbot + RAG**: Next.js app with MCP client connecting to your RAG backend
- **n8n + MCP**: Workflow automation that calls MCP tools as nodes
- **Multi-agent orchestration**: Agent A retrieves, Agent B analyzes, Agent C acts

### 7. Bonus: Migration Guide (Chapter 18)
- Migrating from LangChain/LlamaIndex to MCP-native architecture
- Performance comparison: REST API vs MCP protocol
- When to use MCP vs direct API calls (decision matrix)

---

## File Inventory

```
mcp-rag-integration-playbook/
├── README.md                          # This file
├── 01-mcp-fundamentals.md             # MCP protocol deep dive for RAG engineers
├── 02-server-architecture.md          # 4 server patterns with trade-offs
├── 03-typescript-server.md            # Complete TypeScript MCP server (450+ lines)
├── 04-python-server.md                # Complete Python MCP server (400+ lines)
├── 05-tool-definitions.md             # 12 RAG tool schemas + design rationale
├── 06-retrieval-tools.md              # Search, filter, rerank tool implementations
├── 07-multi-pipeline-router.md        # Intent routing across 4 pipelines
├── 08-context-management.md           # Token budgets, chunked responses, streaming
├── 09-error-handling.md               # Self-correcting patterns for AI clients
├── 10-security.md                     # Auth, rate limits, injection prevention
├── 11-multi-tenant.md                 # Tenant isolation in MCP responses
├── 12-docker-deployment.md            # Production Docker setup
├── 13-monitoring.md                   # Metrics, alerts, dashboards
├── 14-cost-tracking.md                # Per-client, per-tool cost attribution
├── 15-claude-code-integration.md      # Claude Code + RAG walkthrough
├── 16-cursor-integration.md           # Cursor IDE + RAG walkthrough
├── 17-multi-agent.md                  # Agent orchestration via MCP
├── 18-migration-guide.md              # LangChain/LlamaIndex → MCP
├── code/
│   ├── mcp-rag-server.ts              # Production TypeScript server
│   ├── mcp-rag-server.py              # Production Python server
│   ├── tool-schemas.json              # All 12 tool definitions
│   ├── router.ts                      # Multi-pipeline intent router
│   ├── auth-middleware.ts             # Authentication middleware
│   ├── rate-limiter.ts                # Token-aware rate limiting
│   └── docker-compose.yml            # Production deployment
├── configs/
│   ├── claude-desktop-config.json     # Claude Desktop MCP config
│   ├── claude-code-config.json        # Claude Code MCP config
│   ├── cursor-config.json             # Cursor MCP config
│   └── n8n-mcp-node.json             # n8n custom MCP node
└── tests/
    ├── tool-test-suite.ts             # 50 test cases for MCP tools
    └── load-test.ts                   # Concurrent client simulation
```

---

## Who This Is For

- **RAG engineers** who want to expose their pipelines to AI assistants via MCP
- **Platform teams** building internal AI tools that need structured access to knowledge bases
- **AI product developers** shipping MCP-enabled features to end users
- **DevOps/SRE** teams deploying and monitoring MCP servers in production

## Key Numbers

| Metric | Value |
|--------|-------|
| Chapters | 18 |
| Code files | 9 production-ready |
| Tool definitions | 12 |
| Test cases | 50 |
| Config templates | 4 IDE/client configs |
| Lines of code | 1,800+ |
| Battle-tested on | 61K+ queries |

---

## Prerequisites

- Basic understanding of RAG (retrieval-augmented generation)
- Familiarity with TypeScript or Python
- A running RAG pipeline (any architecture)

## Price

**$147** — One-time purchase, lifetime access to updates.

Part of the **MEGA BUNDLE ($497)** — Get this + 15 other production RAG tools.

---

*Built by Alexis Moret (Polytechnique + HEC Paris) from 76+ engineering sessions and 1,100+ commits building production RAG systems.*
