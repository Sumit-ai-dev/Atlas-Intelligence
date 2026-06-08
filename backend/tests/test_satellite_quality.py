"""
tests/test_satellite_quality.py
================================
Unit tests for satellite_quality.py Phase 1 anti-hallucination module.
Tests run without network access — all inputs are synthetic numpy arrays.
"""

import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Make sure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import satellite_quality as sq


# ─────────────────────────────────────────────────────────────────────────────
# 1. CLOUD MASKING
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudMasking(unittest.TestCase):

    def _scl(self, codes: list[list[int]]) -> np.ndarray:
        return np.array(codes, dtype=np.uint8)

    def test_all_clear(self):
        """Scene with no bad pixels → all True mask."""
        scl = self._scl([[4, 5, 6], [4, 5, 6]])   # veg, not-veg, water (all fine)
        mask = sq.build_cloud_mask(scl)
        self.assertTrue(mask.all(), "Expected all pixels to be valid (no clouds)")

    def test_all_cloud(self):
        """Scene with all cloud pixels → all False mask."""
        scl = self._scl([[9, 9], [9, 9]])   # CLOUD_HIGH_PROB
        mask = sq.build_cloud_mask(scl)
        self.assertFalse(mask.any(), "Expected all pixels to be masked (cloud)")

    def test_mixed(self):
        """Mixed: clear row + cloud row."""
        scl = self._scl([
            [4, 5, 6],    # valid
            [9, 9, 9],    # cloud
        ])
        mask = sq.build_cloud_mask(scl)
        self.assertTrue(mask[0].all(),  "Row 0 should be valid")
        self.assertFalse(mask[1].any(), "Row 1 should be masked (cloud)")

    def test_shadow_masked(self):
        """SCL class 3 (shadow) must be excluded."""
        scl = self._scl([[3, 4]])
        mask = sq.build_cloud_mask(scl)
        self.assertFalse(mask[0, 0], "Shadow pixel should be masked")
        self.assertTrue(mask[0, 1],  "Valid pixel should be unmasked")

    def test_masked_pct_all_cloudy(self):
        scl = self._scl([[9, 9, 9], [9, 9, 9]])
        mask = sq.build_cloud_mask(scl)
        self.assertEqual(sq.masked_pct(mask), 100.0)

    def test_masked_pct_half_cloudy(self):
        scl = self._scl([[9, 4]])   # 1 cloud, 1 valid
        mask = sq.build_cloud_mask(scl)
        self.assertAlmostEqual(sq.masked_pct(mask), 50.0)

    def test_cloud_stats_usable_when_clear(self):
        scl = np.full((10, 10), 4, dtype=np.uint8)  # all valid
        stats = sq.cloud_stats(scl)
        self.assertTrue(stats["usable"])
        self.assertEqual(stats["pct_masked"], 0.0)
        self.assertEqual(stats["pct_valid"], 100.0)

    def test_cloud_stats_not_usable_when_mostly_cloudy(self):
        """More than min_valid_pixel_pct masked → usable=False."""
        scl = np.full((10, 10), 9, dtype=np.uint8)   # all cloud
        stats = sq.cloud_stats(scl)
        self.assertFalse(stats["usable"])

    def test_bad_scl_classes_from_config(self):
        """BAD_SCL_CLASSES must be loaded from config, not hardcoded."""
        self.assertIsInstance(sq.BAD_SCL_CLASSES, set)
        self.assertGreater(len(sq.BAD_SCL_CLASSES), 0)
        # Cloud high prob (9) must always be bad
        self.assertIn(9, sq.BAD_SCL_CLASSES)


# ─────────────────────────────────────────────────────────────────────────────
# 2. MULTI-TEMPORAL CONSISTENCY
# ─────────────────────────────────────────────────────────────────────────────

def _make_bands(nir_val: float, red_val: float, shape=(8, 8)) -> dict:
    """Create synthetic band dict with uniform NIR/red values."""
    return {
        "nir":   np.full(shape, nir_val, dtype="float32"),
        "red":   np.full(shape, red_val, dtype="float32"),
        "green": np.full(shape, 0.05, dtype="float32"),
        "blue":  np.full(shape, 0.03, dtype="float32"),
        "swir":  np.full(shape, 0.10, dtype="float32"),
    }


