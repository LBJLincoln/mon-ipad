# RAG Prompt Templates -- 25 Production-Tested Templates

> Drop this file into your CLAUDE.md, .cursorrules, or .github/copilot-instructions.md.
> 25 prompt templates for diagnosing, debugging, and optimizing RAG pipelines.
> Each template tested across 80+ sessions on a production Multi-RAG system handling 61K+ questions.

---

## INSTRUCTIONS FOR AI AGENTS

Use these templates by:
1. Finding the template that matches your task (use the INDEX below)
2. Replacing `{variables}` with actual values
3. Sending to the appropriate LLM or using as internal reasoning structure
4. Following the EXPECTED OUTPUT format for downstream processing

---

## INDEX

| # | Template Name | Category | Use Case |
|---|--------------|----------|----------|
| T01 | Retrieval Failure Diagnosis | Diagnosis | Why did vector search return irrelevant results? |
| T02 | Query-Document Mismatch Analysis | Diagnosis | Analyze semantic gap between query and top results |
| T03 | Pipeline Selection Diagnosis | Diagnosis | Why was the wrong pipeline selected? |
| T04 | Empty Response Root Cause | Diagnosis | Systematic diagnosis of empty/null responses |
| T05 | Rate Limit Impact Assessment | Diagnosis | Determine if 429 errors affected evaluation results |
| T06 | SQL Generation from Schema | SQL RAG | Generate SQL from natural language + schema |
| T07 | SQL Repair | SQL RAG | Fix broken SQL with error context |
| T08 | SQL Result to Natural Language | SQL RAG | Convert raw SQL output to human-readable answer |
| T09 | HyDE Document Generation | Retrieval | Generate hypothetical document for HyDE embedding |
| T10 | Query Expansion | Retrieval | Expand query with synonyms and related terms |
| T11 | Intent Classification | Routing | Classify query type for pipeline routing |
| T12 | Multi-Hop Decomposition | Routing | Break complex query into sub-queries |
| T13 | Reranking Relevance Scoring | Reranking | Score document relevance with explanation |
| T14 | Context Window Optimization | Reranking | Select most relevant passages for LLM context |
| T15 | Entity Extraction for Graph | Graph RAG | Extract named entities from query or document |
| T16 | Community Summary Generation | Graph RAG | Summarize a cluster of related entities |
| T17 | Graph Traversal Query Builder | Graph RAG | Generate Cypher from natural language |
| T18 | Embedding Quality Evaluation | Optimization | Evaluate if embeddings capture query intent |
| T19 | Chunk Size Optimizer | Optimization | Determine optimal chunk size for a corpus |
| T20 | Accuracy Root Cause Analysis | Evaluation | Analyze why accuracy dropped between eval runs |
| T21 | False Negative Detector | Evaluation | Identify evaluation failures caused by matching issues |
| T22 | Pipeline Comparison Report | Evaluation | Compare performance across pipelines |
| T23 | n8n Workflow Node Diagnosis | Infrastructure | Analyze n8n execution data to find failing node |
| T24 | Credential and Config Audit | Infrastructure | Verify all credentials and config are correct |
| T25 | Production Readiness Checklist | Infrastructure | Pre-deployment verification |

---

## DIAGNOSIS TEMPLATES

### T01: Retrieval Failure Diagnosis

**Purpose**: Systematically diagnose why vector search returned irrelevant results for a given query.

**Variables**: `{query}`, `{top_results}`, `{expected_answer}`, `{embedding_model}`, `{index_name}`

```
You are a RAG retrieval specialist. Diagnose why this vector search failed.

QUERY: {query}

TOP 5 RESULTS RETURNED (with similarity scores):
{top_results}

EXPECTED ANSWER: {expected_answer}

EMBEDDING MODEL: {embedding_model}
INDEX: {index_name}

Analyze systematically:
1. VOCABULARY GAP: Does the query use different terminology than the documents?
2. SEMANTIC DRIFT: Are the results topically related but answering a different question?
3. CHUNK BOUNDARY: Could the answer span multiple chunks that were split apart?
4. NAMESPACE ISSUE: Is the query searching the correct namespace/partition?
5. EMBEDDING QUALITY: Is the query type well-suited to this embedding model?
6. DATA COVERAGE: Does the index actually contain documents with the answer?

For each issue found, provide:
- DIAGNOSIS: What went wrong
- EVIDENCE: Which result(s) demonstrate the problem
- FIX: Specific actionable solution
- PRIORITY: HIGH/MEDIUM/LOW

Output as structured analysis.
```

