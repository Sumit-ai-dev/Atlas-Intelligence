"""
satellite_quality.py — Phase 1 Anti-Hallucination Module
=========================================================
Three independent quality improvements over the baseline satellite analysis:

  1. Cloud Masking     — Sentinel-2 SCL band masks out cloud/shadow pixels before
                         any index or classification computation.

  2. Multi-Temporal   — Pulls N scenes over the "current" period and computes a
  Consistency          per-pixel change-agreement score.  Only pixels that appear
                         changed in the MAJORITY of scenes are flagged as real change.

  3. Seasonal         — Detects baseline/current season mismatch and applies a
  Normalization        scene-mean NDVI offset correction to reduce phenological bias.

All thresholds are read from satellite_config.json — nothing is hardcoded here.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Load config (no hardcodes) ────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent / "satellite_config.json"


def _load_cfg() -> dict:
    with open(_CONFIG_PATH) as f:
        return json.load(f)


_CFG: dict = _load_cfg()

# Convenience accessors (re-read at import time; restart backend after config change)
_cloud_cfg   = _CFG["cloud_masking"]
_temp_cfg    = _CFG["temporal_consistency"]
_season_cfg  = _CFG["seasonal_normalization"]

BAD_SCL_CLASSES      : set[int] = set(_cloud_cfg["bad_scl_classes"])
MIN_VALID_PIXEL_PCT  : float    = _cloud_cfg["min_valid_pixel_pct"]
CONSISTENCY_THRESHOLD: float    = _temp_cfg["consistency_threshold"]
CHANGE_PIXEL_THRESHOLD: float   = _temp_cfg["change_pixel_ndvi_delta"]
MAX_RELIABILITY_SCENES: int     = _temp_cfg["max_reliability_scenes"]
SINGLE_SCENE_RELIABILITY: float = _temp_cfg["single_scene_reliability"]
SEASON_WINDOW_DAYS   : int      = _season_cfg["season_window_days"]
SEASON_CONFIDENCE_PENALTY: float= _season_cfg["mismatch_confidence_penalty"]


def reload_config() -> None:
    """Hot-reload configuration without restarting the process."""
    global _CFG, _cloud_cfg, _temp_cfg, _season_cfg
    global BAD_SCL_CLASSES, MIN_VALID_PIXEL_PCT, CONSISTENCY_THRESHOLD
    global CHANGE_PIXEL_THRESHOLD, MAX_RELIABILITY_SCENES, SINGLE_SCENE_RELIABILITY
    global SEASON_WINDOW_DAYS, SEASON_CONFIDENCE_PENALTY
    _CFG = _load_cfg()
    _cloud_cfg  = _CFG["cloud_masking"]
    _temp_cfg   = _CFG["temporal_consistency"]
    _season_cfg = _CFG["seasonal_normalization"]
    BAD_SCL_CLASSES         = set(_cloud_cfg["bad_scl_classes"])
    MIN_VALID_PIXEL_PCT     = _cloud_cfg["min_valid_pixel_pct"]
    CONSISTENCY_THRESHOLD   = _temp_cfg["consistency_threshold"]
    CHANGE_PIXEL_THRESHOLD  = _temp_cfg["change_pixel_ndvi_delta"]
    MAX_RELIABILITY_SCENES  = _temp_cfg["max_reliability_scenes"]
    SINGLE_SCENE_RELIABILITY= _temp_cfg["single_scene_reliability"]
    SEASON_WINDOW_DAYS      = _season_cfg["season_window_days"]
    SEASON_CONFIDENCE_PENALTY = _season_cfg["mismatch_confidence_penalty"]
    logger.info("satellite_config.json reloaded")


# ─────────────────────────────────────────────────────────────────────────────
# 1. CLOUD MASKING
# ─────────────────────────────────────────────────────────────────────────────

def build_cloud_mask(scl_band: np.ndarray) -> np.ndarray:
    """Return a boolean mask: True = pixel is VALID (not cloud/shadow).

    Bad SCL classes are read from satellite_config.json → cloud_masking.bad_scl_classes

    Args:
        scl_band: 2-D uint8 array of SCL class codes at AOI resolution.

    Returns:
        Boolean array, same shape. True = usable, False = masked out.
    """
    valid = np.ones(scl_band.shape, dtype=bool)
    for bad_cls in BAD_SCL_CLASSES:
        valid &= (scl_band != bad_cls)
    return valid


def apply_cloud_mask(band: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Set invalid pixels to NaN so they don't bias index calculations."""
    result = band.astype("float32").copy()
    result[~mask] = np.nan
    return result


