Maintain and improve the DEBUG-PLAYBOOK fix catalog.

Arguments: $ARGUMENTS (optional: "add" to add a new fix, "analyze" to find patterns, "clean" to deduplicate)

Steps:
1. **Read current catalog**: `technicals/DEBUG-PLAYBOOK.md`
2. **If "analyze"**:
   - Count fixes by category (infrastructure, rate-limit, workflow, data, LLM)
   - Identify recurring patterns (fixes that were applied multiple times)
   - Find gaps: common error types not yet documented
   - Suggest preventive measures for top 5 recurring issues
3. **If "add"**:
   - Ask for: symptom, root cause, fix applied, confidence level
   - Generate the next FIX-XX entry
   - Insert into the correct section of DEBUG-PLAYBOOK
   - Cross-reference with similar existing fixes
4. **If "clean"**:
   - Find duplicate or overlapping fixes
   - Merge related fixes into consolidated entries
   - Update cross-references
   - Remove obsolete fixes (for issues that no longer exist)
5. **Auto-detect**: Check recent eval logs for new error patterns not in the catalog
6. **Output**: Summary of changes made + catalog health score (% of known errors documented)
