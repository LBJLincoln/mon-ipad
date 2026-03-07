Synchronize state and improvements across all 7 repos. This is the cross-repo orchestration skill.

Steps:
1. **Read current state**: `directives/PROJECT-STATE.md`
2. **Check each repo status** (git log, last commit, pending changes):
   - mon-ipad (this repo): eval scripts, directives, skills
   - rag-data-ingestion: ingestion scripts, datasets
   - rag-tests: test datasets, results
   - rag-website: Next.js site, chatbots
   - rag-dashboard: metrics display
   - rag-pme-connectors: PME apps
3. **Identify stale repos**: Any repo not updated in > 5 sessions
4. **Push directives**: Run `bash scripts/push-directives.sh` to sync CLAUDE.md to all satellites
5. **Check CI/CD**: Verify GitHub Actions status for each repo
6. **Dependency check**: Verify that repos waiting on data (rag-website waiting on ingestion) are unblocked
7. **Output**: Cross-repo health matrix showing each repo's status, last update, and blocking issues
