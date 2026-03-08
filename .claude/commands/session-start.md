Start a new work session. Execute ALL of the following steps:

1. **Kill zombies**: Check `pgrep -a claude` for old sessions. Kill any that aren't the current session. Check `free -m` for RAM.
2. Read `directives/PROJECT-STATE.md` (current state)
3. Read first 100 lines of `technicals/DEBUG-PLAYBOOK.md` (diagnostic reference)
4. Run `source .env.local` to load environment variables
5. **Environment detection**: If on Codespace (`/workspaces/` exists), check Claude Code installed (`which claude`), check node/python versions. If anything missing, install it.
6. Check pipeline health: call each webhook with a simple test query (standard, graph, quantitative) — use 90s timeout (pipelines are slow)
7. Check database status: Pinecone describe-index-stats, Supabase count queries, Neo4j schema
8. Check Codespace status: `gh cs list` to see which are running
9. Check HF Spaces health: curl each Space /healthz
10. **Launch session monitor**: Start a background agent that watches the session and auto-documents fixes to DEBUG-PLAYBOOK.md
11. Summarize: what's working, what's broken, what's the next priority
12. Output a concise session brief with the current state and recommended actions