class TestNdviMasked(unittest.TestCase):

    def test_pure_vegetation(self):
        bands = _make_bands(nir_val=0.5, red_val=0.1)
        ndvi  = sq.compute_ndvi_masked(bands)
        expected = (0.5 - 0.1) / (0.5 + 0.1)   # 0.667
        np.testing.assert_allclose(ndvi, expected, atol=1e-4)

    def test_cloud_pixels_become_nan(self):
        bands = _make_bands(0.5, 0.1, shape=(4, 4))
        mask  = np.ones((4, 4), dtype=bool)
        mask[0, 0] = False   # mask one pixel
        ndvi = sq.compute_ndvi_masked(bands, mask)
        self.assertTrue(np.isnan(ndvi[0, 0]),  "Masked pixel should be NaN")
        self.assertFalse(np.isnan(ndvi[1, 1]), "Valid pixel should not be NaN")

    def test_ndvi_clipped_to_minus1_plus1(self):
        bands = _make_bands(nir_val=0.0, red_val=0.5)  # very low NDVI
        ndvi  = sq.compute_ndvi_masked(bands)
        self.assertGreaterEqual(float(ndvi.min()), -1.0)
        self.assertLessEqual(float(ndvi.max()), 1.0)


class TestChangeScore(unittest.TestCase):

    def test_no_change(self):
        ndvi = np.full((4, 4), 0.5, dtype="float32")
        score = sq.change_score_pixel(ndvi, ndvi.copy())
        np.testing.assert_allclose(score, 0.0, atol=1e-5)

    def test_max_change(self):
        baseline = np.full((4, 4), 0.8, dtype="float32")
        current  = np.full((4, 4), 0.0, dtype="float32")
        score    = sq.change_score_pixel(baseline, current)
        # |0.8 - 0.0| / 0.8 = 1.0
        np.testing.assert_allclose(score, 1.0, atol=1e-5)

    def test_score_clipped_0_to_1(self):
        baseline = np.full((4, 4), 0.9, dtype="float32")
        current  = np.full((4, 4), -0.9, dtype="float32")
        score    = sq.change_score_pixel(baseline, current)
        self.assertLessEqual(float(score.max()), 1.0)
        self.assertGreaterEqual(float(score.min()), 0.0)


class TestMultiTemporalConsistency(unittest.TestCase):

    def _uniform_bands(self, nir, red):
        return _make_bands(nir, red, shape=(10, 10))

    def test_no_change_across_all_scenes(self):
        """All scenes identical to baseline → zero temporal_confidence."""
        baseline = self._uniform_bands(0.5, 0.1)   # high vegetation
        scenes   = [self._uniform_bands(0.5, 0.1) for _ in range(3)]
        result   = sq.multi_temporal_consistency(baseline, scenes)
        self.assertEqual(result["usable_scene_count"], 3)
        self.assertAlmostEqual(result["temporal_confidence"], 0.0, places=3)

    def test_consistent_construction_signal(self):
        """All scenes show vegetation → bare/built transition → high confidence."""
        baseline = self._uniform_bands(nir=0.5, red=0.1)   # NDVI ≈ 0.67 (veg)
        # Current scenes all show construction (low NDVI)
        scenes   = [self._uniform_bands(nir=0.1, red=0.4) for _ in range(4)]  # NDVI ≈ -0.6
        result   = sq.multi_temporal_consistency(baseline, scenes)
        self.assertEqual(result["usable_scene_count"], 4)
        self.assertGreater(result["temporal_confidence"], sq.CONSISTENCY_THRESHOLD,
                          "Construction signal persisting across 4 scenes should be high-confidence")
        self.assertTrue(result["confident_change"].all(),
                       "All pixels should be flagged as confidently changed")

    def test_noisy_single_scene_filtered(self):
        """1-of-4 scenes shows change → below consistency threshold."""
        baseline = self._uniform_bands(nir=0.5, red=0.1)
        noisy    = self._uniform_bands(nir=0.1, red=0.4)   # only this one changed
        stable   = self._uniform_bands(nir=0.5, red=0.1)
        scenes   = [noisy, stable, stable, stable]
        result   = sq.multi_temporal_consistency(baseline, scenes)
        # 1/4 agreement < CONSISTENCY_THRESHOLD → not confident change
        self.assertFalse(result["confident_change"].any(),
                        "1-of-4 scenes showing change should not be confident change")

    def test_all_scenes_too_cloudy_returns_fallback(self):
        """All scenes >50% cloud → returns usable_scene_count=0."""
        baseline = self._uniform_bands(0.5, 0.1)
        scenes   = [self._uniform_bands(0.5, 0.1)]
        # 100% cloud mask (all False)
        scls     = [np.full((10, 10), 9, dtype=np.uint8)]
        result   = sq.multi_temporal_consistency(
            baseline, scenes, temporal_scls=scls
        )
        self.assertEqual(result["usable_scene_count"], 0)
        self.assertIn("note", result)

    def test_no_scenes_returns_gracefully(self):
        """Empty temporal stack → should not crash."""
        baseline = self._uniform_bands(0.5, 0.1)
        result   = sq.multi_temporal_consistency(baseline, [])
        self.assertEqual(result["usable_scene_count"], 0)


