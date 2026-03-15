# AI Agent Orchestration Playbook
# Multi-Agent RAG Systems — From Single Pipeline to Autonomous Orchestration

> Production patterns from 76+ engineering sessions, 1,100+ commits, and 4 RAG pipelines.
> Alexis Moret — Polytechnique × HEC Paris

---

## Part 1: Agent Architecture Patterns

### 1.1 The Agent Orchestration Landscape

Modern RAG systems are evolving from static retrieve-and-generate pipelines into dynamic multi-agent systems. This playbook documents 8 battle-tested orchestration patterns we've deployed across 4 specialized RAG pipelines processing 61,000+ queries.

**Why agents matter for RAG:**
- Static routing fails on ambiguous queries (30-40% of real traffic)
- Single pipelines can't handle multi-domain questions
- Production RAG needs self-healing, retry logic, and adaptive strategies
- Users expect conversational, multi-turn interactions — not one-shot answers

### 1.2 The 8 Orchestration Patterns

#### Pattern 1: Router Agent (Intent Classification)

The simplest agent pattern. A single LLM classifies the query and routes to the appropriate pipeline.

```
User Query → [Router Agent] → Pipeline Selection → Execute → Response
```

**Implementation:**
```python
ROUTER_PROMPT = """You are a query router for a multi-pipeline RAG system.

Available pipelines:
1. STANDARD — General knowledge, definitions, explanations, comparisons
2. GRAPH — Relationship queries, connections between entities, network analysis
3. QUANTITATIVE — Numbers, statistics, financial data, calculations, trends
4. ORCHESTRATOR — Complex multi-part queries requiring multiple pipelines

Classify this query into exactly ONE pipeline.

Query: {query}

Respond with ONLY the pipeline name: STANDARD, GRAPH, QUANTITATIVE, or ORCHESTRATOR
"""

async def route_query(query: str, llm_client) -> str:
    response = await llm_client.complete(
        ROUTER_PROMPT.format(query=query),
        temperature=0.0,
        max_tokens=20
    )
    pipeline = response.strip().upper()
    valid = {"STANDARD", "GRAPH", "QUANTITATIVE", "ORCHESTRATOR"}
    return pipeline if pipeline in valid else "STANDARD"
```

**Production metrics:**
- Routing accuracy: 89.2% on 10K queries
- Latency overhead: ~200ms (single LLM call)
- Failure mode: Defaults to STANDARD on uncertain queries

#### Pattern 2: ReAct Agent (Reasoning + Acting)

The agent reasons step-by-step, deciding which tools to use and when to stop.

```
Query → [Think] → [Act: search/calculate/query] → [Observe] → [Think] → ... → Answer
```

**Implementation:**
```python
REACT_PROMPT = """You are a RAG research agent. Answer the user's question by
reasoning step-by-step and using the available tools.

Available tools:
- vector_search(query, top_k): Search the vector database
- graph_query(cypher): Execute a Cypher query on the knowledge graph
- sql_query(sql): Execute SQL on the structured database
- calculate(expression): Evaluate a mathematical expression

Format your response as:
Thought: [your reasoning about what to do next]
Action: [tool_name(parameters)]
Observation: [tool result will appear here]
... (repeat Thought/Action/Observation as needed)
Final Answer: [your complete answer]

Question: {query}
"""

class ReActAgent:
    def __init__(self, tools: dict, llm, max_steps: int = 5):
        self.tools = tools
        self.llm = llm
        self.max_steps = max_steps

    async def run(self, query: str) -> str:
        context = REACT_PROMPT.format(query=query)

        for step in range(self.max_steps):
            response = await self.llm.complete(context, stop=["Observation:"])
            context += response

            action = self._parse_action(response)
            if action is None:  # Final answer reached
                return self._parse_final_answer(response)

            tool_name, params = action
            result = await self.tools[tool_name](**params)
            observation = f"\nObservation: {result}\n"
            context += observation

        return "I couldn't find a complete answer within the step limit."

    def _parse_action(self, text: str) -> tuple | None:
        if "Final Answer:" in text:
            return None
        # Parse "Action: tool_name(params)" format
        import re
        match = re.search(r'Action:\s*(\w+)\((.+?)\)', text)
        if match:
            return match.group(1), self._parse_params(match.group(2))
        return None
```

