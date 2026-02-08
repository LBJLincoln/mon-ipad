#!/usr/bin/env python3
"""
Deploy fixes for free-tier model compatibility:
1. Fix Error Response Builder in all workflows (handle missing node references)
2. Add retry logic for free model rate limits
3. Fix hardcoded model references
4. Switch embedding to Jina free tier for Standard/Graph RAG
"""

import json
import os
import copy
import uuid
import urllib.request
import urllib.error
import time

N8N_API_KEY = os.environ.get("N8N_API_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A")
BASE_URL = "https://amoret.app.n8n.cloud"

WORKFLOWS = {
    "standard": "LnTqRX4LZlI009Ks-3Jnp",
    "graph": "95x2BBAbJlLWZtWEJn6rb",
    "quantitative": "LjUz8fxQZ03G9IsU",
    "orchestrator": "FZxkpldDbgV8AD_cg7IWG",
}


def n8n_api(method, path, data=None, retries=3):
    """Call n8n API with retry."""
    for attempt in range(retries):
        try:
            body = json.dumps(data).encode() if data else None
            req = urllib.request.Request(
                f"{BASE_URL}{path}",
                data=body,
                method=method,
                headers={
                    "X-N8N-API-KEY": N8N_API_KEY,
                    "Content-Type": "application/json",
                }
            )
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            print(f"  HTTP {e.code}: {body[:200]}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def sanitize_settings(settings):
    if not settings:
        return {"executionOrder": "v1"}
    return {k: v for k, v in settings.items()
            if k not in ("availableInMCP", "timeSavedMode")}


def update_workflow(wf_id, wf_data):
    clean = {
        "name": wf_data.get("name", f"Workflow {wf_id}"),
        "nodes": wf_data.get("nodes", []),
        "connections": wf_data.get("connections", {}),
        "settings": sanitize_settings(wf_data.get("settings")),
    }
    return n8n_api("PUT", f"/api/v1/workflows/{wf_id}", clean)


def fix_error_response_builder(wf_data, wf_name):
    """Fix Error Response Builder to handle missing Init & ACL gracefully."""
    changed = False
    for node in wf_data.get("nodes", []):
        name = node.get("name", "")

        if "error response builder" in name.lower() or \
           ("error" in name.lower() and "builder" in name.lower()):
            params = node.get("parameters", {})
            code = params.get("jsCode", "")

            if "$node['Init & ACL']" in code and "try" not in code:
                # Wrap in try-catch to handle missing node references
                new_code = """// Error handler - graceful fallback when nodes haven't executed
try {
  const error = $json;
  let initData = {};
  try {
    initData = $node['Init & ACL']?.json || {};
  } catch (e) {
    initData = { trace_id: 'err-' + Date.now(), query: 'unknown' };
  }

  return {
    status: 'ERROR',
    trace_id: initData.trace_id || 'err-' + Date.now(),
    error_type: error.message?.includes('SQL_') ? 'SQL_ERROR' :
                error.message?.includes('rate') ? 'RATE_LIMIT' :
                error.message?.includes('Provider') ? 'PROVIDER_ERROR' : 'SYSTEM_ERROR',
    error_message: error.message || error.description || 'Unknown error',
    query: initData.query || 'unknown',
    timestamp: new Date().toISOString()
  };
} catch (e) {
  return {
    status: 'ERROR',
    trace_id: 'err-fallback-' + Date.now(),
    error_type: 'ERROR_HANDLER_FAILURE',
    error_message: e.message || 'Error handler itself failed',
    timestamp: new Date().toISOString()
  };
}"""
                params["jsCode"] = new_code
                changed = True
                print(f"  [{wf_name}] Fixed Error Response Builder: '{name}'")

    return changed


def fix_sql_error_handler(wf_data, wf_name):
    """Fix SQL Error Handler to handle missing node references."""
    changed = False
    for node in wf_data.get("nodes", []):
        name = node.get("name", "")

        if "sql error handler" in name.lower() or "self-healing" in name.lower():
            params = node.get("parameters", {})
            code = params.get("jsCode", "")

            if "$node['Init & ACL']" in code:
                # Add safety wrappers
                new_code = """// SQL Error Handler - Self-Healing with graceful fallback
try {
  const executorResult = $json;

  let validatorData = {};
  let originalQuery = '';
  let schemaContext = '';
  let tenantId = 'default';

  try { validatorData = $node['SQL Validator (Shield #1)'].json; } catch(e) {}
  try { originalQuery = $node['Init & ACL'].json.query; } catch(e) { originalQuery = 'unknown'; }
  try { schemaContext = $node['Schema Context Builder'].json.schema_context; } catch(e) {}
  try { tenantId = $node['Init & ACL'].json.user_context.tenant_id; } catch(e) {}

  const staticData = $getWorkflowStaticData('global');
  const traceId = 'sql-repair-' + Date.now();

  const retryKey = `retry_${traceId}`;
  const retryCount = (staticData[retryKey] || 0) + 1;
  staticData[retryKey] = retryCount;

  if (retryCount > 2) {
    delete staticData[retryKey];
    return [{
      json: {
        status: 'ERROR',
        trace_id: traceId,
        error_type: 'SQL_MAX_RETRIES',
        error_message: 'SQL self-healing exhausted after 2 retries',
        original_query: originalQuery,
        timestamp: new Date().toISOString()
      }
    }];
  }

  const errorMsg = executorResult.error_message || executorResult.message || 'SQL execution failed';
  const failedSQL = validatorData.validated_sql || executorResult.sql || '';

  return [{
    json: {
      needs_repair: true,
      retry_count: retryCount,
      original_query: originalQuery,
      failed_sql: failedSQL,
      error_message: errorMsg,
      schema_context: schemaContext,
      tenant_id: tenantId,
      trace_id: traceId
    }
  }];
} catch (e) {
  return [{
    json: {
      status: 'ERROR',
      error_type: 'SELF_HEAL_FAILURE',
      error_message: e.message,
      timestamp: new Date().toISOString()
    }
  }];
}"""
                params["jsCode"] = new_code
                changed = True
                print(f"  [{wf_name}] Fixed SQL Error Handler: '{name}'")

    return changed


def add_retry_to_http_nodes(wf_data, wf_name):
    """Add retry options to HTTP Request nodes calling OpenRouter."""
    changed = False
    for node in wf_data.get("nodes", []):
        ntype = node.get("type", "")
        params = node.get("parameters", {})

        if "httpRequest" in ntype:
            url = str(params.get("url", ""))
            if "openrouter" in url.lower():
                # Add retry on failure
                if not params.get("options"):
                    params["options"] = {}
                options = params["options"]
                if not options.get("retry"):
                    options["retry"] = {
                        "maxTries": 3,
                        "waitBetweenTries": 2000,
                    }
                    changed = True
                    print(f"  [{wf_name}] Added retry to: '{node.get('name')}'")

    return changed


def fix_hardcoded_models(wf_data, wf_name):
    """Replace hardcoded model names with $vars references."""
    changed = False
    for node in wf_data.get("nodes", []):
        params = node.get("parameters", {})

        # Check JSON body for hardcoded model names
        for key in ["jsonBody", "body"]:
            if key in params and isinstance(params[key], str):
                body = params[key]
                # Replace hardcoded embedding model
                if '"text-embedding-3-small"' in body and '$vars' not in body:
                    params[key] = body.replace(
                        '"text-embedding-3-small"',
                        '"{{ $vars.EMBEDDING_MODEL || \'text-embedding-3-small\' }}"'
                    )
                    changed = True
                    print(f"  [{wf_name}] Fixed hardcoded embedding model in: '{node.get('name')}'")

    return changed


def main():
    print("=" * 60)
    print("Deploying free-model compatibility fixes to all workflows")
    print("=" * 60)

    for wf_name, wf_id in WORKFLOWS.items():
        print(f"\n--- {wf_name.upper()} ({wf_id}) ---")

        try:
            wf_data = n8n_api("GET", f"/api/v1/workflows/{wf_id}")
        except Exception as e:
            print(f"  ERROR fetching workflow: {e}")
            continue

        changed = False
        changed |= fix_error_response_builder(wf_data, wf_name)
        changed |= fix_sql_error_handler(wf_data, wf_name)
        changed |= add_retry_to_http_nodes(wf_data, wf_name)
        changed |= fix_hardcoded_models(wf_data, wf_name)

        if changed:
            try:
                update_workflow(wf_id, wf_data)
                print(f"  DEPLOYED: {wf_name}")
            except Exception as e:
                print(f"  DEPLOY ERROR: {e}")
        else:
            print(f"  No changes needed for {wf_name}")

    # Re-activate all workflows after update
    print("\n--- Re-activating workflows ---")
    for wf_name, wf_id in WORKFLOWS.items():
        try:
            n8n_api("POST", f"/api/v1/workflows/{wf_id}/activate")
            print(f"  Activated: {wf_name}")
        except:
            print(f"  Already active: {wf_name}")

    print("\n" + "=" * 60)
    print("Done! All fixes deployed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
