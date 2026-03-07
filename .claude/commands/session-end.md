End the current session properly. Execute ALL steps in order:

1. Check for any running background processes and wait or report them
2. Run `python3 eval/generate_status.py` to update dashboard data
3. Update `directives/PROJECT-STATE.md` with session achievements:
   - What was accomplished
   - Current pipeline accuracies
   - Database counts (Pinecone vectors, Supabase rows, Neo4j nodes)
   - Next session TODO
4. Git add all changed files (but NOT .env.local or credentials)
5. Create a commit with message: "Session XX: [summary of achievements]"
6. Push to origin main
7. Run `bash scripts/push-directives.sh` to sync CLAUDE.md to satellite repos
8. Output a final session summary for the user