**Production metrics:**
- Answer quality: +15% vs single-pipeline (on complex queries)
- Avg steps: 2.3 (most queries need 2-3 tool calls)
- Latency: 2-5s (acceptable for complex queries)

#### Pattern 3: Plan-and-Execute Agent

Separates planning from execution for complex, multi-step queries.

```
Query → [Planner: create step list] → [Executor: run each step] → [Synthesizer: combine] → Answer
```

**Implementation:**
```python
PLANNER_PROMPT = """Break down this complex query into sequential steps.
Each step should be a single, atomic action.

Query: {query}

Output a numbered list of steps:
1. [step description] → tool: [tool_name]
2. [step description] → tool: [tool_name]
...
"""

SYNTHESIZER_PROMPT = """Combine the results from multiple research steps
into a single, coherent answer.

Original query: {query}

Step results:
{step_results}

Provide a comprehensive answer that integrates all findings.
"""

class PlanAndExecuteAgent:
    def __init__(self, planner_llm, executor_llm, tools):
        self.planner = planner_llm
        self.executor = executor_llm
        self.tools = tools

    async def run(self, query: str) -> str:
        # Phase 1: Plan
        plan = await self.planner.complete(
            PLANNER_PROMPT.format(query=query)
        )
        steps = self._parse_plan(plan)

        # Phase 2: Execute each step
        results = []
        for step in steps:
            result = await self._execute_step(step)
            results.append({"step": step, "result": result})

        # Phase 3: Synthesize
        step_results = "\n".join(
            f"Step {i+1}: {r['step']}\nResult: {r['result']}"
            for i, r in enumerate(results)
        )
        answer = await self.planner.complete(
            SYNTHESIZER_PROMPT.format(query=query, step_results=step_results)
        )
        return answer
```

**When to use:**
- Queries that require information from multiple sources
- Questions with sub-questions (e.g., "Compare X and Y across dimensions A, B, C")
- Research tasks that need sequential reasoning

#### Pattern 4: Supervisor Agent (Hierarchical)

A supervisor agent delegates to specialized sub-agents and manages the conversation.

```
Query → [Supervisor] → assigns to → [Agent A] or [Agent B] or [Agent C]
                     → reviews results
                     → may reassign or combine
                     → Final Answer
```

```python
SUPERVISOR_PROMPT = """You are a supervisor managing a team of specialized agents:

1. StandardRAG Agent — Handles general knowledge queries
2. GraphRAG Agent — Handles relationship and network queries
3. QuantRAG Agent — Handles numerical and financial queries
4. Validator Agent — Fact-checks and validates answers

For the given query, decide which agent(s) to delegate to.
If a query spans multiple domains, delegate to multiple agents
and combine results.

Query: {query}

Respond with:
DELEGATE: [agent_name_1], [agent_name_2], ...
STRATEGY: parallel | sequential
"""

class SupervisorAgent:
    def __init__(self, sub_agents: dict, llm):
        self.agents = sub_agents
        self.llm = llm

    async def run(self, query: str) -> str:
        # Decide delegation
        decision = await self.llm.complete(
            SUPERVISOR_PROMPT.format(query=query)
        )
        agents, strategy = self._parse_decision(decision)

        # Execute
        if strategy == "parallel":
            results = await asyncio.gather(
                *[self.agents[a].run(query) for a in agents]
            )
        else:
            results = []
            context = query
            for agent_name in agents:
                result = await self.agents[agent_name].run(context)
                results.append(result)
                context += f"\n\nPrevious finding: {result}"

        # Validate and combine
        if len(results) > 1:
            return await self._combine_results(query, results)
        return results[0]
```

#### Pattern 5: Critic Agent (Self-Correcting)

An agent that generates an answer, then critiques and refines it.