**Expected output**: Structured diagnosis with ranked fixes.

---

### T02: Query-Document Mismatch Analysis

**Purpose**: Analyze the semantic gap between a query and its retrieved documents to improve retrieval.

**Variables**: `{query}`, `{retrieved_doc}`, `{relevance_score}`, `{expected_doc_keywords}`

```
Analyze the semantic gap between this query and retrieved document.

QUERY: {query}
RETRIEVED DOCUMENT (score: {relevance_score}):
{retrieved_doc}

EXPECTED KEYWORDS IN IDEAL DOCUMENT: {expected_doc_keywords}

Analysis tasks:
1. List the KEY CONCEPTS in the query
2. List the KEY CONCEPTS in the document
3. Identify OVERLAPPING concepts (why it was retrieved)
4. Identify MISSING concepts (why it's not the right answer)
5. Suggest QUERY REFORMULATIONS that would retrieve the right document
6. Suggest DOCUMENT ENRICHMENT that would make the right document rank higher

Output format:
- OVERLAP_SCORE: 0-100 (conceptual overlap percentage)
- MISSING_CONCEPTS: [list]
- REFORMULATED_QUERIES: [list of 3 alternative queries]
- ENRICHMENT_SUGGESTIONS: [list of metadata/content additions]
```

---

### T03: Pipeline Selection Diagnosis

**Purpose**: Determine why the orchestrator routed a query to the wrong pipeline.

**Variables**: `{query}`, `{selected_pipeline}`, `{correct_pipeline}`, `{classification_output}`

```
The orchestrator routed this query to the wrong pipeline. Diagnose why.

QUERY: {query}
SELECTED PIPELINE: {selected_pipeline}
CORRECT PIPELINE: {correct_pipeline}
CLASSIFIER OUTPUT: {classification_output}

Analysis:
1. What SIGNALS in the query suggest {selected_pipeline}?
2. What SIGNALS in the query suggest {correct_pipeline}?
3. Which signals are STRONGER and why did the classifier get confused?
4. Is this an AMBIGUOUS query (legitimately hard to classify)?
5. What CLASSIFICATION RULE would correctly handle this query?

Provide:
- ROOT_CAUSE: Why the misclassification happened
- FIX_TYPE: "prompt_update" | "feature_addition" | "threshold_change" | "training_data"
- SPECIFIC_FIX: Exact change to make
- TEST_QUERIES: 3 similar queries to verify the fix doesn't regress
```

---

### T04: Empty Response Root Cause

**Purpose**: Systematic diagnosis when a RAG pipeline returns an empty or null response.

**Variables**: `{query}`, `{pipeline}`, `{http_status}`, `{response_body}`, `{execution_time_ms}`

```
A RAG pipeline returned an empty response. Diagnose the root cause.

QUERY: {query}
PIPELINE: {pipeline}
HTTP STATUS: {http_status}
RESPONSE BODY: {response_body}
EXECUTION TIME: {execution_time_ms}ms

Check each failure point in order:

1. WEBHOOK LAYER
   - Status 404? --> Webhook not registered or wrong path
   - Status 500? --> Internal error (check error message)
   - Status 200 but empty? --> Workflow completed but returned nothing

2. RETRIEVAL LAYER
   - Did vector search return results? (empty namespace, wrong index)
   - Did graph query return results? (disconnected entities)
   - Did SQL query return results? (wrong tenant_id, wrong filter)

3. LLM LAYER
   - Did LLM call succeed? (429 rate limit, timeout)
   - Did LLM return valid format? (markdown instead of JSON)
   - Did LLM return "I don't know"? (insufficient context)

4. RESPONSE LAYER
   - Is "Respond to Webhook" node present in workflow?
   - Is executeWorkflow used with respondToWebhook sub-workflow?
   - Is response serialization correct? (object vs string)

For each layer, output:
- STATUS: OK | SUSPECT | FAILED
- EVIDENCE: What indicates this status
- NEXT_STEP: What to check or fix
```

---

### T05: Rate Limit Impact Assessment

**Purpose**: Determine how many evaluation failures were caused by rate limits vs actual pipeline issues.

