Run a comprehensive monitoring pass on the Multi-RAG system. Detect problems, suggest fixes, and auto-apply known solutions.

Steps:
1. **Pipeline Health**: Call each webhook (standard, graph, quant) with a test query. Record latency and error status.
2. **Database Health**: Check Pinecone vector counts, Supabase row counts, Neo4j node counts.
3. **Symptom Detection**: Compare results against known patterns in `technicals/DEBUG-PLAYBOOK.md`:
   - "[object Object]" in responses → Pattern 5.2
   - HTML in responses → FIX-35
   - "Query must start with SELECT" → Rate limit or bad SQL
   - Empty responses → FIX-34
   - 404 → Webhook not registered
   - 500 → Credential or env var issue
4. **Auto-Fix**: For symptoms with confidence > 90% (exact match in DEBUG-PLAYBOOK), apply the documented fix automatically and retest.
5. **Accuracy Check**: Run 3 known-good questions per pipeline. Compare with baseline (Std 87.5%, Graph 40.9%, Quant 95.2%).
6. **Quota Check**: Test Jina API connectivity, check Pinecone capacity (% used), estimate remaining eval budget.
7. **Report**: Output structured report with:
   - Status per component (OK/WARN/FAIL)
   - Any auto-fixes applied
   - Recommended manual actions
   - Comparison vs last session's metrics
