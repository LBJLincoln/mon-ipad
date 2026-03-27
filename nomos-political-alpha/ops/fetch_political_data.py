#!/usr/bin/env python3
"""
Political Data Fetcher — All free APIs for Trump Donor Alpha.

Sources:
  1. FEC API — donor amounts, committees, timing
  2. Federal Register — executive orders, rules
  3. SEC EDGAR — Form 4 insider trades
  4. Polymarket CLOB — whale activity on Trump policy markets
  5. yfinance — stock prices for donor tickers
  6. FRED — macro indicators
  7. CoinGecko — crypto prices
  8. USAspending — government contracts

All APIs are FREE. No paid subscriptions needed.
"""

import os, sys, json, time, ssl, math, hashlib
import urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DONORS_DIR = DATA / "donors"
SIGNALS_DIR = DATA / "signals"
POLY_DIR = DATA / "polymarket"
INSIDER_DIR = DATA / "insider"
HIST_DIR = DATA / "historical"
for d in [DONORS_DIR, SIGNALS_DIR, POLY_DIR, INSIDER_DIR, HIST_DIR]:
    d.mkdir(parents=True, exist_ok=True)

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ── Load env ──
def _load_env():
    for f in [ROOT / ".env.local", ROOT / ".env"]:
        if f.exists():
            for line in f.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"): continue
                if line.startswith("export "): line = line[7:]
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
_load_env()

FEC_API_KEY = os.environ.get("FEC_API_KEY", "DEMO_KEY")
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
OPENSECRETS_KEY = os.environ.get("OPENSECRETS_API_KEY", "")

# ═══════════════════════════════════════════════════════════
# TRUMP DONOR UNIVERSE — Publicly traded companies
# ═══════════════════════════════════════════════════════════