**Variables**: `{eval_results}`, `{total_questions}`, `{failure_count}`, `{error_messages}`

```
Analyze evaluation results to separate rate-limit failures from real pipeline failures.

TOTAL QUESTIONS: {total_questions}
FAILURE COUNT: {failure_count}
FAILURE RATE: {failure_count}/{total_questions}

ERROR MESSAGES FROM FAILURES:
{error_messages}

Classification rules:
- RATE_LIMIT: Contains "429", "rate limit", "too many requests", "quota exceeded"
- TIMEOUT: Contains "timeout", "ETIMEDOUT", "ESOCKETTIMEDOUT", execution_time > 90s
- LLM_ERROR: Contains "unable to generate", "no response", model returned empty
- PIPELINE_ERROR: Actual wrong answer, incorrect SQL, wrong entity, bad retrieval
- INFRASTRUCTURE: Contains "502", "503", "connection refused", "ECONNRESET"

For each failure, classify into one of the above categories.

Output:
- REAL_FAILURES: count (pipeline actually got the answer wrong)
- INFRASTRUCTURE_FAILURES: count (pipeline never had a chance to answer)
- ADJUSTED_ACCURACY: (total - infrastructure_failures - real_failures) / (total - infrastructure_failures)
- RECOMMENDATION: Should this eval be re-run? Which questions need retry?
```

---

## SQL RAG TEMPLATES

### T06: SQL Generation from Schema

**Purpose**: Generate PostgreSQL SQL from a natural language question and database schema.

**Variables**: `{question}`, `{schema}`, `{sample_rows}`, `{tenant_id}`

```
You are a PostgreSQL SQL expert. Generate a query to answer this question.

DATABASE SCHEMA:
{schema}

SAMPLE DATA (first 3 rows per table):
{sample_rows}

IMPORTANT RULES:
1. Use ILIKE '%keyword%' for text matching, NEVER exact '=' for names
2. ALWAYS include: WHERE tenant_id = '{tenant_id}'
3. Available periods: 'FY' (full year), 'Q1', 'Q2', 'Q3', 'Q4'
4. Fiscal years available: 2020, 2021, 2022, 2023
5. SELECT only -- no INSERT, UPDATE, DELETE, DROP, ALTER
6. Include LIMIT clause for safety
7. Use explicit column names, never SELECT *

QUESTION: {question}

Output ONLY valid JSON:
{{"sql": "SELECT ...", "explanation": "brief explanation of query logic"}}
```

**Example usage**:
```
QUESTION: "What was TechVision's revenue in 2023?"

Expected output:
{"sql": "SELECT revenue FROM financials WHERE company_name ILIKE '%techvision%' AND fiscal_year = 2023 AND period = 'FY' AND tenant_id = 'benchmark' LIMIT 1", "explanation": "Fetching annual revenue for TechVision in fiscal year 2023"}
```

---

### T07: SQL Repair

**Purpose**: Fix broken SQL using the error message and original intent.

**Variables**: `{original_sql}`, `{error_message}`, `{schema}`, `{original_question}`

```
The following SQL query failed. Fix it.

ORIGINAL QUESTION: {original_question}

FAILED SQL:
{original_sql}

ERROR MESSAGE:
{error_message}

DATABASE SCHEMA:
{schema}

Common fixes to consider:
- Column name typo: verify against schema
- Table name wrong: check available tables
- Missing quotes around string values
- Wrong data type comparison (numeric vs text)
- Missing tenant_id filter
- Period format wrong ('FY' vs '2023' vs 'FY 2023')
- ILIKE pattern missing % wildcards

Output ONLY valid JSON:
{{"sql": "SELECT ...", "fix_applied": "description of what was wrong and how it was fixed"}}
```

---

### T08: SQL Result to Natural Language

**Purpose**: Convert raw SQL query results into a natural language answer.

**Variables**: `{question}`, `{sql_query}`, `{sql_result}`, `{column_descriptions}`

```
Convert this SQL result into a natural language answer.

ORIGINAL QUESTION: {question}

SQL QUERY USED:
{sql_query}

RAW RESULT:
{sql_result}

COLUMN DESCRIPTIONS:
{column_descriptions}

Rules:
1. Answer the question directly and concisely
2. Include the specific numbers from the result
3. Format large numbers readably (e.g., $6.745 billion, not 6745000000)
4. Include units and currency where applicable
5. If result is empty, say "No data found for this query"
6. Mention the company name, time period, and metric for context
7. Do NOT explain the SQL query
8. Do NOT add information not in the result

Answer:
```

