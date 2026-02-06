#!/usr/bin/env python3
"""
Fix Graph RAG and Quantitative RAG workflow JSONs.

Graph RAG: Split Response Formatter into Context Builder + HTTP Request node + Answer Formatter
  - This fixes the 404 error from using $vars.OPENROUTER_API_KEY in Code nodes
  - Uses predefined openRouterApi credential (same as HyDE node) via HTTP Request node

Quantitative RAG: Fix error handling so workflow doesn't crash
  - SQL Validator: wrap in try/catch, never throw
  - Response Formatter: handle both success and error path inputs
"""

import json
import copy
import os

REPO = "/home/user/mon-ipad"

# ============================================================
# FIX 1: GRAPH RAG
# ============================================================
def fix_graph_rag():
    path = os.path.join(REPO, "TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json")
    with open(path) as f:
        wf = json.load(f)

    # --- Step 1: Replace Response Formatter code (now acts as Context Builder) ---
    new_context_builder_code = r"""// Context Builder — Prepares prompt for LLM answer synthesis
// Uses HTTP Request node with openRouterApi credential (not Code node httpRequest)
const ctx = $json.budgeted_context || {};
const query = $node['OTEL Init'].json.query;
const traceId = $node['OTEL Init'].json.trace_id;

// Build context string from all retrieved sources
const contextParts = [];

// Reranked docs (highest quality)
if (ctx.reranked && ctx.reranked.length > 0) {
  const rerankedText = ctx.reranked.slice(0, 5).map((d, i) => {
    const content = typeof d === 'string' ? d : (d.document || d.content || d.text || '');
    return `[Doc ${i+1}] ${content}`;
  }).filter(Boolean).join('\n');
  if (rerankedText) contextParts.push('=== Top Relevant Documents ===\n' + rerankedText);
}

// Graph relationships
if (ctx.relationships) {
  contextParts.push('=== Graph Relationships ===\n' + ctx.relationships);
}

// Graph paths
if (ctx.graph && ctx.graph.length > 0) {
  const graphText = ctx.graph.slice(0, 5).map(g => g.content || g.text || '').filter(Boolean).join('\n');
  if (graphText) contextParts.push('=== Graph Context ===\n' + graphText);
}

// Community summaries
if (ctx.community && ctx.community.length > 0) {
  const commText = ctx.community.slice(0, 3).map(c => c.content || c.text || '').filter(Boolean).join('\n');
  if (commText) contextParts.push('=== Community Summaries ===\n' + commText);
}

// Vector results
if (ctx.vector && ctx.vector.length > 0) {
  const vecText = ctx.vector.slice(0, 3).map(v => v.content || v.text || '').filter(Boolean).join('\n');
  if (vecText) contextParts.push('=== Vector Results ===\n' + vecText);
}

const fullContext = contextParts.join('\n\n');

// Build LLM request body (will be sent by HTTP Request node with proper credentials)
const userContent = fullContext.trim()
  ? `Question: ${query}\n\nContext:\n${fullContext}`
  : `Question: ${query}\n\nNo relevant context was found in the knowledge graph. Please indicate that no information is available.`;

const requestBody = {
  model: 'google/gemini-2.0-flash-exp',
  messages: [
    {
      role: 'system',
      content: 'You are a precise RAG answer generator. Using ONLY the provided context, answer the user question concisely and accurately. Reply in the SAME LANGUAGE as the question. If the context does not contain enough information, say so. Do NOT add information beyond what is in the context. Be concise: answer in 1-3 sentences when possible.'
    },
    { role: 'user', content: userContent }
  ],
  temperature: 0.2,
  max_tokens: 500
};

return [{ json: {
  requestBody,
  trace_id: traceId,
  query,
  tokens_used: $json.tokens_used || 0,
  traversal_depth: $json.traversal_depth || 0,
  context_sources: contextParts.length
} }];
"""

    for node in wf["nodes"]:
        if node["name"] == "Response Formatter" and node["type"] == "n8n-nodes-base.code":
            node["parameters"]["jsCode"] = new_context_builder_code
            print("  [Graph RAG] Updated Response Formatter -> Context Builder")
            break

    # --- Step 2: Add LLM Answer Synthesis HTTP Request node ---
    llm_node = {
        "parameters": {
            "method": "POST",
            "url": "={{ $vars.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1/chat/completions' }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "openRouterApi",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.requestBody) }}",
            "options": {
                "timeout": 25000
            }
        },
        "id": "a1b2c3d4-llm-answer-synthesis",
        "name": "LLM Answer Synthesis",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.3,
        "position": [2080, 6304],
        "credentials": {
            "openRouterApi": {
                "id": "aTHBqnntMBApo0Dy",
                "name": "OpenRouter account"
            }
        }
    }
    wf["nodes"].append(llm_node)
    print("  [Graph RAG] Added LLM Answer Synthesis HTTP Request node")

    # --- Step 3: Add Answer Formatter Code node ---
    answer_formatter_code = r"""// Extract LLM answer and format final response
const answer = $json.choices?.[0]?.message?.content || 'No answer generated';
const contextData = $node['Response Formatter'].json;

return [{ json: {
  status: 'SUCCESS',
  trace_id: contextData.trace_id || '',
  response: answer,
  metadata: {
    source: 'graph_rag_llm_synthesis',
    tokens_used: contextData.tokens_used || 0,
    traversal_depth: contextData.traversal_depth || 0,
    context_sources: contextData.context_sources || 0
  }
} }];
"""
    answer_node = {
        "parameters": {
            "jsCode": answer_formatter_code
        },
        "id": "e5f6g7h8-answer-formatter",
        "name": "Answer Formatter",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2280, 6304]
    }
    wf["nodes"].append(answer_node)
    print("  [Graph RAG] Added Answer Formatter Code node")

    # --- Step 4: Update connections ---
    # Change: Response Formatter → Shield #9 becomes Response Formatter → LLM Answer Synthesis
    wf["connections"]["Response Formatter"] = {
        "main": [[{
            "node": "LLM Answer Synthesis",
            "type": "main",
            "index": 0
        }]]
    }
    # Add: LLM Answer Synthesis → Answer Formatter
    wf["connections"]["LLM Answer Synthesis"] = {
        "main": [[{
            "node": "Answer Formatter",
            "type": "main",
            "index": 0
        }]]
    }
    # Add: Answer Formatter → Shield #9: Export Trace
    wf["connections"]["Answer Formatter"] = {
        "main": [[{
            "node": "Shield #9: Export Trace",
            "type": "main",
            "index": 0
        }]]
    }
    print("  [Graph RAG] Updated connections: RF → LLM → AF → Shield#9")

    with open(path, "w") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"  [Graph RAG] Saved to {path}")


