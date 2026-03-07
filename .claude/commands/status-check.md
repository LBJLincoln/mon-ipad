Check the full infrastructure status of the Multi-RAG system. Execute ALL checks in parallel where possible:

1. **Pinecone**: Use MCP `describe-index-stats` for `sota-rag-jina-1024` and `website-sectors-jina-1024`
2. **Supabase**: Run SQL counts on `sector_documents`, `sector_financial_tables`, `benchmark_results`
3. **Neo4j**: Use MCP `get-schema` and count total nodes/relationships
4. **HF Spaces**: Test health of N8N_HOST (GET /healthz)
5. **Pipeline webhooks**: Quick POST to each webhook (standard, graph, quant) with a simple query
6. **Running processes**: Check for any background ingestion or eval processes (`ps aux | grep python3`)
7. **Git status**: Show any uncommitted changes
8. **Disk/RAM**: Show available resources

Output a clean summary table with green/red status for each component.