---

### T09: HyDE Document Generation

**Purpose**: Generate a hypothetical document that would answer the query, for HyDE embedding.

**Variables**: `{query}`, `{domain}`

```
Generate a short passage (100-150 words) that would be a perfect answer to this question. Write as if this passage exists in a {domain} knowledge base.

QUESTION: {query}

Requirements:
- Write in the style of an authoritative reference document
- Include specific details, names, and numbers where plausible
- Use terminology that would appear in real {domain} documents
- Do NOT start with "The answer is..." -- write as if it's part of a larger document
- Keep it focused and factual

Passage:
```

**Why this works**: The hypothetical document shares vocabulary with real documents in the index, bridging the query-document semantic gap. The embedding of this passage will be closer to the actual answer document than the embedding of the short question.

---

## RETRIEVAL TEMPLATES

### T10: Query Expansion

**Purpose**: Expand a user query with synonyms, related terms, and alternative phrasings to improve retrieval recall.

**Variables**: `{query}`, `{domain}`

```
Expand this search query with related terms to improve retrieval from a {domain} knowledge base.

ORIGINAL QUERY: {query}

Generate:
1. SYNONYMS: Alternative words for key terms (3-5)
2. RELATED_TERMS: Conceptually related terms not in the query (3-5)
3. ALTERNATIVE_PHRASINGS: Different ways to ask the same question (3)
4. DOMAIN_JARGON: Technical terms from {domain} that relate to this query (2-3)

Output as JSON:
{{
  "original": "{query}",
  "synonyms": ["..."],
  "related_terms": ["..."],
  "alternative_phrasings": ["..."],
  "domain_jargon": ["..."],
  "expanded_query": "combined query using the most useful expansions"
}}
```

---

## ROUTING TEMPLATES

### T11: Intent Classification

**Purpose**: Classify a user query to route it to the correct RAG pipeline.

**Variables**: `{query}`

```
Classify this question into exactly one category.

CATEGORIES:
- FACTUAL: Asks for facts, definitions, explanations, descriptions, "what is", "who is", "explain"
- QUANTITATIVE: Asks for specific numbers, metrics, financial data, comparisons, trends, "how much", "what percentage", "compare revenue"
- RELATIONAL: Asks about connections, relationships, networks, "related to", "connected", "who works with", "partners of"
- MULTI_HOP: Requires combining information from multiple sources or reasoning steps, "what is X and how does it relate to Y"

QUESTION: {query}

Analysis:
1. Key signal words: [list them]
2. Primary intent: [what the user wants to know]
3. Data type needed: [text/numbers/relationships]

Output JSON:
{{"category": "FACTUAL|QUANTITATIVE|RELATIONAL|MULTI_HOP", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}
```

---

### T12: Multi-Hop Decomposition

**Purpose**: Break a complex multi-hop question into sequential sub-queries.

**Variables**: `{query}`

```
This question requires multiple steps to answer. Decompose it into sequential sub-queries.

COMPLEX QUESTION: {query}

For each sub-query, specify:
1. The sub-question to answer
2. Which pipeline to use (standard/graph/quantitative)
3. What information from previous steps is needed
4. How this step's result feeds into the final answer

Output JSON:
{{
  "original_question": "{query}",
  "steps": [
    {{
      "step": 1,
      "sub_query": "...",
      "pipeline": "standard|graph|quantitative",
      "depends_on": [],
      "output_needed": "what this step produces for later steps"
    }},
    {{
      "step": 2,
      "sub_query": "...",
      "pipeline": "...",
      "depends_on": [1],
      "output_needed": "..."
    }}
  ],
  "final_synthesis": "How to combine step outputs into the final answer"
}}
```

---

## RERANKING TEMPLATES

### T13: Reranking Relevance Scoring

**Purpose**: Score document relevance to a query with detailed explanation (for debugging reranker behavior).

**Variables**: `{query}`, `{document}`, `{rank_position}`