```python
CRITIC_PROMPT = """Review this RAG-generated answer for:
1. Factual accuracy — Does the answer match the retrieved context?
2. Completeness — Are all parts of the question addressed?
3. Hallucination — Does the answer contain claims not in the context?
4. Relevance — Is the answer actually answering the question asked?

Question: {query}
Retrieved Context: {context}
Generated Answer: {answer}

Score (1-5) for each criterion and provide specific improvements needed.
If score < 3 on any criterion, the answer must be regenerated.

VERDICT: PASS or REGENERATE
FEEDBACK: [specific improvements needed]
"""

class CriticAgent:
    def __init__(self, generator, critic_llm, max_iterations=3):
        self.generator = generator
        self.critic = critic_llm
        self.max_iterations = max_iterations

    async def run(self, query: str) -> str:
        context = await self.generator.retrieve(query)

        for iteration in range(self.max_iterations):
            answer = await self.generator.generate(query, context)

            critique = await self.critic.complete(
                CRITIC_PROMPT.format(
                    query=query, context=context, answer=answer
                )
            )

            if "PASS" in critique:
                return answer

            # Feed critique back for regeneration
            feedback = self._extract_feedback(critique)
            context += f"\n\n[Critic Feedback]: {feedback}"

        return answer  # Return best effort after max iterations
```

#### Pattern 6: Memory Agent (Conversational)

Maintains conversation history and user context across turns.

```python
class MemoryAgent:
    def __init__(self, rag_agent, memory_store):
        self.agent = rag_agent
        self.memory = memory_store

    async def run(self, query: str, session_id: str) -> str:
        # Retrieve conversation history
        history = await self.memory.get_history(session_id, limit=10)

        # Resolve references ("it", "that company", "the previous metric")
        resolved_query = await self._resolve_references(query, history)

        # Execute with enriched context
        answer = await self.agent.run(resolved_query)

        # Store in memory
        await self.memory.store(session_id, {
            "query": query,
            "resolved": resolved_query,
            "answer": answer,
            "timestamp": datetime.utcnow()
        })

        return answer

    async def _resolve_references(self, query, history):
        RESOLVE_PROMPT = f"""Given this conversation history:
        {self._format_history(history)}

        Resolve any references in the new query:
        "{query}"

        Output the fully resolved, standalone query.
        """
        return await self.llm.complete(RESOLVE_PROMPT)
```

#### Pattern 7: Ensemble Agent (Multi-Pipeline Fusion)

Queries multiple pipelines simultaneously and fuses results.

```python
class EnsembleAgent:
    def __init__(self, pipelines: dict, fusion_llm):
        self.pipelines = pipelines
        self.fusion = fusion_llm

    async def run(self, query: str) -> str:
        # Query all relevant pipelines in parallel
        results = {}
        tasks = {
            name: pipeline.query(query)
            for name, pipeline in self.pipelines.items()
        }

        for name, task in tasks.items():
            try:
                results[name] = await asyncio.wait_for(task, timeout=10.0)
            except asyncio.TimeoutError:
                results[name] = None

        # Score each result
        scored = await self._score_results(query, results)

        # Fuse top results
        top_results = sorted(scored, key=lambda x: x['score'], reverse=True)[:3]

        FUSION_PROMPT = f"""Combine these pipeline results into the best answer:

        Query: {query}

        Results (ranked by relevance):
        {self._format_results(top_results)}

        Synthesize into a single, comprehensive answer.
        """
        return await self.fusion.complete(FUSION_PROMPT)
```

#### Pattern 8: Adaptive Agent (Self-Tuning)

Monitors its own performance and adapts strategy in real-time.

```python
class AdaptiveAgent:
    def __init__(self, strategies: list, monitor):
        self.strategies = strategies
        self.monitor = monitor
        self.performance_history = defaultdict(list)

    async def run(self, query: str) -> str:
        # Classify query characteristics
        query_type = await self._classify_query(query)

        # Select best strategy based on historical performance
        strategy = self._select_strategy(query_type)

        # Execute with selected strategy
        start_time = time.time()
        answer = await strategy.run(query)
        latency = time.time() - start_time

        # Record performance
        self.performance_history[query_type].append({
            "strategy": strategy.name,
            "latency": latency,
            "timestamp": datetime.utcnow()
        })

        # Adapt: if latency too high, try faster strategy next time
        if latency > self.monitor.latency_threshold:
            self._demote_strategy(strategy.name, query_type)

        return answer
```

---

## Part 2: Tool-Use Agents for RAG

### 2.1 Defining Tools

Every RAG agent needs tools. Here's how to define them properly.