# ============================================================
# FIX 2: QUANTITATIVE RAG
# ============================================================
def fix_quantitative_rag():
    path = os.path.join(REPO, "TEST - SOTA 2026 - WF4 Quantitative V2.0 (1).json")
    with open(path) as f:
        wf = json.load(f)

    # --- Step 1: Fix SQL Validator - wrap in try/catch, never throw ---
    new_sql_validator_code = r"""// CRITICAL: SQL Validator - Security Shield (ERROR-SAFE VERSION)
// Never throws - returns error data that flows through pipeline
const contextData = $node['Schema Context Builder'].json;

try {
  let llmResponse = {};
  try {
    llmResponse = JSON.parse($json.choices?.[0]?.message?.content || '{}');
  } catch (e) {
    // LLM returned invalid JSON - return safe fallback
    return {
      ...contextData,
      validated_sql: "SELECT 'SQL_GENERATION_ERROR: Invalid LLM response' as error_message, 'error' as status WHERE tenant_id = '" + contextData.user_context.tenant_id + "' LIMIT 1",
      explanation: 'LLM returned invalid JSON response',
      validation_status: 'FAILED',
      validation_error: 'SQL_GENERATION_ERROR',
      validation_timestamp: new Date().toISOString()
    };
  }

  const sql = String(llmResponse.sql || '').trim();
  const sqlUpper = sql.toUpperCase();

  // FORBIDDEN PATTERNS - P0 Security
  const forbiddenPatterns = [
    /DELETE|UPDATE|INSERT|DROP|TRUNCATE|ALTER|CREATE/i,
    /GRANT|REVOKE|EXEC|EXECUTE|CALL/i,
    /--|;.*;|UNION.*SELECT/i,
    /xp_|sp_|pg_sleep/i,
    /\bINTO\s+OUTFILE\b|\bLOAD_FILE\b/i
  ];

  for (const pattern of forbiddenPatterns) {
    if (pattern.test(sqlUpper)) {
      return {
        ...contextData,
        validated_sql: "SELECT 'SQL_INJECTION_DETECTED' as error_message, 'error' as status WHERE tenant_id = '" + contextData.user_context.tenant_id + "' LIMIT 1",
        explanation: 'Forbidden SQL pattern detected',
        validation_status: 'FAILED',
        validation_error: 'SQL_INJECTION_DETECTED',
        validation_timestamp: new Date().toISOString()
      };
    }
  }

  // REQUIRED PATTERNS - return error instead of throwing
  if (!sqlUpper.startsWith('SELECT')) {
    return {
      ...contextData,
      validated_sql: "SELECT 'Query must start with SELECT' as error_message, 'error' as status WHERE tenant_id = '" + contextData.user_context.tenant_id + "' LIMIT 1",
      explanation: 'Query must start with SELECT',
      validation_status: 'FAILED',
      validation_error: 'SQL_VALIDATION_ERROR',
      validation_timestamp: new Date().toISOString()
    };
  }

  // Add LIMIT if missing (instead of throwing)
  let finalSql = llmResponse.sql;
  if (!sqlUpper.includes('LIMIT')) {
    finalSql = finalSql + ' LIMIT 1000';
  }

  // Extract LIMIT value
  const limitMatch = sqlUpper.match(/LIMIT\s+(\d+)/i);
  if (limitMatch) {
    const limitValue = parseInt(limitMatch[1]);
    if (limitValue > 1000) {
      finalSql = finalSql.replace(/LIMIT\s+\d+/i, 'LIMIT 1000');
    }
  }

  // Check tenant_id filter - add if missing (instead of throwing)
  if (!sqlUpper.includes('TENANT_ID')) {
    // Try to add tenant_id filter
    if (sqlUpper.includes('WHERE')) {
      finalSql = finalSql.replace(/WHERE/i, `WHERE tenant_id = '${contextData.user_context.tenant_id}' AND`);
    } else if (sqlUpper.includes('FROM')) {
      finalSql = finalSql.replace(/(FROM\s+\w+)/i, `$1 WHERE tenant_id = '${contextData.user_context.tenant_id}'`);
    }
  }

  // Passed validation
  return {
    ...contextData,
    validated_sql: finalSql,
    explanation: llmResponse.explanation || '',
    validation_status: 'PASSED',
    validation_timestamp: new Date().toISOString()
  };

} catch (globalError) {
  // Catch-all: never let the node crash
  return {
    ...contextData,
    validated_sql: "SELECT 'VALIDATOR_ERROR: " + String(globalError.message).replace(/'/g, "''").substring(0, 100) + "' as error_message, 'error' as status LIMIT 1",
    explanation: 'Validator encountered an unexpected error: ' + globalError.message,
    validation_status: 'FAILED',
    validation_error: 'VALIDATOR_CRASH',
    validation_timestamp: new Date().toISOString()
  };
}
"""

    for node in wf["nodes"]:
        if node["name"] == "SQL Validator (Shield #1)":
            node["parameters"]["jsCode"] = new_sql_validator_code
            print("  [Quant RAG] Fixed SQL Validator - error-safe version")
            break

    # --- Step 2: Fix Response Formatter to handle both success and error paths ---
    new_response_formatter_code = r"""// Response Formatter - handles both success and error paths
// May receive data from Interpretation Layer (success) or Needs SQL Repair? (error)
let aggregatorData = {};
let initData = {};
let interpretation = '';

// Try to get Init & ACL data (always available)
try {
  initData = $node['Init & ACL'].json || {};
} catch (e) {
  initData = {};
}

// Try to get Result Aggregator data (only on success path)
try {
  aggregatorData = $node['Result Aggregator'].json || {};
} catch (e) {
  aggregatorData = {};
}

// Determine interpretation based on input source
// On success path: $json comes from Interpretation Layer (has choices)
// On error path: $json comes from Needs SQL Repair? (has error/fallback_message)
if ($json.choices?.[0]?.message?.content) {
  interpretation = $json.choices[0].message.content;
} else if ($json.error || $json.fallback_message) {
  // Coming from error path
  interpretation = $json.fallback_message || 'Unable to generate SQL query for this question. Error: ' + ($json.error || 'unknown');
} else {
  interpretation = 'No interpretation available';
}

return {
  status: aggregatorData.validation_status === 'PASSED' ? 'SUCCESS' : 'ERROR',
  trace_id: aggregatorData.trace_id || initData.trace_id || '',
  query: aggregatorData.query || initData.query || '',
  sql_executed: aggregatorData.validated_sql || '',
  result_count: aggregatorData.result_count || 0,
  interpretation: interpretation,
  raw_results: aggregatorData.has_results ? (aggregatorData.sql_results || []) : [],
  metadata: {
    validation_status: aggregatorData.validation_status || 'UNKNOWN',
    timestamp: new Date().toISOString(),
    engine: 'QUANTITATIVE'
  }
};
"""

    for node in wf["nodes"]:
        if node["name"] == "Response Formatter" and node["type"] == "n8n-nodes-base.code":
            node["parameters"]["jsCode"] = new_response_formatter_code
            print("  [Quant RAG] Fixed Response Formatter - handles error paths")
            break

    # --- Step 3: Fix Result Aggregator to handle error inputs from SQL Executor ---
    new_result_aggregator_code = r"""// Prepare data for interpretation - handles both success and error from SQL Executor
let validatorData = {};
try {
  validatorData = $node['SQL Validator (Shield #1)'].json || {};
} catch (e) {
  validatorData = {};
}

const inputItems = $input.all();
const sqlResults = [];

for (const item of inputItems) {
  // Check if this is an error item
  if (item.json && !item.json.error && !item.json.errorMessage) {
    sqlResults.push(item.json);
  }
}

if (sqlResults.length === 0) {
  return {
    ...validatorData,
    sql_results: [],
    result_count: 0,
    has_results: false
  };
}

return {
  ...validatorData,
  sql_results: sqlResults,
  result_count: sqlResults.length,
  has_results: true,
  result_preview: JSON.stringify(sqlResults.slice(0, 5), null, 2)
};
"""

    for node in wf["nodes"]:
        if node["name"] == "Result Aggregator":
            node["parameters"]["jsCode"] = new_result_aggregator_code
            print("  [Quant RAG] Fixed Result Aggregator - handles error inputs")
            break

    with open(path, "w") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"  [Quant RAG] Saved to {path}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  FIXING WORKFLOW JSONs")
    print("=" * 60)

    print("\n--- Graph RAG V3.3 ---")
    fix_graph_rag()

    print("\n--- Quantitative V2.0 ---")
    fix_quantitative_rag()

    print("\n" + "=" * 60)
    print("  DONE - Both workflows fixed")
    print("=" * 60)
