# Department: INFRA (D6)

## Mission
Maintain 99.9% uptime across all 6 HF evolution islands, the VM data server, cron jobs, and autonomous pipelines with zero manual intervention required.

## Primary Metric
- **Name:** uptime_pct
- **Current:** 99%+ (estimated)
- **Target:** 99.9%
- **Direction:** higher_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| restart_count_per_day | ~2 | < 1 |
| keepalive_success_rate | 95% | 99.9% |
| cron_job_success_rate | 95% | 99% |
| data_server_response_ms | ~500 | < 300 |
| space_cold_start_time_s | ~60 | < 30 |
| pipeline_completion_rate | 90% | 99% |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| keepalive_interval_min | 30 | [10, 60] | 5 |
| health_check_timeout_s | 30 | [10, 120] | 10 |
| auto_restart_threshold | 3_failures | [1, 5] | 1 |
| auto_restart_cooldown_s | 300 | [60, 600] | 60 |
| space_warmup_request_count | 1 | [1, 5] | 1 |
| data_server_cache_ttl_s | 3600 | [300, 7200] | 300 |
| cron_retry_count | 1 | [0, 3] | 1 |
| log_retention_days | 7 | [3, 30] | 1 |
| memory_alert_threshold_mb | 800 | [600, 900] | 50 |
| disk_alert_threshold_pct | 85 | [70, 95] | 5 |

## Experiment Protocol
1. Load current infra config (keepalive intervals, thresholds, retry logic)
2. Mutate one parameter from the search space
3. Run experiment (5 min budget): deploy config change, monitor uptime/response times
4. Measure uptime_pct, restart_count, response latency over observation window
5. If uptime improved or restart_count decreased without latency regression -> keep
6. If not -> revert to previous config
7. Log result to data/departments/infra/karpathy-output.json

## Mutation Strategy
- **Type:** conservative single-parameter perturbation (infra changes are high-risk)
- **Selection:** prioritize parameters associated with recent incidents
- **Safety:** never reduce keepalive_interval below 10 min (rate limit protection)
- **Rollback:** immediate revert if any space goes down within 5 min of change
- **Canary:** test config change on S15 (least critical) before fleet-wide deploy

## Tools & Paths
- **Loop script:** scripts/departments/infra/infra-loop.sh
- **Output:** data/departments/infra/karpathy-output.json
- **Keepalive:** scripts/keepalive-spaces.sh (*/30 cron)
- **Autonomous cycle:** scripts/autonomous-cycle.sh (:30 every 4h)
- **Health status:** data/health-status.json
- **Agent health:** data/agent-health.json
- **Data server:** scripts/data-server.py (auto-restart in autonomous-cycle.sh)
- **VM constraints:** 1 vCPU, 969 MB RAM (ZERO ML allowed)
- **HF Space URLs:**
  - S10: nomos42-nba-quant.hf.space
  - S11: nomos42-nba-quant-2.hf.space
  - S12-S15: nomos42-nba-evo-{3,4,5,6}.hf.space

## Success Criteria
- uptime_pct >= 99.9% over rolling 7-day window
- restart_count < 1 per day (average over 7 days)
- All 6 HF Spaces respond to health check within timeout
- Zero missed cron jobs (autonomous-cycle, keepalive, odds scraping)
- VM memory usage stays below 800 MB (969 MB physical limit)
- Data server responds within 300ms for API requests

## Dependencies
- **Upstream:** None (D6 is foundational infrastructure)
- **Downstream:** All departments depend on D6 for compute and data availability
- **External:** HF Spaces platform stability, VM host reliability, cron daemon
- **Compute:** VM only (monitoring scripts, no ML)