```
Score the relevance of this document to the query.

QUERY: {query}

DOCUMENT (current rank: #{rank_position}):
{document}

Scoring criteria:
1. TOPICAL_RELEVANCE (0-25): Does the document discuss the same topic as the query?
2. ANSWER_PRESENCE (0-25): Does the document contain the actual answer?
3. SPECIFICITY (0-25): Does the document address the specific aspect asked about?
4. RECENCY (0-25): Is the information current and applicable? (if temporal aspect exists)

Output:
{{
  "topical_relevance": {{"score": 0-25, "reason": "..."}},
  "answer_presence": {{"score": 0-25, "reason": "..."}},
  "specificity": {{"score": 0-25, "reason": "..."}},
  "recency": {{"score": 0-25, "reason": "..."}},
  "total_score": 0-100,
  "should_be_in_top_5": true|false,
  "ideal_rank": 1-20
}}
```

---

### T14: Context Window Optimization

**Purpose**: Select the most relevant passages from retrieved documents to maximize answer quality within the LLM context window.

**Variables**: `{query}`, `{retrieved_passages}`, `{max_tokens}`

```
Select and order the most relevant passages for answering this query within a {max_tokens} token budget.

QUERY: {query}

RETRIEVED PASSAGES (ranked by retrieval score):
{retrieved_passages}

Selection criteria:
1. Does this passage contain part of the answer? (REQUIRED for inclusion)
2. Does this passage provide context needed to understand the answer?
3. Does this passage contradict or complement other selected passages?
4. What is the marginal information gain of including this passage?

For each passage, decide:
- INCLUDE (contains answer or critical context)
- MAYBE (useful context but not essential)
- EXCLUDE (redundant, off-topic, or exceeds budget)

Output:
{{
  "selected_passages": [
    {{"passage_id": "...", "reason": "...", "token_count": N}}
  ],
  "excluded_passages": [
    {{"passage_id": "...", "reason": "..."}}
  ],
  "total_tokens_used": N,
  "coverage_assessment": "Does the selected context contain enough information to answer the query?"
}}
```

---

## GRAPH RAG TEMPLATES

### T15: Entity Extraction for Graph

**Purpose**: Extract named entities from text for knowledge graph construction or graph-based retrieval.

**Variables**: `{text}`, `{entity_types}`

```
Extract named entities from this text for knowledge graph construction.

TEXT:
{text}

ENTITY TYPES TO EXTRACT:
{entity_types}

For each entity, provide:
- NAME: Canonical form (e.g., "TechVision Inc" not "TechVision" or "the company")
- TYPE: From the entity types list
- ALIASES: Other forms used in the text
- RELATIONSHIPS: Connections to other entities mentioned

Output JSON:
{{
  "entities": [
    {{
      "name": "...",
      "type": "...",
      "aliases": ["..."],
      "context_sentence": "the sentence where this entity appears"
    }}
  ],
  "relationships": [
    {{
      "source": "entity_name_1",
      "target": "entity_name_2",
      "type": "WORKS_FOR|PARTNER_OF|LOCATED_IN|SUBSIDIARY_OF|...",
      "evidence": "text supporting this relationship"
    }}
  ]
}}
```

---

### T16: Community Summary Generation

**Purpose**: Generate a summary of an entity cluster (community) in a knowledge graph.

**Variables**: `{community_entities}`, `{community_relationships}`, `{community_id}`

```
Summarize this community of related entities from a knowledge graph.

COMMUNITY ID: {community_id}

ENTITIES IN COMMUNITY:
{community_entities}

RELATIONSHIPS WITHIN COMMUNITY:
{community_relationships}

Generate a 2-4 sentence summary that:
1. Identifies the THEME connecting these entities
2. Highlights the most IMPORTANT entities and why
3. Describes the KEY RELATIONSHIPS that define this community
4. Uses language that would help a search query match this community

Summary:
```

---

### T17: Graph Traversal Query Builder

**Purpose**: Generate a Cypher query from a natural language question about entity relationships.

**Variables**: `{question}`, `{node_labels}`, `{relationship_types}`, `{sample_data}`

```
Generate a Neo4j Cypher query to answer this relationship question.

QUESTION: {question}

AVAILABLE NODE LABELS:
{node_labels}

AVAILABLE RELATIONSHIP TYPES:
{relationship_types}

SAMPLE DATA:
{sample_data}

Rules:
1. Use CONTAINS for text matching (case-insensitive: toLower())
2. Limit results: RETURN ... LIMIT 10
3. Use path patterns for multi-hop: (a)-[*1..3]-(b)
4. Return meaningful properties, not just node IDs
5. Use OPTIONAL MATCH for relationships that may not exist

Output:
{{
  "cypher": "MATCH ...",
  "explanation": "What this query does and why",
  "expected_result_format": "Description of what the results will look like"
}}
```

