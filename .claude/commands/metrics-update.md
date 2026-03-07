Centralize and update all project metrics in a single pass.

Steps:
1. **Database Metrics** (parallel):
   - Pinecone: describe-index-stats for all indexes (sota-rag-jina-1024, website-sectors-jina-1024)
   - Supabase: count all key tables (sector_documents, sector_financial_tables, benchmark_results)
   - Neo4j: count total nodes and relationships
2. **Pipeline Metrics**:
   - Read latest eval results from `docs/data.json`
   - Extract accuracy per pipeline per phase
   - Calculate trends (improving/declining/stable)
3. **Infrastructure Metrics**:
   - HF Space health (test each space in N8N_ALL_HOSTS)
   - Jina API connectivity + estimated remaining quota
   - VM disk and RAM usage
4. **Error Metrics**:
   - Count fixes in DEBUG-PLAYBOOK (total documented)
   - Top 5 most frequent error patterns from recent evals
5. **Output**:
   - Update `docs/status.json` with fresh data
   - Print a dashboard-style summary with all metrics
   - Flag any metric that regressed vs last session
6. **Trend Analysis**:
   - Compare current vs 3 sessions ago
   - Identify which pipeline improved most/least
   - Suggest where to focus next session