DONOR_UNIVERSE = {
    # Tier 1: Direct quid pro quo documented (FT Oct 2025)
    "GEO":  {"name": "GEO Group",           "sector": "private_prisons", "donated": 500_000,  "channel": "inaugural", "favor": "mass_deportation_contracts", "delivered": True},
    "CXW":  {"name": "CoreCivic",           "sector": "private_prisons", "donated": 500_000,  "channel": "inaugural", "favor": "ICE_contracts",              "delivered": True},
    "COIN": {"name": "Coinbase",             "sector": "crypto",         "donated": 1_000_000, "channel": "inaugural", "favor": "GENIUS_Act_deregulation",   "delivered": True},
    "MO":   {"name": "Altria",               "sector": "tobacco",        "donated": 1_000_000, "channel": "inaugural", "favor": "menthol_ban_rescinded",     "delivered": True},
    "UNH":  {"name": "UnitedHealth",         "sector": "healthcare",     "donated": 5_000_000, "channel": "MAGA_Inc",  "favor": "Medicare_Advantage_rates",  "delivered": True},
    "PPC":  {"name": "Pilgrims Pride",       "sector": "food",           "donated": 5_000_000, "channel": "inaugural", "favor": "USDA_production_speedup",   "delivered": True},
    "OKLO": {"name": "Oklo Inc",             "sector": "nuclear",        "donated": 250_000,   "channel": "inaugural", "favor": "pro_nuclear_policy",        "delivered": False},
    "META": {"name": "Meta Platforms",       "sector": "big_tech",       "donated": 1_000_000, "channel": "inaugural", "favor": "FTC_antitrust_softened",    "delivered": True},
    "FOUR": {"name": "Shift4 Payments",      "sector": "fintech",        "donated": 2_000_000, "channel": "inaugural", "favor": "NASA_admin_nomination",     "delivered": True},

    # Tier 2: Large inaugural donors ($1M+)
    "CVX":  {"name": "Chevron",              "sector": "oil_gas",        "donated": 2_000_000, "channel": "inaugural", "favor": "drilling_deregulation",     "delivered": True},
    "XOM":  {"name": "ExxonMobil",           "sector": "oil_gas",        "donated": 1_000_000, "channel": "inaugural", "favor": "EPA_rollback",              "delivered": True},
    "OXY":  {"name": "Occidental Petroleum", "sector": "oil_gas",        "donated": 1_000_000, "channel": "inaugural", "favor": "federal_land_drilling",     "delivered": True},
    "AMZN": {"name": "Amazon",               "sector": "big_tech",       "donated": 1_000_000, "channel": "inaugural", "favor": "FTC_antitrust",             "delivered": False},
    "UBER": {"name": "Uber",                 "sector": "tech",           "donated": 1_000_000, "channel": "inaugural", "favor": "gig_economy_deregulation",  "delivered": False},
    "QCOM": {"name": "Qualcomm",             "sector": "tech",           "donated": 1_000_000, "channel": "inaugural", "favor": "chips_deregulation",        "delivered": False},
    "BA":   {"name": "Boeing",               "sector": "defense",        "donated": 1_000_000, "channel": "inaugural", "favor": "defense_contracts_FAA",     "delivered": False},
    "FDX":  {"name": "FedEx",                "sector": "transport",      "donated": 1_000_351, "channel": "inaugural", "favor": "transport_deregulation",    "delivered": False},
    "TSLA": {"name": "Tesla",                "sector": "auto_ev",        "donated": 290_000_000, "channel": "musk_PAC", "favor": "DOGE_influence_SpaceX",   "delivered": True},
    "LVS":  {"name": "Las Vegas Sands",      "sector": "gaming",         "donated": 132_000_000, "channel": "adelson_PAC", "favor": "Israel_gaming_policy",  "delivered": True},

    # Tier 3: Ballroom donors (antitrust play)
    "AAPL": {"name": "Apple",                "sector": "big_tech",       "donated": 1_000_000, "channel": "ballroom",  "favor": "DOJ_antitrust_soft",       "delivered": False},
    "MSFT": {"name": "Microsoft",            "sector": "big_tech",       "donated": 1_000_000, "channel": "ballroom",  "favor": "Activision_merger",        "delivered": True},
    "NVDA": {"name": "Nvidia",               "sector": "big_tech",       "donated": 1_000_000, "channel": "ballroom",  "favor": "chip_monopoly_review",     "delivered": False},
    "CMCSA":{"name": "Comcast",              "sector": "media",          "donated": 1_000_000, "channel": "ballroom",  "favor": "media_regulation",         "delivered": False},
    "UNP":  {"name": "Union Pacific",        "sector": "rail",           "donated": 1_000_000, "channel": "ballroom",  "favor": "rail_deregulation",        "delivered": False},

    # Tier 4: Crypto ecosystem beneficiaries
    "MSTR": {"name": "MicroStrategy",        "sector": "crypto",         "donated": 0,         "channel": "indirect",  "favor": "crypto_reserve_policy",    "delivered": True},
    "HOOD": {"name": "Robinhood",            "sector": "fintech",        "donated": 250_000,   "channel": "inaugural", "favor": "crypto_trading_expansion",  "delivered": True},
}

DONOR_TICKERS = list(DONOR_UNIVERSE.keys())

# Crypto tickers for CoinGecko
CRYPTO_IDS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "official-trump": "TRUMP"}

# Sector ETFs for relative strength
SECTOR_ETFS = ["ITA", "XLE", "XLF", "IWM", "XLK", "XLV", "SPY", "QQQ"]

# FRED macro series
FRED_SERIES = {
    "VIXCLS": "vix",
    "DGS10": "us10y",
    "DTWEXBGS": "dxy_broad",
    "BAMLH0A0HYM2": "hy_spread",
    "UNRATE": "unemployment",
    "T10Y2Y": "yield_curve",
}


# ═══════════════════════════════════════════════════════════
# HTTP HELPERS
# ═══════════════════════════════════════════════════════════

