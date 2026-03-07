Start a new work session. Execute ALL of the following steps:

1. Read `directives/PROJECT-STATE.md` (current state)
2. Read first 100 lines of `technicals/DEBUG-PLAYBOOK.md` (diagnostic reference)
3. Run `source .env.local` to load environment variables
4. Check pipeline health: call each webhook with a simple test query (standard, graph, quantitative)
5. Check database status: Pinecone describe-index-stats, Supabase count queries, Neo4j schema
6. Summarize: what's working, what's broken, what's the next priority
7. Output a concise session brief with the current state and recommended actions