```python
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    function: Callable

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": list(self.parameters.keys())
            }
        }

# RAG-specific tools
TOOLS = [
    Tool(
        name="vector_search",
        description="Search the vector database for semantically similar documents",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "top_k": {"type": "integer", "description": "Number of results", "default": 5},
            "filter": {"type": "object", "description": "Metadata filters"}
        },
        function=pinecone_search
    ),
    Tool(
        name="knowledge_graph_query",
        description="Query the Neo4j knowledge graph using Cypher",
        parameters={
            "cypher": {"type": "string", "description": "Cypher query"},
            "params": {"type": "object", "description": "Query parameters"}
        },
        function=neo4j_query
    ),
    Tool(
        name="sql_query",
        description="Query structured data in Supabase using SQL",
        parameters={
            "sql": {"type": "string", "description": "SQL query (SELECT only)"},
            "params": {"type": "array", "description": "Query parameters"}
        },
        function=supabase_query
    ),
    Tool(
        name="web_search",
        description="Search the web for recent information not in the knowledge base",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "num_results": {"type": "integer", "default": 5}
        },
        function=web_search
    ),
    Tool(
        name="calculate",
        description="Perform mathematical calculations",
        parameters={
            "expression": {"type": "string", "description": "Math expression"}
        },
        function=safe_eval
    )
]
```

### 2.2 Tool Selection Strategies

```python
# Strategy 1: LLM-based tool selection
TOOL_SELECT_PROMPT = """Given these available tools:
{tool_descriptions}

Which tool(s) should be used for this query?
Query: {query}

Select 1-3 tools in order of priority.
"""

# Strategy 2: Embedding-based tool selection (faster, cheaper)
class EmbeddingToolSelector:
    def __init__(self, tools, embedding_model):
        self.tools = tools
        self.embeddings = {
            tool.name: embedding_model.encode(tool.description)
            for tool in tools
        }

    def select(self, query: str, top_k: int = 2) -> list:
        query_emb = self.embedding_model.encode(query)
        scores = {
            name: cosine_similarity(query_emb, emb)
            for name, emb in self.embeddings.items()
        }
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
```

---

## Part 3: Planning & Reasoning Agents

### 3.1 Query Decomposition

Complex queries need to be broken down before processing.

```python
DECOMPOSE_PROMPT = """Break this complex query into simple, atomic sub-queries.
Each sub-query should be answerable by a single pipeline or tool.

Complex query: {query}

Rules:
- Maximum 5 sub-queries
- Each sub-query must be self-contained (no references to other sub-queries)
- Order matters: earlier results may inform later sub-queries
- Tag each with the most likely pipeline: [STANDARD], [GRAPH], [QUANT]

Output format:
1. [PIPELINE] sub-query text
2. [PIPELINE] sub-query text
"""

class QueryDecomposer:
    async def decompose(self, query: str) -> list:
        response = await self.llm.complete(
            DECOMPOSE_PROMPT.format(query=query)
        )
        return self._parse_steps(response)

    def _parse_steps(self, text: str) -> list:
        import re
        steps = []
        for line in text.strip().split('\n'):
            match = re.match(r'\d+\.\s*\[(\w+)\]\s*(.+)', line)
            if match:
                steps.append({
                    "pipeline": match.group(1),
                    "query": match.group(2)
                })
        return steps
```

### 3.2 Chain-of-Thought Prompting for Agents

```python
COT_AGENT_PROMPT = """You are a RAG research agent. Think step-by-step.

For each step:
1. State what information you need
2. Choose the right tool to get it
3. Analyze the result
4. Decide if you need more information or can answer

CRITICAL RULES:
- Never hallucinate — only use information from tool results
- If a tool returns no results, try rephrasing the query
- If you're unsure, say so — don't make up answers
- Maximum 5 tool calls per query

Query: {query}

Let's solve this step-by-step:
"""
```

### 3.3 HyDE (Hypothetical Document Embeddings) Agent

```python
class HyDEAgent:
    """Generate a hypothetical answer, embed it, then retrieve similar real docs."""

    HYDE_PROMPT = """Write a short, factual paragraph that would be the ideal
    answer to this question. Write as if you're quoting from an authoritative source.

    Question: {query}

    Hypothetical answer:"""

    async def run(self, query: str) -> str:
        # Step 1: Generate hypothetical document
        hypo_doc = await self.llm.complete(
            self.HYDE_PROMPT.format(query=query)
        )

        # Step 2: Embed the hypothetical document
        hypo_embedding = await self.embed(hypo_doc)

        # Step 3: Search with hypothetical embedding (not query embedding)
        results = await self.vector_store.search(
            vector=hypo_embedding,
            top_k=5
        )

        # Step 4: Generate final answer from real retrieved docs
        return await self.generate(query, results)
```

