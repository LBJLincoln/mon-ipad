#!/usr/bin/env python3
"""
Fetch NBA odds via OddsHarvester (Playwright scraping of OddsPortal).
Called by DataWorker (Node.js) via child_process.

Output: JSON to stdout with upcoming NBA odds from 80+ bookmakers.
"""

import json
import sys
import os
from datetime import datetime, timezone

def main():
    try:
        from oddsharvester.core.scraper_app import ScraperApp
        from oddsharvester.utils.sport_market_constants import Sport

        # Scrape upcoming NBA odds (moneyline + spreads + totals)
        app = ScraperApp(
            sport=Sport.BASKETBALL,
            leagues=["nba"],
            markets=["1x2"],  # moneyline
            storage_type="local",
            output_dir="/data/odds",
        )

        results = app.scrape_upcoming()

        # Convert to JSON-serializable format
        output = {
            "source": "oddsharvester",
            "sport": "basketball_nba",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "games": [],
        }

        if results and hasattr(results, "matches"):
            for match in results.matches:
                game = {
                    "home_team": getattr(match, "home_team", ""),
                    "away_team": getattr(match, "away_team", ""),
                    "commence_time": getattr(match, "date", ""),
                    "bookmakers": {},
                }

                if hasattr(match, "odds"):
                    for bk_name, odds_data in match.odds.items():
                        game["bookmakers"][bk_name] = {
                            "home": odds_data.get("home", None),
                            "away": odds_data.get("away", None),
                            "draw": odds_data.get("draw", None),
                        }

                output["games"].append(game)

        print(json.dumps(output))

    except ImportError as e:
        # OddsHarvester not installed — return empty
        print(json.dumps({
            "source": "oddsharvester",
            "error": f"Import failed: {e}",
            "games": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        sys.exit(0)

    except Exception as e:
        print(json.dumps({
            "source": "oddsharvester",
            "error": str(e),
            "games": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        sys.exit(0)


if __name__ == "__main__":
    main()
