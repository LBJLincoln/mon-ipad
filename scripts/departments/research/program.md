# Department: RESEARCH (D1)

## Mission
Continuously scan academic papers, GitHub repos, and Kaggle kernels to discover, extract, and propose novel techniques that close the Brier gap toward 0.20.

## Primary Metric
- **Name:** techniques_tested_per_week
- **Current:** 18
- **Target:** 30
- **Direction:** higher_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| papers_scanned_per_week | 50 | 100 |
| proposals_generated | 8 | 15 |
| proposals_implemented | 3 | 8 |
| gap_pct_covered_by_portfolio | 45% | 80% |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| arxiv_scan_depth | 50 | [20, 200] | 10 |
| github_search_queries | 5 | [3, 20] | 1 |
| kaggle_kernel_scan_depth | 30 | [10, 100] | 10 |
| relevance_threshold | 0.7 | [0.3, 0.95] | 0.05 |
| recency_window_days | 90 | [30, 365] | 30 |
| min_citation_count | 5 | [0, 50] | 5 |
| source_weight_arxiv | 0.4 | [0.1, 0.6] | 0.05 |
| source_weight_github | 0.3 | [0.1, 0.6] | 0.05 |
| source_weight_kaggle | 0.3 | [0.1, 0.6] | 0.05 |
| technique_novelty_bonus | 1.2 | [1.0, 2.0] | 0.1 |

## Experiment Protocol
1. Load current best config (scan depth, relevance thresholds, source weights)
2. Mutate one parameter from the search space
3. Run experiment (5 min budget): scan sources with mutated config, count unique techniques found
4. Measure techniques_tested_per_week (extrapolated from scan yield)
5. If improved (more techniques at same or higher quality) -> keep, commit config
6. If not -> revert to previous config
7. Log result to data/departments/research/karpathy-output.json

## Mutation Strategy
- **Type:** single-parameter perturbation
- **Selection:** uniform random from search space
- **Step:** fixed step per parameter (see table)
- **Direction:** random (up or down within range)
- **Cooldown:** do not re-mutate same parameter within 3 iterations

## Tools & Paths
- **Loop script:** scripts/departments/research/research-loop.sh
- **Output:** data/departments/research/karpathy-output.json
- **Proposals:** data/research/feature-proposals-*.json
- **Memory:** .claude/projects/-home-termius-mon-ipad/memory/research_*.md
- **APIs:** arxiv API, GitHub Search API, Kaggle API
- **Web scraping:** Brave Search for conference proceedings, blog posts
- **Cycle history:** data/cycle7_actionable_proposals.json

## Success Criteria
- techniques_tested_per_week >= 30 sustained for 2 consecutive weeks
- At least 50% of proposals have measured Brier delta < 0 (actually improve predictions)
- Zero weeks with 0 new proposals generated
- Pipeline from paper discovery to proposal generation under 48 hours

## Dependencies
- **Upstream:** None (D1 is the source of new ideas)
- **Downstream:** D2 (Engineering) consumes proposals, D3 (Evolution) uses new features
- **External:** arxiv.org availability, GitHub API rate limits, Kaggle API access
- **Compute:** CPU only (scanning + extraction, no ML)