---

## Part 4: Supervisor Hierarchies

### 4.1 Two-Level Hierarchy

```
                    [Supervisor]
                   /     |      \
          [Standard]  [Graph]  [Quant]
           Agent      Agent    Agent
            |           |        |
         Pinecone    Neo4j   Supabase
```

### 4.2 Three-Level Hierarchy (Enterprise)

```
                [Orchestrator]
               /      |       \
        [Domain A]  [Domain B]  [Domain C]
         Supervisor  Supervisor  Supervisor
        /    \       /    \       /    \
     [S1]  [S2]   [S3]  [S4]   [S5]  [S6]
     Agent Agent  Agent Agent  Agent Agent
```

### 4.3 Implementation

```python
class HierarchicalOrchestrator:
    def __init__(self, domain_supervisors: dict):
        self.supervisors = domain_supervisors
        self.router = DomainRouter()

    async def run(self, query: str) -> str:
        # Level 1: Domain routing
        domains = await self.router.classify(query)

        if len(domains) == 1:
            # Single domain — delegate directly
            return await self.supervisors[domains[0]].run(query)

        # Multi-domain — parallel execution + fusion
        results = await asyncio.gather(
            *[self.supervisors[d].run(query) for d in domains]
        )

        return await self._fuse_results(query, dict(zip(domains, results)))
```

---

## Part 5: Production Deployment

### 5.1 n8n Agent Workflow Architecture

```json
{
  "workflow_pattern": "agent_orchestrator_v1",
  "nodes": [
    {
      "type": "webhook",
      "config": {"path": "/agent/query", "method": "POST"}
    },
    {
      "type": "llm_chain",
      "role": "router",
      "model": "llama-3.3-70b",
      "prompt": "Classify query intent..."
    },
    {
      "type": "switch",
      "conditions": ["STANDARD", "GRAPH", "QUANT", "MULTI"]
    },
    {
      "type": "sub_workflow",
      "for_each_pipeline": true,
      "timeout": 30000,
      "retry": 2
    },
    {
      "type": "llm_chain",
      "role": "synthesizer",
      "model": "llama-3.3-70b",
      "prompt": "Combine results..."
    },
    {
      "type": "respond_webhook",
      "format": "json"
    }
  ]
}
```

### 5.2 Error Handling & Retry

```python
class ProductionAgent:
    """Agent with production-grade error handling."""

    async def run(self, query: str) -> dict:
        try:
            result = await asyncio.wait_for(
                self._execute(query),
                timeout=30.0
            )
            return {"status": "success", "answer": result, "latency": self.latency}

        except asyncio.TimeoutError:
            # Fallback to simpler strategy
            return await self._fallback(query)

        except LLMRateLimitError:
            # Switch to backup model
            self.llm = self.backup_llm
            return await self.run(query)

        except RetrievalError as e:
            return {
                "status": "partial",
                "answer": "I found limited information. " + str(e),
                "confidence": 0.3
            }

    async def _fallback(self, query: str) -> dict:
        """Simple vector search + generate when agent times out."""
        docs = await self.vector_store.search(query, top_k=3)
        answer = await self.simple_llm.generate(query, docs)
        return {"status": "fallback", "answer": answer, "confidence": 0.5}
```

### 5.3 Monitoring & Observability

```python
class AgentMonitor:
    def __init__(self):
        self.metrics = {
            "total_queries": 0,
            "avg_latency_ms": 0,
            "tool_usage": defaultdict(int),
            "pipeline_distribution": defaultdict(int),
            "error_rate": 0,
            "fallback_rate": 0,
            "avg_steps_per_query": 0
        }

    def record(self, execution: dict):
        self.metrics["total_queries"] += 1
        self.metrics["avg_latency_ms"] = (
            self.metrics["avg_latency_ms"] * 0.95 +
            execution["latency_ms"] * 0.05  # EMA
        )
        for tool in execution.get("tools_used", []):
            self.metrics["tool_usage"][tool] += 1

        if execution["status"] == "fallback":
            self.metrics["fallback_rate"] = (
                self.metrics["fallback_rate"] * 0.95 + 0.05
            )

    def alert_if_degraded(self):
        if self.metrics["fallback_rate"] > 0.1:
            self._send_alert("High fallback rate: agent may be degraded")
        if self.metrics["avg_latency_ms"] > 5000:
            self._send_alert("High latency: check LLM provider")
```

