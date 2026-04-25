# TF Rigorous Validation — 2026-04-25 12:10 UTC

Bootstrap 95% CI (1000 resamples), ECE calibration, walk-forward Brier, per-agent breakdown.

## NBA
- window: last 30 days, 56 confident bets
- **Brier**: 0.5480  95% CI [0.5035, 0.5885]
- **Win rate**: 3.57%  95% CI [0.00%, 8.93%]
- **PnL**: $-92.21  95% CI [$-102.61, $-79.77]
- **ECE**: 0.7127  (0=perfectly calibrated; random ~0.25)

### Reliability (predicted vs actual per bucket)
| bucket | n | predicted | actual | gap |
|---|---:|---:|---:|---:|
| 0.6-0.7 | 11 | 0.639 | 0.000 | -0.639 |
| 0.7-0.8 | 31 | 0.735 | 0.065 | -0.670 |
| 0.8-0.9 | 11 | 0.846 | 0.000 | -0.846 |
| 0.9-1.0 | 3 | 0.933 | 0.000 | -0.933 |

### Walk-forward Brier trajectory (rolling windows)
| window | n | brier |
|---|---:|---:|
| d31-37 | 20 | 0.6325 |
| d35-39 | 20 | 0.5812 |
| d35-40 | 20 | 0.5832 |
| d36-44 | 20 | 0.5551 |
| d37-47 | 20 | 0.509 |
| d39-53 | 20 | 0.5206 |
| d41-55 | 20 | 0.4951 |
| d44-60 | 20 | 0.4927 |

### Per-agent (top 5 + bottom 3)
| agent | bets | WR | Brier | PnL |
|---|---:|---:|---:|---:|
| `gemini-anl` | 1 | - | 0.6084 | $-2.78 |
| `nvidia-minimax` | 2 | 50.00% | 0.2762 | $-2.87 |
| `selfhost-gemma3` | 4 | 25.00% | 0.3294 | $-2.93 |
| `qwen-arb` | 1 | - | 0.36 | $-3.94 |
| `mistral-large` | 4 | - | 0.5262 | $-8.16 |
| `selfhost-qwen06` | 11 | - | 0.7049 | $-14.16 |
| `nemotron-120b` | 13 | - | 0.4756 | $-18.50 |
| `mistral-small` | 15 | - | 0.6161 | $-26.82 |

## POL
- window: last 17 days, 216 confident bets
- **Brier**: 0.2635  95% CI [0.2428, 0.2866]
- **Win rate**: 55.09%  95% CI [48.15%, 61.57%]
- **PnL**: $+40.18  95% CI [$-27.11, $+104.65]
- **ECE**: 0.1496  (0=perfectly calibrated; random ~0.25)

### Reliability (predicted vs actual per bucket)
| bucket | n | predicted | actual | gap |
|---|---:|---:|---:|---:|
| 0.5-0.6 | 28 | 0.549 | 0.714 | +0.166 |
| 0.6-0.7 | 120 | 0.639 | 0.525 | -0.114 |
| 0.7-0.8 | 65 | 0.715 | 0.508 | -0.207 |
| 0.8-0.9 | 3 | 0.817 | 1.000 | +0.183 |

### Walk-forward Brier trajectory (rolling windows)
| window | n | brier |
|---|---:|---:|
| d0-2 | 20 | 0.1937 |
| d0-2 | 20 | 0.2395 |
| d0-2 | 20 | 0.2733 |
| d2-3 | 20 | 0.3014 |
| d2-3 | 20 | 0.3423 |
| d2-4 | 20 | 0.3304 |
| d2-4 | 20 | 0.3409 |
| d3-4 | 20 | 0.3091 |
| d3-4 | 20 | 0.2612 |
| d4-4 | 20 | 0.2557 |
| d4-5 | 20 | 0.2442 |
| d4-5 | 20 | 0.2909 |
| d4-5 | 20 | 0.3051 |
| d4-5 | 20 | 0.319 |
| d5-6 | 20 | 0.2876 |
| d5-6 | 20 | 0.3012 |
| d5-6 | 20 | 0.3014 |
| d5-7 | 20 | 0.2681 |
| d6-7 | 20 | 0.2808 |
| d6-7 | 20 | 0.2301 |
| d6-8 | 20 | 0.2587 |
| d7-8 | 20 | 0.3303 |
| d7-9 | 20 | 0.3697 |
| d8-10 | 20 | 0.3856 |
| d8-10 | 20 | 0.3564 |
| d8-10 | 20 | 0.3123 |
| d9-11 | 20 | 0.2859 |
| d10-11 | 20 | 0.2468 |
| d10-11 | 20 | 0.1862 |
| d10-12 | 20 | 0.1482 |
| d11-12 | 20 | 0.1395 |
| d11-12 | 20 | 0.173 |
| d11-13 | 20 | 0.1997 |
| d12-13 | 20 | 0.2678 |
| d12-14 | 20 | 0.2932 |
| d12-14 | 20 | 0.2624 |
| d13-15 | 20 | 0.2464 |
| d13-15 | 20 | 0.2073 |
| d14-16 | 20 | 0.1951 |
| d14-16 | 20 | 0.2089 |

### Per-agent (top 5 + bottom 3)
| agent | bets | WR | Brier | PnL |
|---|---:|---:|---:|---:|
| `qwen-quant` | 53 | 58.50% | 0.2486 | $+37.07 |
| `qwen-arb` | 41 | 46.30% | 0.2884 | $+13.45 |
| `mistral-ministral` | 5 | 100.00% | 0.1602 | $+4.81 |
| `llama-contra` | 42 | 54.80% | 0.2766 | $+4.63 |
| `nvidia-minimax` | 2 | 100.00% | 0.0842 | $+4.54 |
| `gemini-tact` | 11 | 45.50% | 0.311 | $-3.43 |
| `nemotron-120b` | 15 | 53.30% | 0.2434 | $-9.02 |
| `gemini-anl` | 25 | 44.00% | 0.2876 | $-23.68 |

## Cross-TF Brier comparison (Welch's t-test)
- NBA mean Brier: 0.548
- POL mean Brier: 0.2635
- t = 11.8384, df ≈ 87.0, p (two-sided) ≈ 0.0
- statistically significant at 95%: **yes (p<0.05)**