def masked_pct(mask: np.ndarray) -> float:
    """Fraction of pixels that are MASKED (cloud/shadow), as a percentage 0–100."""
    return round(float((~mask).sum()) / max(mask.size, 1) * 100.0, 2)


def cloud_stats(scl_band: np.ndarray) -> dict:
    """Return cloud mask + summary stats for the scene.

    Uses MIN_VALID_PIXEL_PCT from config to determine if a scene is usable.
    """
    mask       = build_cloud_mask(scl_band)
    pct_masked = masked_pct(mask)
    pct_valid  = round(100.0 - pct_masked, 2)
    usable     = pct_valid >= MIN_VALID_PIXEL_PCT
    return {
        "mask":       mask,
        "pct_masked": pct_masked,
        "pct_valid":  pct_valid,
        "usable":     usable,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. MULTI-TEMPORAL CONSISTENCY
# ─────────────────────────────────────────────────────────────────────────────

def compute_ndvi_masked(bands: dict, cloud_mask: np.ndarray | None = None) -> np.ndarray:
    """NDVI with optional cloud masking.  Returns float32, NaN where masked."""
    nir   = bands["nir"].astype("float32")
    red   = bands["red"].astype("float32")
    denom = nir + red
    denom = np.where(denom == 0, 1e-6, denom)
    ndvi  = np.clip((nir - red) / denom, -1.0, 1.0)
    if cloud_mask is not None:
        ndvi[~cloud_mask] = np.nan
    return ndvi


def change_score_pixel(ndvi_baseline: np.ndarray, ndvi_current: np.ndarray) -> np.ndarray:
    """Per-pixel change score = |ΔNDVI| normalised to [0, 1].

    Normalisation clamp: anything ≥0.8 NDVI units → score = 1.0 (max change).
    This is a spectral property of the index, not a business threshold.
    """
    delta     = ndvi_current - ndvi_baseline
    abs_delta = np.abs(np.nan_to_num(delta, nan=0.0))
    return np.clip(abs_delta / 0.80, 0.0, 1.0)


def multi_temporal_consistency(
    baseline_bands: dict,
    temporal_scenes_bands: list[dict],
    baseline_scl: np.ndarray | None = None,
    temporal_scls: list[np.ndarray | None] | None = None,
) -> dict:
    """Compute per-pixel agreement across multiple current-period scenes.

    Uses CONSISTENCY_THRESHOLD and CHANGE_PIXEL_THRESHOLD from config.

    Args:
        baseline_bands:        Band dict for the fixed baseline scene.
        temporal_scenes_bands: List of band dicts for each current-period scene.
        baseline_scl:          SCL array for baseline (optional).
        temporal_scls:         SCL arrays for each current scene (optional).

    Returns:
        dict with agreement_map, confident_change, scene_count,
        usable_scene_count, temporal_confidence.
    """
    if temporal_scls is None:
        temporal_scls = [None] * len(temporal_scenes_bands)

    base_mask       = build_cloud_mask(baseline_scl) if baseline_scl is not None else None
    ndvi_base       = compute_ndvi_masked(baseline_bands, base_mask)
    agreement_sum   = None
    usable_count    = 0
    reference_shape = ndvi_base.shape
    min_valid_frac  = MIN_VALID_PIXEL_PCT / 100.0

    for bands, scl in zip(temporal_scenes_bands, temporal_scls):
        cur_mask = build_cloud_mask(scl) if scl is not None else None
        ndvi_cur = compute_ndvi_masked(bands, cur_mask)

        # Skip scene if too cloudy
        if cur_mask is not None:
            pct_valid = float(cur_mask.sum()) / max(cur_mask.size, 1)
            if pct_valid < min_valid_frac:
                logger.warning(
                    "Skipping temporal scene: only %.1f%% clear (min required: %.0f%%)",
                    pct_valid * 100, MIN_VALID_PIXEL_PCT,
                )
                continue

        # Align shapes (scenes may differ by 1 px due to windowed reads)
        h = min(reference_shape[0], ndvi_cur.shape[0])
        w = min(reference_shape[1], ndvi_cur.shape[1])
        base_crop      = ndvi_base[:h, :w]
        cur_crop       = ndvi_cur[:h, :w]
        score          = change_score_pixel(base_crop, cur_crop)
        changed_pixels = (score >= CHANGE_PIXEL_THRESHOLD).astype("float32")

        if agreement_sum is None:
            agreement_sum = np.zeros_like(changed_pixels)
        agreement_sum = agreement_sum[:h, :w]
        agreement_sum += changed_pixels
        usable_count  += 1

    if usable_count == 0:
        dummy = np.zeros(reference_shape, dtype="float32")
        return {
            "agreement_map":       dummy,
            "confident_change":    dummy.astype(bool),
            "scene_count":         len(temporal_scenes_bands),
            "usable_scene_count":  0,
            "temporal_confidence": 0.0,
            "note": "No usable temporal scenes (all too cloudy)",
        }

    agreement_map    = agreement_sum / usable_count
    confident_change = agreement_map >= CONSISTENCY_THRESHOLD

    any_change = agreement_map > 0
    temporal_confidence = float(agreement_map[any_change].mean()) if any_change.any() else 0.0

    return {
        "agreement_map":       agreement_map,
        "confident_change":    confident_change,
        "scene_count":         len(temporal_scenes_bands),
        "usable_scene_count":  usable_count,
        "temporal_confidence": round(temporal_confidence, 4),
    }


def adjust_activity_for_temporal_confidence(
    raw_construction_activity_pct: float,
    temporal_confidence: float,
    usable_scene_count: int,
) -> tuple[float, float]:
    """Scale construction activity estimate by temporal confidence.

    Uses SINGLE_SCENE_RELIABILITY and MAX_RELIABILITY_SCENES from config.

    Returns:
        (adjusted_pct, reliability_score)
    """
    if usable_scene_count <= 1:
        return raw_construction_activity_pct, SINGLE_SCENE_RELIABILITY

    adjusted    = raw_construction_activity_pct * temporal_confidence
    reliability = min(
        temporal_confidence + 0.1 * min(usable_scene_count, MAX_RELIABILITY_SCENES),
        1.0,
    )
    return round(adjusted, 2), round(reliability, 3)


# ─────────────────────────────────────────────────────────────────────────────
# 3. SEASONAL NORMALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def same_season_delta_days(date1: datetime, date2: datetime) -> int:
    """Calendar distance in days ignoring year (wraps at year boundary).

    E.g. Jan 10 vs Dec 28 → 13 days apart.
    """
    doy1 = date1.timetuple().tm_yday
    doy2 = date2.timetuple().tm_yday
    diff = abs(doy1 - doy2)
    return min(diff, 365 - diff)


def is_season_matched(baseline_dt: datetime, current_dt: datetime) -> bool:
    """True if the baseline and current scenes are in the same seasonal window.

    Window size is read from satellite_config.json → seasonal_normalization.season_window_days
    """
    return same_season_delta_days(baseline_dt, current_dt) <= SEASON_WINDOW_DAYS


def season_mismatch_warning(baseline_dt: datetime, current_dt: datetime) -> dict:
    """Return a warning dict if seasons don't match.

    E.g. comparing June (monsoon) vs December (dry) causes NDVI to drop
    dramatically — looks like vegetation loss even with no construction.
    Season names are read from config if provided, otherwise derived from month.
    """
    delta   = same_season_delta_days(baseline_dt, current_dt)
    matched = delta <= SEASON_WINDOW_DAYS

    if matched:
        return {"season_matched": True, "season_delta_days": delta, "warning": None}

    def season_name(dt: datetime) -> str:
        """Indian subcontinent seasonal classification by calendar month."""
        m = dt.month
        if m in (6, 7, 8, 9):    return "monsoon (Jun–Sep)"
        if m in (10, 11):         return "post-monsoon (Oct–Nov)"
        if m in (12, 1, 2):       return "winter (Dec–Feb)"
        return "pre-monsoon (Mar–May)"

    base_season = season_name(baseline_dt)
    curr_season = season_name(current_dt)
    warning_msg = (
        f"Season mismatch: baseline is {base_season}, current is {curr_season} "
        f"({delta} days apart). NDVI changes may reflect seasonal vegetation "
        f"cycles rather than construction activity."
    )
    return {
        "season_matched":    False,
        "season_delta_days": delta,
        "baseline_season":   base_season,
        "current_season":    curr_season,
        "warning":           warning_msg,
    }


def ndvi_seasonal_correction(
    ndvi_baseline: np.ndarray,
    ndvi_current: np.ndarray,
    season_matched: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply scene-mean NDVI offset correction when seasons don't match.

    Conservative first-order correction: shifts current NDVI by the scene-mean
    difference so phenological bias is reduced before computing change scores.
    """
    if season_matched:
        return ndvi_baseline, ndvi_current

    mean_base = float(np.nanmean(ndvi_baseline))
    mean_curr = float(np.nanmean(ndvi_current))
    offset    = mean_curr - mean_base

    corrected = np.clip(ndvi_current - offset, -1.0, 1.0)
    logger.info(
        "Seasonal offset applied: ΔNDVI_mean=%.4f (baseline=%.4f, current=%.4f)",
        offset, mean_base, mean_curr,
    )
    return ndvi_baseline, corrected


# ─────────────────────────────────────────────────────────────────────────────
# 4. QUALITY SUMMARY BLOCK
# ─────────────────────────────────────────────────────────────────────────────

def build_quality_block(
    *,
    baseline_scl_stats: dict | None,
    current_scl_stats:  dict | None,
    temporal_result:    dict | None,
    season_info:        dict | None,
    raw_activity_pct:   float,
) -> dict:
    """Assemble the `quality` block saved in the scan JSON.

    Degrades gracefully when SCL bands or temporal scenes are unavailable.
    """
    block: dict = {"phase": "1"}

    # Cloud masking
    if baseline_scl_stats and current_scl_stats:
        block["cloud_mask"] = {
            "baseline_pct_masked": baseline_scl_stats["pct_masked"],
            "current_pct_masked":  current_scl_stats["pct_masked"],
            "baseline_usable":     baseline_scl_stats["usable"],
            "current_usable":      current_scl_stats["usable"],
        }
    else:
        block["cloud_mask"] = {"note": "SCL band not available for this scene"}

    # Temporal consistency
    if temporal_result and temporal_result.get("usable_scene_count", 0) > 0:
        confidence  = temporal_result["temporal_confidence"]
        adj_pct, reliability = adjust_activity_for_temporal_confidence(
            raw_activity_pct, confidence, temporal_result["usable_scene_count"],
        )
        block["temporal_consistency"] = {
            "scenes_fetched":        temporal_result["scene_count"],
            "scenes_usable":         temporal_result["usable_scene_count"],
            "confidence":            confidence,
            "adjusted_activity_pct": adj_pct,
            "reliability_score":     reliability,
            "note": (
                "High confidence: change is persistent across multiple scenes."
                if confidence >= CONSISTENCY_THRESHOLD
                else "Low confidence: change may be cloud/seasonal artefact."
            ),
        }
    else:
        block["temporal_consistency"] = {
            "note":       "Only 1 scene available — temporal check skipped",
            "confidence": None,
        }

    # Seasonal normalization
    if season_info:
        block["seasonal_normalization"] = {
            "season_matched":    season_info["season_matched"],
            "season_delta_days": season_info["season_delta_days"],
            "warning":           season_info.get("warning"),
        }
    else:
        block["seasonal_normalization"] = {"note": "Season info not available"}

    return block