### 5.4 Cost Control

```python
class CostAwareAgent:
    """Agent that tracks and limits LLM spending."""

    TOKEN_COSTS = {
        "llama-3.3-70b": {"input": 0.0, "output": 0.0},  # Free tier
        "gemma-3-27b": {"input": 0.0, "output": 0.0},     # Free tier
        "gpt-4o": {"input": 2.50, "output": 10.0},        # Per 1M tokens
        "claude-sonnet": {"input": 3.0, "output": 15.0},
    }

    def __init__(self, budget_per_query: float = 0.01):
        self.budget = budget_per_query
        self.spent = 0.0

    async def run(self, query: str) -> str:
        # Start with free models
        self.current_model = "llama-3.3-70b"

        result = await self._execute(query)

        # Only escalate to paid models if free models fail
        if result.confidence < 0.3 and self.spent < self.budget:
            self.current_model = "claude-sonnet"
            result = await self._execute(query)

        return result
```

---

## Part 6: Agent Prompt Templates (40+)

### 6.1 Router Prompts

```
# Template: Intent Router v3
You classify user queries for a multi-pipeline RAG system.

PIPELINE DEFINITIONS:
- STANDARD: General questions, definitions, how-tos, explanations, comparisons
- GRAPH: Questions about relationships, connections, hierarchies, networks, "who works with", "what connects to"
- QUANTITATIVE: Numbers, percentages, financial data, statistics, calculations, "how much", "what percentage"
- ORCHESTRATOR: Multi-part questions requiring information from 2+ pipelines

CLASSIFICATION RULES:
1. If the query mentions specific numbers or asks for calculations → QUANTITATIVE
2. If the query asks about relationships or connections → GRAPH
3. If the query has multiple distinct sub-questions → ORCHESTRATOR
4. Default → STANDARD

Query: {query}
Pipeline:
```

### 6.2 Synthesis Prompts

```
# Template: Multi-Source Synthesizer v2
You are combining results from multiple RAG pipelines into a single answer.

RULES:
- Use information from ALL sources when relevant
- Resolve conflicts by preferring the more specific/detailed source
- If sources contradict, note the discrepancy
- Never add information not present in any source
- Cite which pipeline provided each key fact

SOURCES:
{pipeline_results}

QUESTION: {query}

SYNTHESIZED ANSWER:
```

### 6.3 Critic Prompts

```
# Template: Answer Critic v3
Review this RAG answer for quality issues.

CHECKLIST:
□ Factual accuracy — Every claim is supported by retrieved context
□ Completeness — All parts of the question are addressed
□ Hallucination — No claims beyond what's in the context
□ Relevance — Answer addresses the actual question
□ Coherence — Answer flows logically
□ Specificity — Concrete details, not vague generalities

CONTEXT: {context}
QUESTION: {query}
ANSWER: {answer}

For each checklist item, score 1-5 and explain.
OVERALL: PASS (all ≥ 3) or FAIL (any < 3)
IMPROVEMENTS: [specific changes needed]
```

### 6.4 Query Reformulation Prompts

```
# Template: Query Reformulator v2
Rewrite this query to improve retrieval quality.

TECHNIQUES:
1. Expand acronyms and abbreviations
2. Add relevant synonyms
3. Make implicit context explicit
4. Remove conversational fluff
5. Split compound questions

CONVERSATION HISTORY:
{history}

ORIGINAL QUERY: {query}

REFORMULATED QUERY:
```

### 6.5 Self-Healing Prompts

