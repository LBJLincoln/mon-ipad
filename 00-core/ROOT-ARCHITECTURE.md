# Root Architecture (Target: 7 folders)

Updated: 2026-02-27T16:10:00Z

## Target folders
- 00-core
- 01-pipelines
- 02-products
- 03-data
- 04-observability
- 05-automation
- 06-alexis-assistant

## Migration policy
- Phase A (now): create canonical structure + mapping docs + non-breaking operation.
- Phase B (after validation): physically move legacy dirs into target folders and update script paths.

## Legacy mapping (planned)
- directives, technicals, docs -> 00-core
- n8n, hf-space, eval -> 01-pipelines
- website*, dashboard -> 02-products
- datasets, db, outputs -> 03-data
- logs, snapshot, n8n_analysis_results -> 04-observability
- scripts, mcp, config, node_modules -> 05-automation
- shared strategic docs -> 06-alexis-assistant
