# NOMOS42 — Autonomous vs Manual Systems
> Updated 2026-03-31

## Fully Autonomous (runs 24/7 without human)

| System | Mechanism | Frequency | Self-Healing |
|--------|-----------|-----------|-------------|
| NBA Evolution (6 islands) | HF Spaces always-on | Continuous | Auto-restart via watchdog |
| Political Evolution (4 islands) | HF Spaces always-on | Continuous | Auto-restart via watchdog |
| Brain decisions | HF Space background thread | Every 4h | Fallback AI chain |
| Watchdog | cron */5 | Every 5 min | Restarts all crashed services |
| Bot keepalive | cron */5 | Every 5 min | Auto-restart dead bots |
| Infra agent | cron */30 | Every 30 min | Auto-restart GPU platforms |
| Odds fetching | cron */30 (game hours) | Every 30 min | Retries on failure |
| Cross-repo monitor | cron 2h | Every 2h | Reports only |
| Daily evaluation | cron 10:00 | Daily | Updates bankroll |
| Arena benchmark | cron 11:00 | Daily | Reports only |
| Portfolio optimizer | cron 22:00 | Daily | Reports only |
| Kaggle GPU evolution | cron 3:00 | Daily | Auto-retry |
| Google Drive backup | cron 3:00 | Daily | Reports failure |

## Semi-Autonomous (triggered by human, then runs alone)

| System | Trigger | Duration | Human Needed For |
|--------|---------|----------|-----------------|
| Karpathy research loop | /karpathy-loop | 1-4h | Initial trigger only |
| Predictions | autonomous-cycle.sh | 5 min | None (cron triggered) |
| Feature deployment | git subtree push | 10 min | Decision to deploy |
| HF Space config changes | POST /api/config | Instant | Decision which params |
| Colab GPU evolution | Manual notebook start | 4-12h | Start + monitor credits |
| Modal GPU evolution | API call | 1-30 min | Start |

## Manual Only (requires human each time)

| System | Why Manual | Could Automate? |
|--------|-----------|----------------|
| Feature engineering | Creative decisions | Partially (Karpathy loop) |
| Engine version bumps | Breaking changes possible | No — needs review |
| New category addition | Domain knowledge | No — needs research |
| SaaS pricing decisions | Business strategy | No |
| Git merge conflicts | Judgment calls | No |
| GPU platform signup | Account creation | No |
| Forge user onboarding | Relationship | Partially |

## What COULD Be Automated Next

| Improvement | Effort | Impact | Priority |
|-------------|--------|--------|----------|
| Cross-pollination between islands | 2h | HIGH — breaks monoculture | P1 |
| Auto-deploy engine updates to all spaces | 1h | HIGH — removes manual sync | P1 |
| Codex Triggers for GitHub issue triage | 1h | MEDIUM — auto-responds to issues | P2 |
| Auto-retry failed Kaggle sessions | 30min | MEDIUM — recovers GPU time | P2 |
| Political data daily full-fetch cron | Done | Already automated | - |
| Auto-generate predictions even without odds | 1h | MEDIUM — never miss a game | P2 |
| Forge F0-F6 as autonomous agents | 8h | LOW — no users yet | P3 |
| Dashboard auto-deploy on data push | 30min | LOW — Vercel already auto-deploys | P4 |