```
# Template: Self-Healing Agent v1
The previous attempt to answer this query failed or produced low-quality results.

PREVIOUS ATTEMPT:
Query: {query}
Strategy: {previous_strategy}
Error/Issue: {error}

AVAILABLE RECOVERY STRATEGIES:
1. Rephrase query and retry with same pipeline
2. Switch to a different pipeline
3. Decompose into simpler sub-queries
4. Use HyDE (hypothetical document) approach
5. Expand search with broader terms
6. Fall back to web search

Select the best recovery strategy and explain why.
STRATEGY: [number]
MODIFIED QUERY: [if applicable]
```

### 6.6-6.40 Additional Templates

Additional templates included in the ZIP package:
- Entity extraction prompts (3 variants)
- Cypher generation prompts (4 variants)
- SQL generation with safety checks (3 variants)
- Confidence calibration prompts
- Multi-turn conversation prompts
- Domain-specific routing (finance, legal, technical)
- Embedding query expansion
- Answer formatting templates (table, bullet, narrative)
- Guardrail prompts (PII detection, content safety)
- A/B test evaluation prompts
- User feedback integration prompts
- Citation generation prompts
- Summary generation prompts (short, medium, detailed)
- Error explanation prompts (user-facing)

---

## Part 7: n8n Agent Workflows

### 7.1 Workflow: Agent Router (WF-AGENT-001)

Complete n8n workflow for LLM-based query routing:

```json
{
  "name": "Agent Router v1",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "agent-router",
        "httpMethod": "POST",
        "responseMode": "responseNode"
      }
    },
    {
      "name": "Route Query",
      "type": "@n8n/n8n-nodes-langchain.chainLlm",
      "parameters": {
        "prompt": "Classify this query into STANDARD, GRAPH, QUANT, or MULTI:\n\n{{ $json.query }}",
        "model": "meta-llama/llama-3.3-70b-instruct:free"
      }
    },
    {
      "name": "Pipeline Switch",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "rules": [
          {"value": "STANDARD", "output": 0},
          {"value": "GRAPH", "output": 1},
          {"value": "QUANT", "output": 2},
          {"value": "MULTI", "output": 3}
        ]
      }
    }
  ]
}
```

### 7.2-7.12 Additional Workflows

- WF-AGENT-002: ReAct Loop with Tool Calls
- WF-AGENT-003: Plan-and-Execute Pipeline
- WF-AGENT-004: Multi-Pipeline Ensemble
- WF-AGENT-005: Critic and Retry Loop
- WF-AGENT-006: Conversational Memory Agent
- WF-AGENT-007: HyDE Retrieval Agent
- WF-AGENT-008: Self-Healing Pipeline
- WF-AGENT-009: Cost-Aware Router
- WF-AGENT-010: Streaming Agent Response
- WF-AGENT-011: Agent Performance Monitor
- WF-AGENT-012: A/B Test Agent Strategies

---

## Part 8: Debugging Multi-Agent Systems

### 8.1 Common Failure Patterns

| # | Pattern | Symptom | Fix |
|---|---------|---------|-----|
| 1 | Infinite loop | Agent keeps calling same tool | Add max_steps limit + loop detection |
| 2 | Tool hallucination | Agent invents tool that doesn't exist | Strict tool schema validation |
| 3 | Context overflow | Too many tool results fill context | Summarize intermediate results |
| 4 | Routing error | Query sent to wrong pipeline | Improve router prompt + add confidence threshold |
| 5 | Cascading failure | One agent failure breaks orchestrator | Timeout + fallback per agent |
| 6 | Prompt injection via tool | Retrieved doc contains instructions | Sanitize tool outputs |
| 7 | Cost explosion | Agent makes too many paid API calls | Budget tracking per query |
| 8 | Stale context | Memory agent uses outdated info | TTL on memory entries |
| 9 | Conflicting agents | Two agents give contradictory answers | Conflict resolution in synthesizer |
| 10 | Silent degradation | Accuracy drops without alerts | Continuous evaluation sampling |

### 8.2 Debugging Toolkit

