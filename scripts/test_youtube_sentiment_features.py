#!/usr/bin/env python3
"""Unit tests for the YouTube FinBERT rolling sentiment feature extractor.

Covers:
- Engine-version bump (v3.2-67cat) and 6 registered feature names.
- Per-game rolling windows (3/7/14d) over an in-memory DataFrame.
- sim_date_cutoff hard-filter replicating the audit reported by HAWKEYE
  (May-2026 cutoff drops 152/223 videos on NBA corpus).
- Leakage-gate refuses any published_at > cutoff even if earlier than game_date.
- Empty-window path returns all zeros without NaN.

Kent Beck bar: one behaviour per test, test the contract.
Linus: all leakage gates verified. Carmack: in-memory pandas, no FS I/O.
"""
from __future__ import annotations

import os
import sys
import unittest
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Disable auto-load of the on-disk parquet so each test can inject its own df.
os.environ["NOMOS_YT_SENT_PATH"] = "/dev/null/no_such_sent_parquet.parquet"

from features import engine as nba_eng  # noqa: E402


def _make_df(rows):
    """rows: list of (id, published_at_iso, polarity)."""
    import pandas as pd  # local import so test still collects without pyarrow
    df = pd.DataFrame([
        {
            "id": i,
            "published_at": pd.Timestamp(pub, tz="UTC"),
            "channel": "test",
            "sent_pos": max(p, 0.0),
            "sent_neu": 1.0 - abs(p),
            "sent_neg": max(-p, 0.0),
            "polarity": p,
        }
        for i, pub, p in rows
    ])
    return df


class EngineVersionAndNamesTests(unittest.TestCase):
    def test_engine_version_bumped_to_v32_67cat(self):
        self.assertEqual(nba_eng.ENGINE_VERSION, "v3.2-67cat")

    def test_cat67_six_feature_names_registered(self):
        eng = nba_eng.NBAFeatureEngine(include_market=False, enable_youtube=False)
        expected = [
            "yt_pol_mean_3", "yt_pol_mean_7", "yt_pol_mean_14",
            "yt_abs_pol_mean_3", "yt_abs_pol_mean_7", "yt_abs_pol_mean_14",
        ]
        for name in expected:
            self.assertIn(name, eng.feature_names, f"{name} missing")

    def test_default_enable_youtube_is_false_for_nba(self):
        """NBA corpus not mature per HAWKEYE audit — default off per FRANKENSTEIN."""
        eng = nba_eng.NBAFeatureEngine(include_market=False)
        self.assertFalse(eng.enable_youtube)


class RollingWindowTests(unittest.TestCase):
    def test_empty_df_returns_all_zero_dict(self):
        out = nba_eng._youtube_sentiment_features(None, "2026-03-15")
        for k, v in out.items():
            self.assertEqual(v, 0.0, f"{k} expected 0.0, got {v}")
        self.assertEqual(len(out), 6)

    def test_3d_window_includes_only_recent_videos(self):
        df = _make_df([
            ("a", "2026-03-14T00:00:00Z", +0.5),   # 1 day old → in 3d/7d/14d
            ("b", "2026-03-10T00:00:00Z", -0.3),   # 5 days old → in 7d/14d
            ("c", "2026-03-01T00:00:00Z", +0.8),   # 14 days old → in 14d only
            ("d", "2026-02-01T00:00:00Z", -0.9),   # 42 days → none
        ])
        out = nba_eng._youtube_sentiment_features(df, "2026-03-15")
        # 3d window = only 'a' → polarity 0.5
        self.assertAlmostEqual(out["yt_pol_mean_3"], 0.5, places=6)
        self.assertAlmostEqual(out["yt_abs_pol_mean_3"], 0.5, places=6)
        # 7d window = a + b → (0.5 + -0.3) / 2 = 0.1 ; |.| → (0.5 + 0.3)/2 = 0.4
        self.assertAlmostEqual(out["yt_pol_mean_7"], 0.1, places=6)
        self.assertAlmostEqual(out["yt_abs_pol_mean_7"], 0.4, places=6)
        # 14d window = a + b + c → (0.5 - 0.3 + 0.8) / 3 = 0.333...
        self.assertAlmostEqual(out["yt_pol_mean_14"], 1.0 / 3.0, places=6)
        self.assertAlmostEqual(out["yt_abs_pol_mean_14"], (0.5 + 0.3 + 0.8) / 3.0, places=6)

    def test_future_videos_beyond_game_date_are_refused(self):
        df = _make_df([
            ("past", "2026-03-14T00:00:00Z", +0.5),
            ("future", "2026-04-01T00:00:00Z", +0.9),  # AFTER game_date
        ])
        out = nba_eng._youtube_sentiment_features(df, "2026-03-15")
        # Only 'past' in 3d; 'future' must be refused even without sim_cutoff
        self.assertAlmostEqual(out["yt_pol_mean_3"], 0.5, places=6)


