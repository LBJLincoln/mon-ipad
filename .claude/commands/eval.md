Run a quick evaluation smoke test on the RAG pipelines.

Arguments: $ARGUMENTS (optional: pipeline name like "standard", "graph", "quantitative", or "all")

Steps:
1. Run `source .env.local`
2. Run `python3 eval/quick-test.py --questions 5 --pipelines ${ARGUMENTS:-standard,graph,quantitative}`
3. If any pipeline scores below 50%, run a deeper check with `--questions 10` on that specific pipeline
4. Report results in a summary table: pipeline | questions | correct | accuracy | avg latency
5. Compare with Phase 3 baselines: Standard 87.5%, Graph 40.9%, Quantitative 95.2%
6. Flag any regressions (accuracy drop > 5pp vs baseline)