def _get(url, timeout=15, retries=2):
    """GET with retries and SSL bypass."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-PoliticalAlpha/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt == retries:
                print(f"[WARN] GET failed {url[:80]}: {e}")
                return None
            time.sleep(1 * (attempt + 1))
    return None


# ═══════════════════════════════════════════════════════════
# 1. FEC DONOR DATA
# ═══════════════════════════════════════════════════════════

# Trump-Vance Inaugural Committee ID
TRUMP_INAUGURAL_COMMITTEE = "C00947002"
# MAGA Inc Super PAC
MAGA_INC = "C00826800"
# Trump 47 Committee
TRUMP_47 = "C00907287"

TRUMP_COMMITTEES = [TRUMP_INAUGURAL_COMMITTEE, MAGA_INC, TRUMP_47]

def fetch_fec_donors(committee_id=TRUMP_INAUGURAL_COMMITTEE, min_amount=50000):
    """Fetch large donors to a Trump committee from FEC API."""
    print(f"[FEC] Fetching donors for committee {committee_id}...")
    all_donors = []
    page = 1
    while True:
        url = (f"https://api.open.fec.gov/v1/schedules/schedule_a/"
               f"?committee_id={committee_id}&min_amount={min_amount}"
               f"&per_page=100&page={page}&sort=-contribution_receipt_amount"
               f"&api_key={FEC_API_KEY}")
        data = _get(url)
        if not data or "results" not in data:
            break
        results = data["results"]
        if not results:
            break
        for r in results:
            all_donors.append({
                "contributor_name": r.get("contributor_name", ""),
                "contributor_employer": r.get("contributor_employer", ""),
                "amount": r.get("contribution_receipt_amount", 0),
                "date": r.get("contribution_receipt_date", ""),
                "committee": committee_id,
                "city": r.get("contributor_city", ""),
                "state": r.get("contributor_state", ""),
                "occupation": r.get("contributor_occupation", ""),
                "entity_type": r.get("entity_type", ""),
            })
        page += 1
        if page > 20:  # Safety cap
            break
        time.sleep(0.5)  # Rate limit
    print(f"[FEC] Got {len(all_donors)} donors for {committee_id}")
    return all_donors

def fetch_all_trump_donors():
    """Fetch donors from all Trump committees."""
    all_donors = []
    for cid in TRUMP_COMMITTEES:
        donors = fetch_fec_donors(cid)
        all_donors.extend(donors)
        time.sleep(1)
    # Save
    out = DONORS_DIR / f"fec_donors_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(all_donors, indent=2))
    print(f"[FEC] Total: {len(all_donors)} donors saved to {out}")
    return all_donors


# ═══════════════════════════════════════════════════════════
# 2. FEDERAL REGISTER — Executive Orders & Rules
# ═══════════════════════════════════════════════════════════

FEDERAL_REGISTER_BASE = "https://www.federalregister.gov/api/v1"

POLICY_KEYWORDS = {
    "oil_gas": ["drilling", "petroleum", "fossil fuel", "LNG", "pipeline", "EPA", "environmental"],
    "crypto": ["cryptocurrency", "digital asset", "blockchain", "stablecoin", "crypto"],
    "defense": ["defense", "military", "Pentagon", "weapons", "NATO", "armed forces"],
    "immigration": ["immigration", "deportation", "ICE", "border", "asylum", "detention"],
    "tobacco": ["tobacco", "nicotine", "menthol", "cigarette", "FDA tobacco"],
    "healthcare": ["Medicare", "Medicaid", "healthcare", "pharmaceutical", "drug pricing"],
    "big_tech": ["antitrust", "Big Tech", "monopoly", "merger", "FTC", "DOJ antitrust"],
    "finance": ["Dodd-Frank", "banking", "financial regulation", "SEC", "CFTC"],
    "transport": ["transportation", "freight", "shipping", "rail", "trucking"],
    "nuclear": ["nuclear", "atomic", "nuclear energy", "SMR", "reactor"],
    "auto_ev": ["electric vehicle", "EV", "auto", "NHTSA", "emissions"],
    "gaming": ["gaming", "casino", "gambling", "betting"],
    "food": ["USDA", "food safety", "poultry", "agriculture", "farming"],
    "private_prisons": ["detention", "ICE", "correctional", "prison", "incarceration"],
}

def fetch_executive_orders(days_back=30):
    """Fetch recent executive orders from Federal Register."""
    after = (datetime.now() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    url = (f"{FEDERAL_REGISTER_BASE}/documents?"
           f"conditions[presidential_document_type]=executive_order"
           f"&conditions[publication_date][gte]={after}"
           f"&per_page=100&order=newest")
    data = _get(url)
    if not data or "results" not in data:
        return []
    orders = []
    for r in data["results"]:
        title = r.get("title", "").lower()
        abstract = (r.get("abstract") or "").lower()
        text = title + " " + abstract
        # Match to sectors
        affected_sectors = []
        for sector, keywords in POLICY_KEYWORDS.items():
            if any(kw.lower() in text for kw in keywords):
                affected_sectors.append(sector)
        # Map sectors to donor tickers
        affected_tickers = []
        for ticker, info in DONOR_UNIVERSE.items():
            if info["sector"] in affected_sectors:
                affected_tickers.append(ticker)
        orders.append({
            "title": r.get("title", ""),
            "date": r.get("publication_date", ""),
            "type": r.get("type", ""),
            "abstract": r.get("abstract", ""),
            "url": r.get("html_url", ""),
            "affected_sectors": affected_sectors,
            "affected_tickers": affected_tickers,
            "document_number": r.get("document_number", ""),
        })
    out = SIGNALS_DIR / f"exec_orders_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(orders, indent=2))
    print(f"[FedReg] {len(orders)} executive orders, {sum(1 for o in orders if o['affected_tickers'])} affecting donors")
    return orders

def fetch_federal_rules(days_back=14):
    """Fetch recent federal rules (not just EOs) affecting donor sectors."""
    after = (datetime.now() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    rules = []
    for sector, keywords in POLICY_KEYWORDS.items():
        for kw in keywords[:2]:  # Top 2 keywords per sector
            url = (f"{FEDERAL_REGISTER_BASE}/documents?"
                   f"conditions[term]={urllib.parse.quote(kw)}"
                   f"&conditions[publication_date][gte]={after}"
                   f"&conditions[type]=RULE"
                   f"&per_page=20&order=newest")
            data = _get(url, timeout=10)
            if data and "results" in data:
                for r in data["results"]:
                    affected_tickers = [t for t, info in DONOR_UNIVERSE.items() if info["sector"] == sector]
                    rules.append({
                        "title": r.get("title", ""),
                        "date": r.get("publication_date", ""),
                        "sector": sector,
                        "keyword": kw,
                        "affected_tickers": affected_tickers,
                        "url": r.get("html_url", ""),
                    })
            time.sleep(0.3)
    out = SIGNALS_DIR / f"fed_rules_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(rules, indent=2))
    print(f"[FedReg] {len(rules)} federal rules affecting donor sectors")
    return rules


# ═══════════════════════════════════════════════════════════
# 3. SEC EDGAR — Form 4 Insider Trades
# ═══════════════════════════════════════════════════════════

SEC_EDGAR_BASE = "https://efts.sec.gov/LATEST"

# CIK numbers for donor companies (must look up)
# We use full-text search instead
def fetch_insider_trades(ticker, days_back=30):
    """Fetch Form 4 filings for a ticker from SEC EDGAR full-text search."""
    url = (f"{SEC_EDGAR_BASE}/search-index?"
           f"q=%22{ticker}%22&dateRange=custom"
           f"&startdt={(datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')}"
           f"&enddt={datetime.now().strftime('%Y-%m-%d')}"
           f"&forms=4&from=0&size=20")
    headers = {"User-Agent": "Nomos42 research@nomos42.ai", "Accept": "application/json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"[SEC] Failed for {ticker}: {e}")
        return []

    filings = []
    for hit in data.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        filings.append({
            "ticker": ticker,
            "file_date": src.get("file_date", ""),
            "form_type": src.get("form_type", ""),
            "display_names": src.get("display_names", []),
            "entity_name": src.get("entity_name", ""),
        })
    return filings

def fetch_all_insider_trades():
    """Fetch Form 4 for all donor tickers."""
    all_trades = {}
    for ticker in DONOR_TICKERS:
        trades = fetch_insider_trades(ticker)
        if trades:
            all_trades[ticker] = trades
        time.sleep(0.2)  # SEC rate limit: 10/sec
    out = INSIDER_DIR / f"form4_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(all_trades, indent=2))
    total = sum(len(v) for v in all_trades.values())
    print(f"[SEC] {total} Form 4 filings across {len(all_trades)} tickers")
    return all_trades


# ═══════════════════════════════════════════════════════════
# 4. POLYMARKET CLOB — Whale Activity on Trump Policy
# ═══════════════════════════════════════════════════════════

POLYMARKET_BASE = "https://clob.polymarket.com"
POLYMARKET_GAMMA = "https://gamma-api.polymarket.com"

TRUMP_POLICY_SLUGS = [
    "will-trump-be-impeached", "trump-approval-rating",
    "will-the-court-force-trump-to-refund-tariffs",
    "republicans-hold-house-2026",
]

def fetch_polymarket_markets(query="trump", limit=50):
    """Fetch Polymarket markets related to Trump policy."""
    url = f"{POLYMARKET_GAMMA}/markets?tag=politics&limit={limit}&active=true"
    data = _get(url)
    if not data:
        return []
    markets = []
    for m in data:
        title = (m.get("question") or m.get("title") or "").lower()
        if any(kw in title for kw in ["trump", "tariff", "republican", "gop", "immigration",
                                       "crypto", "defense", "impeach", "approval", "iran",
                                       "venezuela", "congress", "midterm", "sec ", "epa"]):
            markets.append({
                "id": m.get("id") or m.get("condition_id", ""),
                "question": m.get("question") or m.get("title", ""),
                "slug": m.get("slug", ""),
                "active": m.get("active", True),
                "volume": m.get("volume", 0),
                "liquidity": m.get("liquidity", 0),
                "outcome_prices": m.get("outcomePrices", ""),
                "end_date": m.get("end_date_iso", ""),
            })
    out = POLY_DIR / f"markets_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    out.write_text(json.dumps(markets, indent=2))
    print(f"[Polymarket] {len(markets)} Trump-related markets found")
    return markets

def fetch_polymarket_trades(token_id, limit=100):
    """Fetch recent trades for a specific Polymarket market token."""
    url = f"{POLYMARKET_BASE}/trades?asset_id={token_id}&limit={limit}"
    data = _get(url)
    if not data:
        return []
    whale_trades = []
    for t in data:
        size = float(t.get("size", 0))
        if size >= 500:  # Whale threshold: $500+
            whale_trades.append({
                "price": float(t.get("price", 0)),
                "size": size,
                "side": t.get("side", ""),
                "timestamp": t.get("match_time", ""),
                "maker": t.get("maker_address", "")[:10],
            })
    return whale_trades


# ═══════════════════════════════════════════════════════════
# 5. STOCK PRICES (yfinance)
# ═══════════════════════════════════════════════════════════

def fetch_stock_prices(tickers=None, period="3mo"):
    """Fetch OHLCV for donor tickers + sector ETFs."""
    try:
        import yfinance as yf
    except ImportError:
        print("[WARN] yfinance not installed. pip install yfinance")
        return {}

    all_tickers = (tickers or DONOR_TICKERS) + SECTOR_ETFS
    print(f"[yfinance] Fetching {len(all_tickers)} tickers, period={period}...")
    prices = {}
    for ticker in all_tickers:
        try:
            df = yf.download(ticker, period=period, progress=False)
            if not df.empty:
                prices[ticker] = [
                    {"date": str(idx.date()), "open": float(row["Open"]),
                     "high": float(row["High"]), "low": float(row["Low"]),
                     "close": float(row["Close"]), "volume": int(row["Volume"])}
                    for idx, row in df.iterrows()
                ]
        except Exception as e:
            print(f"[yfinance] Failed {ticker}: {e}")
        time.sleep(0.1)
    out = HIST_DIR / f"prices_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(prices))
    print(f"[yfinance] Got prices for {len(prices)} tickers")
    return prices


# ═══════════════════════════════════════════════════════════
# 6. FRED MACRO DATA
# ═══════════════════════════════════════════════════════════

def fetch_fred_data(days_back=90):
    """Fetch macro series from FRED."""
    if not FRED_API_KEY:
        print("[WARN] FRED_API_KEY not set. Skipping macro data.")
        return {}
    macro = {}
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    for series_id, name in FRED_SERIES.items():
        url = (f"https://api.stlouisfed.org/fred/series/observations?"
               f"series_id={series_id}&api_key={FRED_API_KEY}"
               f"&file_type=json&observation_start={start}")
        data = _get(url)
        if data and "observations" in data:
            macro[name] = [{"date": o["date"], "value": float(o["value"]) if o["value"] != "." else None}
                          for o in data["observations"]]
    out = HIST_DIR / f"macro_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(macro))
    print(f"[FRED] {len(macro)} macro series fetched")
    return macro


# ═══════════════════════════════════════════════════════════
# 7. COINGECKO — Crypto Prices
# ═══════════════════════════════════════════════════════════

def fetch_crypto_prices(days=90):
    """Fetch crypto prices from CoinGecko (free, no key)."""
    crypto = {}
    for cg_id, symbol in CRYPTO_IDS.items():
        url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart?vs_currency=usd&days={days}"
        data = _get(url)
        if data and "prices" in data:
            crypto[symbol] = [{"timestamp": p[0], "price": p[1]} for p in data["prices"]]
        time.sleep(2)  # CoinGecko rate limit
    out = HIST_DIR / f"crypto_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(crypto))
    print(f"[CoinGecko] {len(crypto)} crypto series fetched")
    return crypto


# ═══════════════════════════════════════════════════════════
# 8. USASPENDING — Government Contracts to Donors
# ═══════════════════════════════════════════════════════════

def fetch_gov_contracts(company_name, days_back=180):
    """Fetch government contracts awarded to a company."""
    url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    payload = json.dumps({
        "filters": {
            "recipient_search_text": [company_name],
            "time_period": [{"start_date": (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                            "end_date": datetime.now().strftime("%Y-%m-%d")}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "Awarding Agency"],
        "limit": 50, "page": 1,
        "sort": "Award Amount", "order": "desc",
    }).encode()
    try:
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json", "User-Agent": "Nomos42/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("results", [])
    except Exception as e:
        print(f"[USAspending] Failed for {company_name}: {e}")
        return []

def fetch_donor_contracts():
    """Fetch gov contracts for key donor companies."""
    contracts = {}
    priority_donors = ["Lockheed Martin", "Boeing", "CoreCivic", "GEO Group",
                       "FedEx", "Chevron", "ExxonMobil", "UnitedHealth"]
    for company in priority_donors:
        c = fetch_gov_contracts(company)
        if c:
            contracts[company] = c
        time.sleep(1)
    out = SIGNALS_DIR / f"gov_contracts_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(contracts, indent=2))
    total = sum(len(v) for v in contracts.values())
    print(f"[USAspending] {total} contracts across {len(contracts)} companies")
    return contracts


# ═══════════════════════════════════════════════════════════
# MASTER FETCH — Run all data collection
# ═══════════════════════════════════════════════════════════

def fetch_all(skip_slow=False):
    """Run all data fetchers. Call this from cron on VM."""
    print(f"\n{'='*60}")
    print(f"NOMOS42 POLITICAL ALPHA — Data Fetch {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    results = {}

    # Fast fetches (< 1 min total)
    results["exec_orders"] = fetch_executive_orders(days_back=30)
    results["fed_rules"] = fetch_federal_rules(days_back=14)
    results["polymarket"] = fetch_polymarket_markets()

    if not skip_slow:
        # Medium fetches (1-5 min)
        results["fec_donors"] = fetch_all_trump_donors()
        results["insider_trades"] = fetch_all_insider_trades()
        results["crypto"] = fetch_crypto_prices(days=90)

        # Slow fetches (5-15 min)
        results["stock_prices"] = fetch_stock_prices()
        results["macro"] = fetch_fred_data()
        results["gov_contracts"] = fetch_donor_contracts()

    # Summary
    print(f"\n{'='*60}")
    print(f"FETCH COMPLETE")
    for k, v in results.items():
        count = len(v) if isinstance(v, (list, dict)) else "?"
        print(f"  {k}: {count}")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Nomos42 Political Alpha Data Fetcher")
    parser.add_argument("--fast", action="store_true", help="Skip slow fetches (stocks, contracts)")
    parser.add_argument("--fec", action="store_true", help="FEC donors only")
    parser.add_argument("--signals", action="store_true", help="Federal Register only")
    parser.add_argument("--polymarket", action="store_true", help="Polymarket only")
    parser.add_argument("--insider", action="store_true", help="SEC Form 4 only")
    parser.add_argument("--prices", action="store_true", help="Stock prices only")
    parser.add_argument("--all", action="store_true", help="Everything")
    args = parser.parse_args()

    if args.fec:
        fetch_all_trump_donors()
    elif args.signals:
        fetch_executive_orders()
        fetch_federal_rules()
    elif args.polymarket:
        fetch_polymarket_markets()
    elif args.insider:
        fetch_all_insider_trades()
    elif args.prices:
        fetch_stock_prices()
    elif args.fast:
        fetch_all(skip_slow=True)
    else:
        fetch_all()