class TestAdjustActivity(unittest.TestCase):

    def test_single_scene_returns_raw(self):
        pct, rel = sq.adjust_activity_for_temporal_confidence(50.0, 0.8, 1)
        self.assertEqual(pct, 50.0)
        self.assertEqual(rel, sq.SINGLE_SCENE_RELIABILITY)

    def test_high_confidence_scales_correctly(self):
        pct, rel = sq.adjust_activity_for_temporal_confidence(100.0, 1.0, 5)
        self.assertAlmostEqual(pct, 100.0, places=1)
        self.assertLessEqual(rel, 1.0)

    def test_low_confidence_scales_down(self):
        pct, rel = sq.adjust_activity_for_temporal_confidence(100.0, 0.3, 5)
        self.assertLess(pct, 50.0, "Low confidence should scale activity way down")


# ─────────────────────────────────────────────────────────────────────────────
# 3. SEASONAL NORMALIZATION
# ─────────────────────────────────────────────────────────────────────────────

class TestSeasonalDelta(unittest.TestCase):

    def _dt(self, month: int, day: int) -> datetime:
        return datetime(2023, month, day, tzinfo=timezone.utc)

    def test_same_day_different_year(self):
        d1 = datetime(2020, 6, 15, tzinfo=timezone.utc)
        d2 = datetime(2026, 6, 15, tzinfo=timezone.utc)
        delta = sq.same_season_delta_days(d1, d2)
        # June 15 is DOY 167 in leap year (2020) and DOY 166 in non-leap (2026)
        # so delta can be 0 or 1 depending on leap-year DOY shift
        self.assertLessEqual(delta, 1, f"Same calendar date across years should be ≤1 day apart, got {delta}")


    def test_year_boundary_wraps(self):
        # Jan 5 vs Dec 28 → 8 days, not 357
        d1 = datetime(2023, 1, 5, tzinfo=timezone.utc)
        d2 = datetime(2022, 12, 28, tzinfo=timezone.utc)
        delta = sq.same_season_delta_days(d1, d2)
        self.assertLessEqual(delta, 15,
                            f"Year-boundary wrap should give ≤15 days, got {delta}")

    def test_june_vs_december_far(self):
        d_june = self._dt(6, 15)
        d_dec  = self._dt(12, 15)
        delta  = sq.same_season_delta_days(d_june, d_dec)
        self.assertGreater(delta, sq.SEASON_WINDOW_DAYS,
                          "June vs December should be far apart in calendar")


class TestIsSeasonMatched(unittest.TestCase):

    def test_matched_same_month(self):
        d1 = datetime(2020, 6, 1, tzinfo=timezone.utc)
        d2 = datetime(2026, 6, 15, tzinfo=timezone.utc)
        self.assertTrue(sq.is_season_matched(d1, d2))

    def test_not_matched_monsoon_vs_winter(self):
        d1 = datetime(2020, 7, 15, tzinfo=timezone.utc)   # monsoon
        d2 = datetime(2026, 1, 15, tzinfo=timezone.utc)   # winter
        self.assertFalse(sq.is_season_matched(d1, d2))


