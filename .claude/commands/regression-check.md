Run a targeted regression check to ensure recent changes haven't broken existing functionality.

Arguments: $ARGUMENTS (optional: "full" for comprehensive, or specific pipeline name)

Steps:
1. **Phase 1 Golden Questions**: Run the original 200 Phase 1 questions (5 per pipeline minimum)
   - Standard: must stay >= 85%
   - Graph: must stay >= 70%
   - Quantitative: must stay >= 85%
2. **Phase 3 Spot Check**: Sample 10 questions from Phase 3 datasets per pipeline
3. **Compare**: Against stored baselines in PROJECT-STATE.md
4. **Flag regressions**: Any accuracy drop > 3pp from baseline
5. **If regression detected**:
   - Identify which dataset/question type regressed
   - Check recent git commits for potential causes
   - Check if any database changes (Pinecone vector count, Supabase rows) correlate
   - Suggest rollback or fix
6. **Output**: Regression report with pass/fail per pipeline and phase
