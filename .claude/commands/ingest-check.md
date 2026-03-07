Check the status of any running ingestion processes.

Steps:
1. Check for running Python ingestion processes: `ps aux | grep -E 'ingest|phase4' | grep -v grep`
2. If log files exist in `logs/`, show the last 10 lines of each
3. Check Pinecone index stats (MCP describe-index-stats for sota-rag-jina-1024)
4. Check Supabase counts (sector_documents, sector_financial_tables)
5. Compare current counts with expected targets
6. Estimate completion time based on log progress rates
7. Report: what's running, progress %, ETA, any errors