class TestSeasonMismatchWarning(unittest.TestCase):

    def test_matched_returns_no_warning(self):
        d1 = datetime(2020, 6, 1, tzinfo=timezone.utc)
        d2 = datetime(2026, 6, 20, tzinfo=timezone.utc)
        result = sq.season_mismatch_warning(d1, d2)
        self.assertTrue(result["season_matched"])
        self.assertIsNone(result["warning"])

    def test_mismatch_returns_warning(self):
        d1 = datetime(2020, 7, 1, tzinfo=timezone.utc)    # monsoon
        d2 = datetime(2026, 12, 15, tzinfo=timezone.utc)  # winter
        result = sq.season_mismatch_warning(d1, d2)
        self.assertFalse(result["season_matched"])
        self.assertIsNotNone(result["warning"])
        self.assertIn("mismatch", result["warning"].lower())

    def test_mismatch_includes_season_names(self):
        d1 = datetime(2020, 7, 1, tzinfo=timezone.utc)
        d2 = datetime(2026, 1, 15, tzinfo=timezone.utc)
        result = sq.season_mismatch_warning(d1, d2)
        self.assertIn("baseline_season", result)
        self.assertIn("current_season", result)


class TestNdviSeasonalCorrection(unittest.TestCase):

    def test_matched_returns_unchanged(self):
        base = np.array([0.4, 0.5, 0.6])
        curr = np.array([0.2, 0.3, 0.4])
        b_out, c_out = sq.ndvi_seasonal_correction(base, curr, season_matched=True)
        np.testing.assert_array_equal(b_out, base)
        np.testing.assert_array_equal(c_out, curr)

    def test_mismatch_shifts_current_mean(self):
        """After correction, scene means should be closer."""
        base = np.array([0.6, 0.6, 0.6], dtype="float32")   # mean = 0.6
        curr = np.array([0.2, 0.2, 0.2], dtype="float32")   # mean = 0.2 (winter season bias)
        b_out, c_out = sq.ndvi_seasonal_correction(base, curr, season_matched=False)
        # offset = 0.2 - 0.6 = -0.4; corrected = 0.2 - (-0.4) = 0.6
        np.testing.assert_allclose(c_out, [0.6, 0.6, 0.6], atol=1e-4)

    def test_corrected_clipped_to_valid_range(self):
        base = np.array([-0.8, -0.8], dtype="float32")
        curr = np.array([0.9, 0.9], dtype="float32")
        _, c_out = sq.ndvi_seasonal_correction(base, curr, season_matched=False)
        self.assertLessEqual(float(c_out.max()), 1.0)
        self.assertGreaterEqual(float(c_out.min()), -1.0)


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONFIG LOADING
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigDriven(unittest.TestCase):

    def test_all_constants_from_config(self):
        """Verify key constants are actually read from the JSON config."""
        from satellite_quality import (
            CONSISTENCY_THRESHOLD, CHANGE_PIXEL_THRESHOLD,
            SEASON_WINDOW_DAYS, MIN_VALID_PIXEL_PCT,
            BAD_SCL_CLASSES, SINGLE_SCENE_RELIABILITY,
        )
        cfg = sq._load_cfg()
        self.assertEqual(CONSISTENCY_THRESHOLD, cfg["temporal_consistency"]["consistency_threshold"])
        self.assertEqual(CHANGE_PIXEL_THRESHOLD, cfg["temporal_consistency"]["change_pixel_ndvi_delta"])
        self.assertEqual(SEASON_WINDOW_DAYS, cfg["seasonal_normalization"]["season_window_days"])
        self.assertEqual(MIN_VALID_PIXEL_PCT, cfg["cloud_masking"]["min_valid_pixel_pct"])
        self.assertEqual(BAD_SCL_CLASSES, set(cfg["cloud_masking"]["bad_scl_classes"]))

    def test_reload_config(self):
        """reload_config() should not crash and should re-read the file."""
        sq.reload_config()   # just verify no exception


if __name__ == "__main__":
    unittest.main(verbosity=2)
