#!/usr/bin/env python3
"""
Deploy benchmark workflows to n8n.

Usage:
    python3 scripts/deploy-benchmark-workflows.py --all
    python3 scripts/deploy-benchmark-workflows.py --workflow supabase
    python3 scripts/deploy-benchmark-workflows.py --workflow neo4j
    python3 scripts/deploy-benchmark-workflows.py --workflow pinecone
    python3 scripts/deploy-benchmark-workflows.py --workflow unified

Requirements:
    - N8N_API_KEY environment variable set
    - PINECONE_API_KEY environment variable set
"""

import json
import os
import sys
import argparse
from urllib import request, error

N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

WORKFLOWS = {
    "supabase": {
        "file": "workflows/benchmarks/supabase-introspection-v1.json",
        "name": "BENCHMARK - Supabase Introspection & Manager V1.0",
        "description": "Complete PostgreSQL database administration and introspection"
    },
    "neo4j": {
        "file": "workflows/benchmarks/neo4j-introspection-v1.json",
        "name": "BENCHMARK - Neo4j Introspection & Manager V1.0",
        "description": "Complete Neo4j graph database administration and introspection"
    },
    "pinecone": {
        "file": "workflows/benchmarks/pinecone-introspection-v1.json",
        "name": "BENCHMARK - Pinecone Introspection & Manager V1.0",
        "description": "Complete Pinecone vector database administration and introspection"
    },
    "unified": {
        "file": "workflows/benchmarks/unified-db-dashboard-v1.json",
        "name": "BENCHMARK - Unified Database Dashboard V1.0",
        "description": "Cross-database dashboard for unified monitoring"
    }
}


def n8n_api(method, path, body=None):
    """Call n8n REST API."""
    url = f"{N8N_HOST}/api/v1{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }
    
    req = request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except error.HTTPError as e:
        body = e.read().decode()[:500] if e.fp else ""
        print(f"  HTTP Error {e.code}: {body}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def list_existing_workflows():
    """List existing workflows to check for duplicates."""
    result = n8n_api("GET", "/workflows")
    if result and "data" in result:
        return {wf.get("name", ""): wf["id"] for wf in result["data"]}
    return {}


def deploy_workflow(key, existing_workflows, dry_run=False):
    """Deploy a single workflow."""
    config = WORKFLOWS[key]
    filepath = config["file"]
    
    print(f"\n{'='*60}")
    print(f"Deploying: {config['name']}")
    print(f"{'='*60}")
    
    # Load workflow file
    try:
        with open(filepath) as f:
            workflow_data = json.load(f)
    except FileNotFoundError:
        print(f"  ERROR: File not found: {filepath}")
        return False
    except json.JSONDecodeError as e:
        print(f"  ERROR: Invalid JSON: {e}")
        return False
    
    # Check if workflow already exists
    if config["name"] in existing_workflows:
        existing_id = existing_workflows[config["name"]]
        print(f"  Workflow already exists (ID: {existing_id})")
        print(f"  Use n8n UI to delete it first, or this will create a duplicate")
    
    if dry_run:
        print(f"  [DRY RUN] Would deploy workflow with {len(workflow_data.get('nodes', []))} nodes")
        return True
    
    # Clean up for import (remove IDs)
    for node in workflow_data.get("nodes", []):
        if "id" in node:
            del node["id"]
        # Ensure credentials are referenced by name
        if "credentials" in node:
            for cred_type, cred in node["credentials"].items():
                if isinstance(cred, dict) and "id" in cred:
                    # Keep credential reference
                    pass
    
    # Deploy
    print(f"  Importing workflow ({len(workflow_data.get('nodes', []))} nodes)...")
    result = n8n_api("POST", "/workflows", workflow_data)
    
    if result and "id" in result:
        print(f"  ✓ Successfully deployed!")
        print(f"  Workflow ID: {result['id']}")
        print(f"  Webhook URL: {N8N_HOST}/webhook/{workflow_data['nodes'][0]['parameters']['path']}")
        
        # Activate workflow
        wf_id = result["id"]
        activate_result = n8n_api("POST", f"/workflows/{wf_id}/activate")
        if activate_result:
            print(f"  ✓ Workflow activated")
        else:
            print(f"  ⚠ Could not activate workflow automatically")
        
        return True
    else:
        print(f"  ✗ Deployment failed")
        return False


def main():
    parser = argparse.ArgumentParser(description="Deploy benchmark workflows to n8n")
    parser.add_argument("--all", action="store_true", help="Deploy all workflows")
    parser.add_argument("--workflow", choices=list(WORKFLOWS.keys()), help="Deploy specific workflow")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't deploy")
    args = parser.parse_args()
    
    if not N8N_API_KEY:
        print("ERROR: N8N_API_KEY environment variable not set")
        print(f"  export N8N_API_KEY='your-api-key'")
        sys.exit(1)
    
    print("="*60)
    print("BENCHMARK WORKFLOWS DEPLOYMENT")
    print("="*60)
    print(f"Target: {N8N_HOST}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    
    # Get existing workflows
    print("\nChecking existing workflows...")
    existing = list_existing_workflows()
    print(f"Found {len(existing)} existing workflows")
    
    # Determine which workflows to deploy
    if args.all:
        to_deploy = list(WORKFLOWS.keys())
    elif args.workflow:
        to_deploy = [args.workflow]
    else:
        print("\nNo workflow specified. Use --all or --workflow <name>")
        print(f"Available workflows: {', '.join(WORKFLOWS.keys())}")
        sys.exit(1)
    
    # Deploy
    results = []
    for key in to_deploy:
        success = deploy_workflow(key, existing, args.dry_run)
        results.append((key, success))
    
    # Summary
    print("\n" + "="*60)
    print("DEPLOYMENT SUMMARY")
    print("="*60)
    for key, success in results:
        status = "✓" if success else "✗"
        print(f"  {status} {WORKFLOWS[key]['name']}")
    
    total = len(results)
    success_count = sum(1 for _, s in results if s)
    print(f"\nTotal: {success_count}/{total} workflows deployed successfully")
    
    if not args.dry_run and success_count > 0:
        print("\nNext steps:")
        print("  1. Go to n8n UI → Settings → Credentials")
        print("  2. Configure credentials for:")
        print("     - Supabase (Postgres)")
        print("     - Neo4j")
        print("     - Pinecone (HTTP Header)")
        print("  3. Test the workflows using the webhook URLs")
        print("\nDocumentation: docs/technical/benchmark-workflows-guide.md")


if __name__ == "__main__":
    main()
