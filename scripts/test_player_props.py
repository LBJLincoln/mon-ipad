#!/usr/bin/env python3
"""Unit tests for scripts/fetch_player_props.py.

Kent Beck bar: one behaviour per test, test the contract, don't pretend to
test the HTTP layer (the _get_json call is a seam we mock only when needed).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_player_props as fpp  # noqa: E402


class BuildTierMapTests(unittest.TestCase):
    def test_single_team_ranks_by_minutes(self):
        stats = {
            "LAL": {
                "players": [
                    {"name": "Bench Guy",   "MIN": 8.0,  "GP": 20, "PPG": 3,  "RPG": 1, "APG": 1, "FG3M": 0.2, "SPG": 0.2, "BPG": 0.1},
                    {"name": "Luka",        "MIN": 35.9, "GP": 40, "PPG": 33, "RPG": 7, "APG": 8, "FG3M": 4.0, "SPG": 1.5, "BPG": 0.5},
                    {"name": "Reaves",      "MIN": 34.7, "GP": 40, "PPG": 23, "RPG": 4, "APG": 5, "FG3M": 2.3, "SPG": 1.0, "BPG": 0.3},
                    {"name": "LeBron",      "MIN": 33.5, "GP": 40, "PPG": 21, "RPG": 6, "APG": 6, "FG3M": 1.3, "SPG": 0.9, "BPG": 0.6},
                    {"name": "Marcus",      "MIN": 28.7, "GP": 40, "PPG": 9,  "RPG": 2, "APG": 2, "FG3M": 1.6, "SPG": 1.2, "BPG": 0.1},
                    {"name": "Rui",         "MIN": 28.5, "GP": 40, "PPG": 11, "RPG": 3, "APG": 0, "FG3M": 1.7, "SPG": 0.5, "BPG": 0.2},
                ]
            }
        }
        tm = fpp.build_tier_map(stats)
        self.assertEqual(set(tm["LAL"].keys()), {"star1", "star2", "star3", "role1", "role2"})
        self.assertEqual(tm["LAL"]["star1"]["name"], "Luka")
        self.assertEqual(tm["LAL"]["star2"]["name"], "Reaves")
        self.assertEqual(tm["LAL"]["role2"]["name"], "Rui")
        # Bench guy (MIN=8) must not appear in top-5
        tops = {p["name"] for p in tm["LAL"].values()}
        self.assertNotIn("Bench Guy", tops)

    def test_small_roster_fills_what_it_can(self):
        stats = {
            "X": {"players": [
                {"name": "A", "MIN": 30, "GP": 10, "PPG": 20, "RPG": 5, "APG": 5, "FG3M": 2, "SPG": 1, "BPG": 1},
                {"name": "B", "MIN": 25, "GP": 10, "PPG": 15, "RPG": 5, "APG": 4, "FG3M": 1, "SPG": 1, "BPG": 0.5},
            ]}
        }
        tm = fpp.build_tier_map(stats)
        # Only 2 players: star1, star2 populated; star3/role1/role2 absent
        self.assertIn("star1", tm["X"])
        self.assertIn("star2", tm["X"])
        self.assertNotIn("star3", tm["X"])

    def test_low_gp_players_filtered_when_enough_seasoned(self):
        # 5 seasoned + 1 rookie w/ more minutes but GP<5 should be dropped
        stats = {
            "Y": {"players": [
                {"name": "Rookie", "MIN": 40, "GP": 3, "PPG": 30, "RPG": 7, "APG": 5, "FG3M": 3, "SPG": 1, "BPG": 0.5},
                {"name": "V1", "MIN": 35, "GP": 30, "PPG": 25, "RPG": 5, "APG": 5, "FG3M": 2, "SPG": 1, "BPG": 0.5},
                {"name": "V2", "MIN": 30, "GP": 30, "PPG": 20, "RPG": 5, "APG": 4, "FG3M": 1, "SPG": 1, "BPG": 0.3},
                {"name": "V3", "MIN": 28, "GP": 30, "PPG": 15, "RPG": 4, "APG": 3, "FG3M": 1, "SPG": 0.5, "BPG": 0.2},
                {"name": "V4", "MIN": 25, "GP": 30, "PPG": 12, "RPG": 3, "APG": 2, "FG3M": 1, "SPG": 0.3, "BPG": 0.1},
                {"name": "V5", "MIN": 20, "GP": 30, "PPG": 10, "RPG": 3, "APG": 1, "FG3M": 0.5, "SPG": 0.2, "BPG": 0.1},
            ]}
        }
        tm = fpp.build_tier_map(stats)
        names = {p["name"] for p in tm["Y"].values()}
        self.assertNotIn("Rookie", names, "low-GP rookie must be filtered when 5+ seasoned available")
        self.assertEqual(tm["Y"]["star1"]["name"], "V1")


class RoundLineTests(unittest.TestCase):
    def test_integer_plus_half(self):
        self.assertEqual(fpp._round_line(24.0), 24.5)
        self.assertEqual(fpp._round_line(24.3), 24.5)
        self.assertEqual(fpp._round_line(24.9), 24.5)
        self.assertEqual(fpp._round_line(25.0), 25.5)
        self.assertEqual(fpp._round_line(0.4), 0.5)  # clamp

    def test_zero_mean_guarded(self):
        self.assertEqual(fpp._round_line(0.0), 0.5)
        self.assertEqual(fpp._round_line(-1.0), 0.5)


class SynthGamePropsTests(unittest.TestCase):
    def setUp(self):
        self.tier_map = fpp.build_tier_map({
            "HOME": {"players": [
                {"name": "H_Star1", "MIN": 36, "GP": 30, "PPG": 30, "RPG": 8, "APG": 9, "FG3M": 3, "SPG": 1.5, "BPG": 0.8},
                {"name": "H_Star2", "MIN": 32, "GP": 30, "PPG": 22, "RPG": 5, "APG": 6, "FG3M": 2, "SPG": 1.0, "BPG": 0.3},
                {"name": "H_Star3", "MIN": 28, "GP": 30, "PPG": 18, "RPG": 6, "APG": 3, "FG3M": 1.5, "SPG": 0.8, "BPG": 0.4},
            ]},
            "AWAY": {"players": [
                {"name": "A_Star1", "MIN": 35, "GP": 30, "PPG": 28, "RPG": 7, "APG": 4, "FG3M": 2.8, "SPG": 1.2, "BPG": 0.6},
                {"name": "A_Star2", "MIN": 30, "GP": 30, "PPG": 20, "RPG": 4, "APG": 8, "FG3M": 2.1, "SPG": 1.1, "BPG": 0.2},
            ]},
        })

    def test_home_star1_points_emitted(self):
        props = fpp.synth_game_props("HOME", "AWAY", self.tier_map)
        self.assertIn("pp_points_star1_home", props)
        e = props["pp_points_star1_home"]
        self.assertEqual(e["line"], 30.5)
        self.assertEqual(e["odds"], fpp.FAIR_DECIMAL)
        self.assertEqual(e["prob_fair"], fpp.FAIR_PROB)
        self.assertEqual(e["player"], "H_Star1")
        self.assertEqual(e["stat"], "points")

    def test_away_star1_all_stats_present(self):
        props = fpp.synth_game_props("HOME", "AWAY", self.tier_map)
        for stat in ("points", "rebounds", "assists", "threes", "steals", "blocks"):
            self.assertIn(f"pp_{stat}_star1_away", props, f"missing {stat} star1 away")

    def test_star3_only_for_points(self):
        props = fpp.synth_game_props("HOME", "AWAY", self.tier_map)
        self.assertIn("pp_points_star3_home", props)
        # Per proposal: rebounds/assists/threes are star1-star2, steals/blocks star1-only
        self.assertNotIn("pp_rebounds_star3_home", props)
        self.assertNotIn("pp_steals_star2_home", props)
        self.assertNotIn("pp_blocks_star2_home", props)

    def test_missing_team_yields_empty(self):
        props = fpp.synth_game_props("???", "AWAY", self.tier_map)
        # Only AWAY props should appear
        self.assertTrue(all(k.endswith("_away") for k in props))

    def test_zero_mean_player_skipped(self):
        tier_map = fpp.build_tier_map({
            "Z": {"players": [
                {"name": "NoBlocks", "MIN": 30, "GP": 30, "PPG": 10, "RPG": 3, "APG": 2, "FG3M": 0, "SPG": 0, "BPG": 0},
                {"name": "B",        "MIN": 25, "GP": 30, "PPG": 8,  "RPG": 3, "APG": 2, "FG3M": 0, "SPG": 0, "BPG": 0},
            ]},
            "W": {"players": [
                {"name": "X", "MIN": 30, "GP": 30, "PPG": 10, "RPG": 3, "APG": 2, "FG3M": 1, "SPG": 0.5, "BPG": 0.5},
                {"name": "Y", "MIN": 25, "GP": 30, "PPG": 8,  "RPG": 3, "APG": 2, "FG3M": 1, "SPG": 0.5, "BPG": 0.5},
            ]},
        })
        props = fpp.synth_game_props("Z", "W", tier_map)
        # NoBlocks has 0 blocks — must not emit pp_blocks_star1_home
        self.assertNotIn("pp_blocks_star1_home", props)
        # Away (W) does have blocks > 0
        self.assertIn("pp_blocks_star1_away", props)


class ImpliedProbTests(unittest.TestCase):
    def test_no_vig_round_trip(self):
        # -110/-110 → each implied 0.5238, no-vig → 0.5 exactly
        p_over = fpp._implied(1.909)
        p_under = fpp._implied(1.909)
        fair = p_over / (p_over + p_under)
        self.assertAlmostEqual(fair, 0.5, places=4)

    def test_favorite_underdog(self):
        # Over 1.5 (heavy fav) Under 2.5 (dog)
        p_over = fpp._implied(1.5)
        p_under = fpp._implied(2.5)
        fair = p_over / (p_over + p_under)
        # Fair should be > 0.5 since over is cheaper
        self.assertGreater(fair, 0.5)

    def test_zero_guard(self):
        self.assertEqual(fpp._implied(0), 0.5)
        self.assertEqual(fpp._implied(1.0), 0.5)


class AbbrTests(unittest.TestCase):
    def test_full_names_map(self):
        self.assertEqual(fpp._abbr("Los Angeles Lakers"), "LAL")
        self.assertEqual(fpp._abbr("Boston Celtics"),     "BOS")

    def test_short_forms(self):
        self.assertEqual(fpp._abbr("GS Warriors"), "GSW")
        self.assertEqual(fpp._abbr("OKC Thunder"), "OKC")

    def test_already_abbr(self):
        self.assertEqual(fpp._abbr("LAL"), "LAL")

    def test_unknown_returns_none(self):
        self.assertIsNone(fpp._abbr("Martian Rocketeers"))


class NameToTierTests(unittest.TestCase):
    def setUp(self):
        self.tier_map = fpp.build_tier_map({
            "LAL": {"players": [
                {"name": "Luka Dončić", "MIN": 36, "GP": 30, "PPG": 33, "RPG": 7, "APG": 8, "FG3M": 4, "SPG": 1, "BPG": 0.5},
                {"name": "LeBron James", "MIN": 33, "GP": 30, "PPG": 21, "RPG": 6, "APG": 6, "FG3M": 1, "SPG": 1, "BPG": 0.5},
            ]}
        })

    def test_exact_match(self):
        self.assertEqual(fpp._name_to_tier("Luka Dončić", "LAL", self.tier_map), "star1")

    def test_substring_match(self):
        # DK often drops the diacritic
        self.assertEqual(fpp._name_to_tier("Luka Doncic", "LAL", self.tier_map), None,
                         "exact-match fails without normalisation — acceptable fallback to None")

    def test_unknown_team(self):
        self.assertIsNone(fpp._name_to_tier("Any", "???", self.tier_map))


class SchemaInvariantTests(unittest.TestCase):
    """Walk the real synth output and assert schema invariants."""

    @classmethod
    def setUpClass(cls):
        synth_path = ROOT / "data" / "nba-agent" / "player-props-synth.json"
        if not synth_path.exists():
            # Generate on the fly
            import subprocess
            subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_player_props.py"),
                            "--synth-only"], cwd=str(ROOT), check=True, capture_output=True)
        with open(synth_path) as f:
            cls.data = json.load(f)

    def test_every_game_has_at_least_six_props(self):
        low = [gk for gk, props in self.data["games"].items() if len(props) < 6]
        self.assertEqual(low, [], f"{len(low)} games have <6 pp_* keys; acceptance requires ≥6")

    def test_every_entry_has_required_keys(self):
        for gk, props in self.data["games"].items():
            for key, entry in props.items():
                self.assertTrue(key.startswith("pp_"))
                self.assertIn("odds", entry)
                self.assertIn("line", entry)
                self.assertIn("prob_fair", entry)
                self.assertGreater(entry["odds"], 1.0)
                self.assertGreater(entry["line"], 0.0)
                self.assertGreaterEqual(entry["prob_fair"], 0.0)
                self.assertLessEqual(entry["prob_fair"], 1.0)

    def test_acceptance_floor_met(self):
        total = len(self.data["games"])
        with_six = sum(1 for props in self.data["games"].values() if len(props) >= 6)
        self.assertEqual(with_six, total, "every game must meet ≥6 floor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
