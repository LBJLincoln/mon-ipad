Target a 10% improvement in the weakest metric this session. This skill implements a structured improvement cycle.

Steps:
1. **Baseline**: Read current metrics from PROJECT-STATE.md and docs/status.json
2. **Identify weakest metric**: Find the pipeline with the largest gap to its target:
   - Standard: current vs 85% target
   - Graph: current vs 70% target
   - Quantitative: current vs 85% target
   - Or: infrastructure metric (latency, uptime, data coverage)
3. **Research applicable technique**: Check PROJECT-ROADMAP.md Section 2 and 6 for:
   - Techniques rated GOLD (high impact + quick win)
   - Cross-pipeline improvements that help multiple pipelines
4. **Plan the improvement**:
   - What to change (specific node, prompt, config)
   - Expected impact (pp or %)
   - Risk assessment (could it cause regressions?)
   - Rollback plan
5. **Measure BEFORE**: Run quick-test with 5-10 questions on the target pipeline
6. **Implement**: Apply ONE change only (never multiple changes at once)
7. **Measure AFTER**: Run the same test again
8. **Compare**: Calculate actual improvement vs expected
9. **Document**: Update PROJECT-STATE with the result
10. **If improvement < 2pp**: Revert and try the next technique in the priority list
11. **If improvement >= 2pp**: Commit, push, celebrate
