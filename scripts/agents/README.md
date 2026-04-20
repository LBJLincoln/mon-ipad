# scripts/agents — browser-use + Hermes VM clients

Thin VM-side clients that drive the 3 agent HF Spaces shipped April 2026.
All Spaces are deployed by the other DR FRANKENSTEIN instance; this VM only
needs the clients + cron entries.

## Client -> Space map

| Client script                      | Target HF Space                            | Role                              |
|------------------------------------|--------------------------------------------|-----------------------------------|
| `nba_line_scraper_client.py`       | `LBJLincoln/nomos-browser-nba`             | ESPN/bbref/VegasInsider lines     |
| `pixel_qa_client.py`               | `TESTforge42/nomos-browser-qa`             | Pixel-world visual QA             |
| `dashboard_qa_client.py`           | `TESTforge42/nomos-browser-qa`             | Vercel dashboard regression gate  |
| `../../nomos-political-alpha/scripts/scrape_fec_edgar.py` | `LBJLincoln/nomos-browser-nba` (`/api/scrape-fec`, pending) | FEC + SEC EDGAR |
| _hermes client_ (future)           | `LBJLincoln26/nomos-hermes-agent`          | Orchestrator RPC                  |

## Cron examples (VM crontab)

```cron
# Every 2h: refresh NBA closing lines into data/lines/
0 */2 * * * cd /home/termius/mon-ipad && python3 scripts/agents/nba_line_scraper_client.py >> data/logs/line-scraper.log 2>&1

# After each PIXEL deploy: visual regression QA (chained from pixel deploy cron)
5 */4 * * * cd /home/termius/mon-ipad && python3 scripts/agents/pixel_qa_client.py >> data/logs/pixel-qa.log 2>&1

# Hourly dashboard QA (catches Vercel breakage before the user does)
20 * * * * cd /home/termius/mon-ipad && python3 scripts/agents/dashboard_qa_client.py >> data/logs/dashboard-qa.log 2>&1

# Daily FEC/EDGAR scrape once /api/scrape-fec ships (stub is a no-op until then)
15 6 * * * cd /home/termius/nomos-political-alpha && python3 scripts/scrape_fec_edgar.py >> data/logs/fec-scraper.log 2>&1
```

## Setup

Clients are pure-httpx and work on any box that has Python 3.10+.
One-shot VM install (browser-use + Hermes for local debug):

```
bash scripts/setup/install-browser-hermes.sh
```

Codespaces auto-runs `.devcontainer/post-create.sh` which does the same.