---

## OPTIMIZATION TEMPLATES

### T18: Embedding Quality Evaluation

**Purpose**: Evaluate whether current embeddings are capturing the semantic intent of queries.

**Variables**: `{query_samples}`, `{embedding_model}`, `{top_results_per_query}`, `{expected_answers}`

```
Evaluate embedding quality for these query-result pairs.

EMBEDDING MODEL: {embedding_model}

QUERY-RESULT PAIRS:
{query_samples}

EXPECTED ANSWERS:
{expected_answers}

For each query, assess:
1. Is the correct document in top-5? top-10? top-20?
2. What is the similarity score of the correct document vs the top result?
3. What type of query fails most? (factual, numerical, relational, multi-hop)
4. Are there consistent vocabulary gaps?

Overall assessment:
- EMBEDDING_FIT: GOOD (>80% correct in top-5) | MODERATE (50-80%) | POOR (<50%)
- TOP_FAILURE_PATTERN: The most common reason for retrieval failure
- RECOMMENDED_ACTIONS:
  a. Switch embedding model?
  b. Add HyDE?
  c. Add query expansion?
  d. Improve chunking?
  e. Add metadata filtering?
  f. Fine-tune embeddings?
```

---

### T19: Chunk Size Optimizer

**Purpose**: Determine the optimal chunk size for a specific corpus based on sample analysis.

**Variables**: `{corpus_description}`, `{sample_documents}`, `{current_chunk_size}`, `{retrieval_accuracy}`

```
Analyze this corpus to recommend optimal chunk size.

CORPUS: {corpus_description}
CURRENT CHUNK SIZE: {current_chunk_size} tokens
CURRENT RETRIEVAL ACCURACY: {retrieval_accuracy}

SAMPLE DOCUMENTS:
{sample_documents}

Analysis factors:
1. INFORMATION DENSITY: How much useful info per paragraph?
   - Dense (technical docs, legal) --> smaller chunks (256-512 tokens)
   - Sparse (narratives, reports) --> larger chunks (512-1024 tokens)

2. ANSWER SPAN: How many tokens does a typical answer occupy?
   - Short answers (<50 tokens) --> smaller chunks for precision
   - Long answers (100+ tokens) --> larger chunks to avoid splitting

3. CONTEXT DEPENDENCY: Do sentences require surrounding context?
   - High (pronouns, references) --> larger chunks or late chunking
   - Low (self-contained paragraphs) --> smaller chunks OK

4. STRUCTURE: Does the document have natural break points?
   - Headers/sections --> split by section
   - Tables --> keep table as single chunk
   - Lists --> keep list as single chunk

Recommendation:
{{
  "recommended_chunk_size": N,
  "recommended_overlap": N,
  "splitting_strategy": "paragraph|section|sentence|fixed",
  "special_handling": ["tables: keep whole", "code: keep whole", etc.],
  "expected_accuracy_improvement": "+X%",
  "reasoning": "..."
}}
```

---

## EVALUATION TEMPLATES

### T20: Accuracy Root Cause Analysis

**Purpose**: Analyze why RAG accuracy dropped between evaluation runs.

**Variables**: `{run_a_results}`, `{run_b_results}`, `{changes_between_runs}`, `{pipeline}`

```
Accuracy dropped between two evaluation runs. Analyze the root cause.

PIPELINE: {pipeline}
RUN A (before): {run_a_results}
RUN B (after): {run_b_results}
CHANGES MADE BETWEEN RUNS: {changes_between_runs}

Analysis steps:
1. REGRESSION IDENTIFICATION: Which specific questions changed from PASS to FAIL?
2. PATTERN DETECTION: Do the regressions share a common trait? (topic, question type, complexity)
3. CHANGE ATTRIBUTION: Can each regression be attributed to a specific change?
4. IMPROVEMENT CHECK: Did any questions change from FAIL to PASS? (was there a tradeoff?)
5. INFRASTRUCTURE CHECK: Were any failures due to rate limits, timeouts, or infra issues?

Output:
{{
  "accuracy_delta": "X% --> Y% (delta: -Z%)",
  "regressions": [
    {{"question_id": "...", "likely_cause": "...", "change_responsible": "..."}}
  ],
  "improvements": [
    {{"question_id": "...", "likely_cause": "..."}}
  ],
  "root_cause": "The primary reason for the accuracy drop",
  "recommendation": "REVERT | FIX_FORWARD | ACCEPTABLE_TRADEOFF",
  "specific_fix": "If FIX_FORWARD, what to do"
}}
```