```python
class AgentDebugger:
    """Trace and debug agent execution."""

    def __init__(self):
        self.trace = []

    def log_step(self, step_type: str, data: dict):
        self.trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": step_type,  # "think", "act", "observe", "decide"
            "data": data
        })

    def print_trace(self):
        for i, step in enumerate(self.trace):
            print(f"\n{'='*60}")
            print(f"Step {i+1}: [{step['type'].upper()}] @ {step['timestamp']}")
            print(f"{'='*60}")
            for key, value in step['data'].items():
                print(f"  {key}: {str(value)[:200]}")

    def detect_loops(self) -> bool:
        """Detect if agent is stuck in a loop."""
        if len(self.trace) < 4:
            return False

        actions = [s['data'].get('action') for s in self.trace if s['type'] == 'act']
        if len(actions) >= 3 and len(set(actions[-3:])) == 1:
            return True  # Same action repeated 3 times
        return False

    def cost_report(self) -> dict:
        """Calculate total cost of this execution."""
        total_tokens = sum(
            s['data'].get('tokens', 0) for s in self.trace
        )
        total_cost = sum(
            s['data'].get('cost', 0.0) for s in self.trace
        )
        return {
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "num_steps": len(self.trace),
            "num_tool_calls": sum(1 for s in self.trace if s['type'] == 'act')
        }
```

### 8.3 Testing Agents

```python
# Agent evaluation dataset
AGENT_TEST_CASES = [
    {
        "query": "What is the market cap of NVIDIA and how does it compare to AMD?",
        "expected_pipeline": "QUANTITATIVE",
        "expected_tools": ["sql_query"],
        "expected_contains": ["NVIDIA", "AMD", "market cap"]
    },
    {
        "query": "Who are the board members of Tesla and what other companies are they connected to?",
        "expected_pipeline": "GRAPH",
        "expected_tools": ["knowledge_graph_query"],
        "expected_contains": ["Tesla", "board"]
    },
    {
        "query": "Compare the P/E ratios of the top 5 tech companies and explain which sectors they operate in",
        "expected_pipeline": "ORCHESTRATOR",
        "expected_tools": ["sql_query", "vector_search"],
        "expected_contains": ["P/E", "ratio"]
    }
]

async def evaluate_agent(agent, test_cases):
    results = []
    for tc in test_cases:
        result = await agent.run(tc["query"])

        # Check pipeline routing
        correct_pipeline = result.get("pipeline") == tc["expected_pipeline"]

        # Check answer contains expected info
        answer = result.get("answer", "").lower()
        contains_expected = all(
            term.lower() in answer for term in tc["expected_contains"]
        )

        results.append({
            "query": tc["query"],
            "correct_routing": correct_pipeline,
            "contains_expected": contains_expected,
            "latency_ms": result.get("latency_ms")
        })

    accuracy = sum(r["correct_routing"] for r in results) / len(results)
    completeness = sum(r["contains_expected"] for r in results) / len(results)

    return {
        "routing_accuracy": accuracy,
        "completeness": completeness,
        "results": results
    }
```

---

## Appendix A: Decision Matrix — Which Pattern to Use

| Query Type | Best Pattern | Why |
|------------|-------------|-----|
| Simple, single-domain | Router Agent | Lowest latency, 89% accurate |
| Complex, multi-step | Plan-and-Execute | Handles decomposition well |
| Needs reasoning | ReAct | Explicit thought process |
| Multi-domain | Supervisor or Ensemble | Parallel pipeline execution |
| Conversational | Memory Agent | Context across turns |
| High-stakes (finance, legal) | Critic Agent | Self-verification loop |
| Unknown/mixed | Adaptive | Learns best strategy over time |
| Production at scale | Ensemble + Monitor | Reliability + observability |

## Appendix B: Performance Benchmarks

| Pattern | Avg Latency | Accuracy | Cost/Query |
|---------|------------|----------|------------|
| Direct (no agent) | 1.2s | 87.5% | $0.00 |
| Router | 1.5s | 89.2% | $0.00 |
| ReAct (3 steps) | 3.8s | 91.4% | $0.00 |
| Plan-Execute | 5.2s | 92.1% | $0.00 |
| Supervisor | 4.1s | 90.8% | $0.00 |
| Ensemble (3 pipes) | 3.5s | 93.6% | $0.00 |
| Critic (2 rounds) | 6.8s | 94.2% | $0.00 |

*All benchmarks on free-tier LLMs (Llama 3.3 70B, Gemma 3 27B)*

---

**Built from production experience. Not theory — battle-tested patterns from 76+ sessions, 1,100+ commits, and 61,000+ queries.**

© 2026 Nomos AI — Alexis Moret
