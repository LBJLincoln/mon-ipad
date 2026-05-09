# Rotation A Research Proposal: FEC/SEC Direct REST API Integration
## fire-71 — 2026-05-09T22h

### Problem
- Political `feature_candidates = 272` vs NBA `3377` (12.4x gap — primary cap on POL Brier improvement)
- `nomos-political-alpha/scripts/scrape_fec_edgar.py` returns `ENDPOINT_NOT_YET_DEPLOYED`
- Browser Space (`LBJLincoln/nomos-browser-nba`) `/api/scrape-fec` endpoint never deployed
- No FEC/SEC financial disclosure data currently flowing into political features

### Solution: Direct REST API (No Browser Space Dependency)

**FEC API (api.fec.gov)** — public REST, zero auth required:
```
GET https://api.fec.gov/v1/candidates/?sort=-receipts&per_page=100&api_key=DEMO_KEY
GET https://api.fec.gov/v1/candidate/{id}/history/
GET https://api.fec.gov/v1/schedules/schedule_a/?recipient_committee_id={id}  (individual contributions)
GET https://api.fec.gov/v1/schedules/schedule_e/?support_oppose_indicator=S   (PAC independent expenditures)
```

**SEC EDGAR API (data.sec.gov)** — public REST, zero auth required:
```
GET https://data.sec.gov/submissions/{CIK}.json   (entity filing history)
GET https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt=2026-01-01  (Form 4 insiders)
GET https://data.sec.gov/api/xbrl/companyfacts/{CIK}.json  (13F institutional holdings)
```

### Proposed New Feature Columns (~130)

| Feature | Source | Update Freq | Expected Signal |
|---------|--------|-------------|----------------|
| `candidate_fec_raised_30d` | FEC receipts | Weekly | Fundraising momentum → viability proxy |
| `candidate_fec_spent_30d` | FEC disbursements | Weekly | Campaign activity = confidence signal |
| `candidate_fec_cash_on_hand` | FEC summary | Weekly | War chest = institutional backing |
| `candidate_fec_raised_vs_opponent_ratio` | FEC derived | Weekly | Head-to-head financial edge |
| `pac_support_net_30d` | FEC schedule_e | Weekly | Institutional political alignment |
| `pac_opposition_net_30d` | FEC schedule_e | Weekly | Attack spend = market fear |
| `campaign_spending_velocity_7d` | FEC derived | Weekly | Acceleration = polling reaction |
| `fundraising_momentum_7d` | FEC derived | Weekly | 7d vs 30d rate — inflection signal |
| `sec_insider_buy_net_90d_{donor}` | SEC Form 4 | Daily | Insider confidence of key donors |
| `sec_13f_institutional_pct_change` | SEC 13F | Quarterly | Institutional positioning shift |
| `donor_network_elo` | FEC+SEC derived | Weekly | Network centrality of donor graph |

### Implementation Plan

**File to create:** `nomos-political-alpha/scripts/fetch_fec_sec_features.py`

```python
# Pseudocode outline
import requests, json
from datetime import date, timedelta

def fetch_fec_candidate_financials(cycle=2026):
    url = f"https://api.fec.gov/v1/candidates/?election_year={cycle}&sort=-receipts&per_page=100"
    r = requests.get(url, params={"api_key": "DEMO_KEY"}, timeout=30)
    return r.json()["results"]

def fetch_pac_expenditures(start_date, end_date):
    url = "https://api.fec.gov/v1/schedules/schedule_e/"
    r = requests.get(url, params={"api_key": "DEMO_KEY", "min_date": start_date, "max_date": end_date}, timeout=30)
    return r.json()["results"]

def build_features_for_event(event_id, event_date):
    # Map political event → candidate(s) → FEC IDs → fetch financials
    # Output: dict of feature_name -> float
    pass

if __name__ == "__main__":
    features = build_features_for_event("...", date.today())
    with open(f"data/fec/fec-features-{date.today()}.json", "w") as f:
        json.dump(features, f)
```

**Cron:** Sunday 02:00 UTC (runs before weekly oracle retrain at 03:00)

**Integration into political_engine.py:**
1. New feature category: `"financial_disclosure"` (category #23)
2. Load `data/fec/fec-features-latest.json` in engine init
3. Features join on `candidate_id` → expands `feature_candidates` 272 → ~400+

### Expected Impact
- Campaign spending → outcome correlation: r=0.7+ in House races (academic consensus)
- Academic lit: Jacobson (1990) through Fouirnaies & Hall (2014) — spending advantages translate
- Conservative Brier improvement: 0.003–0.008 after 10k+ gen GA exploration of expanded feature space
- Zero new HF Space dependency — pure HTTP calls from VM

### Priority: HIGH
**Owner:** VM — `python3 nomos-political-alpha/scripts/fetch_fec_sec_features.py`
**Work Queue Item:** `vm-fec-sec-political-features` (priority 61 in mon-ipad work-queue)
**Blocked by:** Nothing — api.fec.gov DEMO_KEY works with 1000 req/day limit, sufficient for weekly batch

### Cross-Project Note
NBA analog: team financial health (payroll concentration, luxury tax) is not currently in NBA features.
Same pattern — scrape NBA salary cap data (spotrac.com or basketballreference) to add payroll-derived features.
But NBA feature_candidates=3377 already strong — political is the higher-priority beneficiary.