---

### T21: False Negative Detector

**Purpose**: Identify evaluation failures that are false negatives (the answer is correct but the matcher rejected it).

**Variables**: `{question}`, `{expected_answer}`, `{actual_response}`, `{match_result}`

```
Determine if this evaluation failure is a false negative (correct answer rejected by matcher).

QUESTION: {question}
EXPECTED ANSWER: {expected_answer}
ACTUAL RESPONSE: {actual_response}
MATCH RESULT: {match_result}

Check for these false negative patterns:
1. NUMBER FORMAT: "6.7 billion" vs "6,745,000,000" vs "$6.745B"
2. UNIT VARIATION: "15%" vs "15 percent" vs "0.15"
3. SYNONYM: "revenue" vs "total sales" vs "top-line income"
4. PRECISION: "approximately 6.7 billion" vs "6,745,231,000"
5. EXTRA CONTEXT: Answer contains the expected value but also additional correct information
6. LANGUAGE: Answer in different language but correct
7. ORDERING: Multi-part answer with elements in different order

Output:
{{
  "is_false_negative": true|false,
  "pattern": "NUMBER_FORMAT|UNIT_VARIATION|SYNONYM|PRECISION|EXTRA_CONTEXT|LANGUAGE|ORDERING|GENUINE_FAILURE",
  "explanation": "Why this is/isn't a false negative",
  "suggested_matcher_improvement": "How to update the matcher to handle this case"
}}
```

---

### T22: Pipeline Comparison Report

**Purpose**: Generate a structured comparison of pipeline performance across an evaluation run.

**Variables**: `{pipeline_results}`, `{question_categories}`, `{evaluation_label}`

```
Generate a pipeline comparison report from these evaluation results.

EVALUATION: {evaluation_label}
RESULTS BY PIPELINE:
{pipeline_results}

QUESTION CATEGORIES:
{question_categories}

Report structure:

1. OVERALL ACCURACY TABLE
   | Pipeline | Total | Pass | Fail | Accuracy | Avg Latency |

2. ACCURACY BY CATEGORY
   | Category | Standard | Graph | Quantitative | Best Pipeline |

3. FAILURE ANALYSIS
   - Most common failure mode per pipeline
   - Questions that ALL pipelines got wrong (data gap?)
   - Questions where only ONE pipeline succeeded (routing opportunity)

4. RECOMMENDATIONS
   - Which pipeline should handle which category?
   - Where is the biggest improvement opportunity?
   - What changes would have the highest impact?

Output as structured markdown.
```

---

## INFRASTRUCTURE TEMPLATES

### T23: n8n Workflow Node Diagnosis

**Purpose**: Analyze n8n execution data to identify the failing node in a pipeline.

**Variables**: `{execution_data}`, `{workflow_name}`, `{expected_behavior}`

```
Analyze this n8n workflow execution to find the failure point.

WORKFLOW: {workflow_name}
EXPECTED BEHAVIOR: {expected_behavior}

EXECUTION DATA (node-by-node):
{execution_data}

For each node, check:
1. Did it receive input? (empty input = upstream failure)
2. Did it execute? (skipped = condition not met)
3. Did it produce expected output? (wrong format = node config issue)
4. Did it error? (check error type and message)
5. Did it timeout? (check execution time vs expected)

Find the FIRST node that deviated from expected behavior.

Output:
{{
  "failing_node": "node_name",
  "failure_type": "NO_INPUT|WRONG_OUTPUT|ERROR|TIMEOUT|SKIPPED",
  "error_details": "...",
  "upstream_cause": "If the failure is caused by an upstream node, which one?",
  "fix_suggestion": "Specific action to fix this node",
  "nodes_checked": N
}}
```

---

### T24: Credential and Config Audit

**Purpose**: Verify all credentials and configuration are correct before deployment.