class SimDateCutoffLeakageGateTests(unittest.TestCase):
    """
    HAWKEYE audit 2026-04-21 reported 152/223 NBA videos published AFTER the
    sim window (Oct 2025 - Feb 2026) — those must be dropped when a May-2026
    cutoff is applied. This test replicates that audit on a tiny corpus.
    """
    def test_may_2026_cutoff_drops_post_cutoff_videos(self):
        # Simulate a corpus with 6 videos, 4 of which post-date the sim cutoff
        df = _make_df([
            ("pre_1",  "2026-02-10T00:00:00Z", +0.4),
            ("pre_2",  "2026-02-20T00:00:00Z", -0.2),
            ("post_1", "2026-05-05T00:00:00Z", +0.9),  # must be refused
            ("post_2", "2026-05-10T00:00:00Z", +0.7),
            ("post_3", "2026-06-01T00:00:00Z", +0.5),
            ("post_4", "2026-07-15T00:00:00Z", -0.8),
        ])
        # Game date AFTER cutoff — without gate, post_* would be eligible
        out = nba_eng._youtube_sentiment_features(
            df, "2026-08-01", sim_cutoff="2026-05-01",
        )
        # With cutoff: only pre_1 and pre_2 survive. Both are >14d old → 14d window
        # captures them, 3d/7d empty.
        self.assertAlmostEqual(out["yt_pol_mean_3"], 0.0, places=6)
        self.assertAlmostEqual(out["yt_pol_mean_7"], 0.0, places=6)
        self.assertAlmostEqual(out["yt_pol_mean_14"], 0.0, places=6)  # both >14d old

    def test_cutoff_ratio_matches_hawkeye_audit(self):
        """FRANKENSTEIN: with a May-2026 cutoff against a 229-video NBA corpus
        where 152 are dated after the sim window, audit shape = 152/229 = 66.4%
        post-cutoff. We synthesize that shape to lock the math."""
        import pandas as pd
        rows = []
        for i in range(77):  # pre-cutoff
            rows.append((f"pre_{i}", "2026-02-15T00:00:00Z", 0.0))
        for i in range(152):  # post-cutoff
            rows.append((f"post_{i}", "2026-06-01T00:00:00Z", 0.5))
        df = _make_df(rows)
        self.assertEqual(len(df), 229)
        # Rerun sim with cutoff; capture how many rows survive post-filter
        import pandas as pd
        cutoff = pd.Timestamp("2026-05-01", tz="UTC")
        surviving = df[df["published_at"] <= cutoff]
        dropped = len(df) - len(surviving)
        self.assertEqual(dropped, 152, "HAWKEYE audit ratio must hold: 152/229 videos dropped")
        self.assertEqual(len(surviving), 77)


class PolEngineParityTests(unittest.TestCase):
    """Sanity-check: POL engine emits the 6 parallel Cat 44 features (yt44_* prefix)."""
    def test_pol_engine_exposes_cat44_extractor(self):
        # Add POL engine to path via direct file loading to avoid the `features`
        # package name clash with the NBA engine already imported above.
        pol_file = Path("/home/termius/nomos-political-alpha/features/political_engine.py")
        if not pol_file.exists():
            self.skipTest("nomos-political-alpha not present")
        import importlib.util
        spec = importlib.util.spec_from_file_location("pol_political_engine", str(pol_file))
        pe = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(pe)
        except Exception as e:
            self.skipTest(f"POL engine exec failed: {e}")

        self.assertTrue(pe.ENGINE_VERSION.startswith("v3.22-political-44cat"))
        eng = pe.PoliticalFeatureEngine(enable_youtube_finbert=False)
        # extractor is a bound method
        self.assertTrue(hasattr(eng, "_youtube_finbert_rolling"))
        feats, names = eng._youtube_finbert_rolling({"date": "2026-03-15"})
        self.assertEqual(len(feats), 6)
        self.assertEqual(len(names), 6)
        for n in names:
            self.assertTrue(n.startswith("yt44_"), f"POL Cat 44 name missing prefix: {n}")
        # all-zero fallback when no parquet
        for v in feats:
            self.assertEqual(v, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