**Variables**: `{required_credentials}`, `{env_vars}`, `{service_endpoints}`

```
Audit the configuration for a RAG pipeline deployment.

REQUIRED CREDENTIALS:
{required_credentials}

ENVIRONMENT VARIABLES SET:
{env_vars}

SERVICE ENDPOINTS:
{service_endpoints}

Check each item:

1. CREDENTIALS
   - Is each required credential present?
   - Does the credential format match expected pattern? (sk-or-v1-..., pcsk_..., jina_...)
   - Are there expired or exhausted credentials?
   - Are there duplicate credentials that might cause conflicts?

2. ENVIRONMENT VARIABLES
   - N8N_BLOCK_ENV_ACCESS_IN_NODE=false set? (CRITICAL for n8n 2.8+)
   - All LLM model variables set?
   - Database connection strings correct?
   - API base URLs include full path? (e.g., /chat/completions)

3. SERVICE CONNECTIVITY
   - Can each endpoint be reached? (suggest curl commands)
   - Are rate limits known for each service?
   - Are fallback options configured?

Output:
{{
  "status": "READY|ISSUES_FOUND|BLOCKING_ISSUES",
  "critical_issues": ["..."],
  "warnings": ["..."],
  "verification_commands": ["curl commands to test each service"]
}}
```

---

### T25: Production Readiness Checklist

**Purpose**: Pre-deployment verification for a RAG pipeline going to production.

**Variables**: `{pipeline_name}`, `{deployment_target}`, `{eval_results}`, `{infrastructure_status}`

```
Evaluate production readiness for this RAG pipeline deployment.

PIPELINE: {pipeline_name}
TARGET: {deployment_target}
LATEST EVAL RESULTS: {eval_results}
INFRASTRUCTURE STATUS: {infrastructure_status}

Checklist (mark PASS/FAIL/SKIP for each):

ACCURACY
[ ] Accuracy >= target threshold on 50+ questions
[ ] No regression from previous deployment
[ ] False negative rate analyzed and acceptable
[ ] Edge cases documented and handled

RELIABILITY
[ ] Rate limit handling configured (retry + backoff + rotation)
[ ] Timeout values appropriate for pipeline type
[ ] Error handling returns useful messages (not [object Object])
[ ] neverError=true on all external HTTP calls

SECURITY
[ ] No credentials in workflow JSON
[ ] No credentials in git history
[ ] Tenant isolation enforced (WHERE tenant_id = ...)
[ ] SQL injection prevented (SELECT-only validation)

INFRASTRUCTURE
[ ] N8N_BLOCK_ENV_ACCESS_IN_NODE=false set
[ ] Correct credential IDs mapped
[ ] Webhook path verified against registry
[ ] Health check endpoint responding
[ ] Stuck execution cleanup procedure documented

MONITORING
[ ] Execution logging enabled
[ ] Error alerting configured
[ ] Rate limit monitoring active
[ ] Latency tracking in place

Output:
{{
  "ready_for_production": true|false,
  "blocking_items": ["..."],
  "risk_items": ["..."],
  "accepted_risks": ["..."],
  "deployment_command": "..."
}}
```

---

## USAGE TIPS

### Chaining Templates

Templates can be chained for complex workflows:

```
1. T11 (Intent Classification) --> determines pipeline
2. T06 (SQL Generation) --> if quantitative
3. T07 (SQL Repair) --> if SQL fails
4. T08 (Result Interpretation) --> convert to natural language
```

```
1. T01 (Retrieval Failure Diagnosis) --> identifies the problem
2. T10 (Query Expansion) --> generates better query
3. T09 (HyDE Generation) --> creates hypothetical document
4. T14 (Context Window Optimization) --> selects best passages
```

### Template Customization

Adapt these templates to your specific domain by:
- Replacing schema examples with your actual database schema
- Adding domain-specific entity types to T15
- Adjusting scoring criteria in T13 for your relevance definition
- Adding your pipeline names and webhook paths to T11 and T03

---

## META

**Source**: 80+ development sessions on a production Multi-RAG orchestrator (2025-2026).
**Templates tested**: Each template used in production debugging and optimization workflows.
**Pipelines covered**: Standard (vector), Graph (knowledge graph), Quantitative (SQL), Orchestrator (meta-routing).
**Price**: $27 -- AI Agent Context Kit.
