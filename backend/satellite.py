import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from satellite_quality import (
    build_quality_block,
    cloud_stats,
    is_season_matched,
    multi_temporal_consistency,
    ndvi_seasonal_correction,
    season_mismatch_warning,
    adjust_activity_for_temporal_confidence,
)

logger = logging.getLogger(__name__)

# ── Load configuration (all thresholds from satellite_config.json) ────────────
_CONFIG_PATH = Path(__file__).parent / "satellite_config.json"

def _load_cfg() -> dict:
    with open(_CONFIG_PATH) as f:
        return json.load(f)

_CFG = _load_cfg()
_stac_primary = _CFG["stac"]["primary_scene"]
_stac_stack   = _CFG["stac"]["temporal_stack"]
_lc_thresh    = _CFG["land_cover_thresholds"]
_alert_thresh = _CFG["alert_thresholds"]
_conf_cfg     = _CFG["confidence"]


STAC_URL   = _CFG["stac"]["url"]
COLLECTION = _CFG["stac"]["collection"]

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "satellite_cache"
CACHE_DIR.mkdir(exist_ok=True)
DPR_DIR = CACHE_DIR / "dpr"
DPR_DIR.mkdir(exist_ok=True)

# ── Project Registry Path ─────────────────────────────────────────────────────
_REGISTRY_PATH = BASE_DIR / "storage" / "projects_registry.json"


def _load_projects() -> dict:
    """
    Load projects from storage/projects_registry.json.
    Falls back to an empty dict if the file does not exist.
    """
    if not _REGISTRY_PATH.exists():
        logger.warning(
            "[satellite] storage/projects_registry.json not found. "
            "Run Phase 0 setup to initialise the storage layer."
        )
        return {}
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("projects", {})


def _save_projects(projects: dict) -> None:
    """
    Persist the full projects dict back to storage/projects_registry.json.
    Preserves the existing _meta block. Used by POST /projects/register (Phase 1).
    """
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _REGISTRY_PATH.exists():
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {"_meta": {"version": "1.0", "description": "Live project registry"}}
    existing["projects"] = projects
    with open(_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


class ProjectsProxy(dict):
    def _get_dict(self) -> dict:
        try:
            import policy_loader
            return policy_loader.get_projects_registry()
        except Exception:
            try:
                import policy_loader
                policy_loader.load_all()
                return policy_loader.get_projects_registry()
            except Exception:
                return _load_projects()

    def __getitem__(self, key):
        return self._get_dict()[key]

    def __setitem__(self, key, value):
        d = dict(self._get_dict())
        d[key] = value
        _save_projects(d)
        try:
            import policy_loader
            policy_loader.reload()
        except Exception:
            pass

    def __delitem__(self, key):
        d = dict(self._get_dict())
        del d[key]
        _save_projects(d)
        try:
            import policy_loader
            policy_loader.reload()
        except Exception:
            pass

    def __contains__(self, key):
        return key in self._get_dict()

    def __iter__(self):
        return iter(self._get_dict())

    def __len__(self):
        return len(self._get_dict())

    def keys(self):
        return self._get_dict().keys()

    def values(self):
        return self._get_dict().values()

    def items(self):
        return self._get_dict().items()

    def get(self, key, default=None):
        return self._get_dict().get(key, default)

    def pop(self, key, default=None):
        d = dict(self._get_dict())
        val = d.pop(key, default)
        _save_projects(d)
        try:
            import policy_loader
            policy_loader.reload()
        except Exception:
            pass
        return val

    def clear(self):
        _save_projects({})
        try:
            import policy_loader
            policy_loader.reload()
        except Exception:
            pass

    def update(self, *args, **kwargs):
        d = dict(self._get_dict())
        d.update(*args, **kwargs)
        _save_projects(d)
        try:
            import policy_loader
            policy_loader.reload()
        except Exception:
            pass

    def __repr__(self):
        return repr(self._get_dict())


PROJECTS = ProjectsProxy()


def reload_projects_from_registry() -> None:
    """
    Refresh the projects registry.
    Since PROJECTS is a live proxy, this function is now a no-op but kept
    for backward compatibility with existing callers.
    """
    logger.info("[satellite] PROJECTS live proxy is automatically synchronized.")



# Land cover class codes
WATER, VEGETATION, BARE_SOIL, BUILT_UP, OTHER = 0, 1, 2, 3, 4
CLASS_NAMES = {WATER: "water", VEGETATION: "vegetation", BARE_SOIL: "bare_soil", BUILT_UP: "built_up", OTHER: "other"}
CLASS_COLORS = {
    WATER: (40, 90, 200),
    VEGETATION: (40, 160, 60),
    BARE_SOIL: (200, 160, 80),
    BUILT_UP: (220, 60, 60),
    OTHER: (120, 120, 120),
}


def _bbox_in_src_crs(bbox_wgs84, src):
    return transform_bounds("EPSG:4326", src.crs, *bbox_wgs84, densify_pts=21)


def _search_scene(bbox, target_date, days_window=None, max_cloud=None):
    days_window = days_window or _stac_primary["days_window"]
    max_cloud   = max_cloud   or _stac_primary["max_cloud_pct"]
    max_items   = _stac_primary["max_items"]
    client = Client.open(STAC_URL)
    target = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
    start = (target - timedelta(days=days_window)).date().isoformat()
    end = (target + timedelta(days=days_window)).date().isoformat()
    search = client.search(
        collections=[COLLECTION],
        bbox=bbox,
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=max_items,
    )
    items = list(search.items())
    if not items:
        return None
    items.sort(key=lambda it: abs((it.datetime - target).days))
    return items[0]


def _search_sar_scene(bbox, target_date, days_window=None):
    import planetary_computer as pc
    days_window = days_window or 15
    # Use Microsoft Planetary Computer for SAR: it provides terrain-corrected (RTC) data 
    # which is properly georeferenced and ready to use. No API key needed for public data!
    client = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
    target = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
    start = (target - timedelta(days=days_window)).date().isoformat()
    end = (target + timedelta(days=days_window)).date().isoformat()
    
    search = client.search(
        collections=["sentinel-1-rtc"],
        bbox=bbox,
        datetime=f"{start}/{end}",
        max_items=10,
    )
    items = list(search.items())
    if not items:
        return None
    items.sort(key=lambda it: abs((it.datetime - target).days))
    return items[0]



def _search_temporal_stack(bbox, anchor_date_str: str, months_back: int = None, max_cloud: int = None) -> list:
    """Fetch one scene per month going back `months_back` months from anchor_date.

    Parameters default to satellite_config.json → stac.temporal_stack.
    Accepts higher cloud cover than the primary scene to maximise coverage.
    """
    months_back = months_back or _stac_stack["months_back"]
    max_cloud   = max_cloud   or _stac_stack["max_cloud_pct"]
    max_items_s = _stac_stack["max_items_search"]
    client = Client.open(STAC_URL)

    anchor = datetime.fromisoformat(anchor_date_str).replace(tzinfo=timezone.utc)
    start  = (anchor - timedelta(days=30 * months_back)).date().isoformat()
    end    = anchor.date().isoformat()
    search = client.search(
        collections=[COLLECTION],
        bbox=bbox,
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=max_items_s,
    )
    items = list(search.items())
    if not items:
        return []

    # De-duplicate: keep at most 1 scene per calendar month
    seen_months: set = set()
    stack = []
    items.sort(key=lambda it: it.datetime, reverse=True)  # newest first
    for it in items:
        month_key = (it.datetime.year, it.datetime.month)
        if month_key not in seen_months:
            seen_months.add(month_key)
            stack.append(it)
        if len(stack) >= months_back:
            break

    logger.info("Temporal stack: %d scenes fetched for %s", len(stack), anchor_date_str)
    return stack


def _read_band(asset_href, bbox_wgs84, target_shape=None):
    with rasterio.open(asset_href) as src:
        src_bounds = _bbox_in_src_crs(bbox_wgs84, src)
        win = from_bounds(*src_bounds, transform=src.transform)
        if target_shape is None:
            arr = src.read(1, window=win, boundless=True, fill_value=0)
        else:
            arr = src.read(
                1,
                window=win,
                out_shape=target_shape,
                resampling=Resampling.bilinear,
                boundless=True,
                fill_value=0,
            )
    # Sentinel-2 L2A reflectance: scale factor 0.0001 to get [0,1]
    return arr.astype("float32") / 10000.0


def _read_scene_bands(item, bbox):
    """Read optical bands + SCL cloud mask for a Sentinel-2 L2A item."""
    # 10 m bands set the reference shape; 20 m bands (SWIR, SCL) are resampled.
    with rasterio.open(item.assets["red"].href) as src:
        src_bounds = _bbox_in_src_crs(bbox, src)
        win = from_bounds(*src_bounds, transform=src.transform)
        ref_shape = (int(win.height), int(win.width))
    red   = _read_band(item.assets["red"].href,   bbox)
    nir   = _read_band(item.assets["nir"].href,   bbox)
    blue  = _read_band(item.assets["blue"].href,  bbox)
    green = _read_band(item.assets["green"].href, bbox)
    swir  = _read_band(item.assets["swir16"].href, bbox, target_shape=ref_shape)

    # SCL (Scene Classification Layer) — 20 m, resampled to 10 m ref_shape
    scl_arr = None
    if "scl" in item.assets:
        try:
            with rasterio.open(item.assets["scl"].href) as scl_src:
                src_bounds_scl = _bbox_in_src_crs(bbox, scl_src)
                win_scl = from_bounds(*src_bounds_scl, transform=scl_src.transform)
                scl_arr = scl_src.read(
                    1,
                    window=win_scl,
                    out_shape=ref_shape,
                    resampling=Resampling.nearest,
                    boundless=True,
                    fill_value=0,
                ).astype(np.uint8)
        except Exception as exc:
            logger.warning("Could not read SCL band: %s", exc)

    # Align all band shapes
    h = min(red.shape[0], nir.shape[0], blue.shape[0], green.shape[0], swir.shape[0])
    w = min(red.shape[1], nir.shape[1], blue.shape[1], green.shape[1], swir.shape[1])
    bands = {
        "blue":  blue[:h, :w],
        "green": green[:h, :w],
        "red":   red[:h, :w],
        "nir":   nir[:h, :w],
        "swir":  swir[:h, :w],
    }
    if scl_arr is not None:
        bands["scl"] = scl_arr[:h, :w]
    return bands


def _read_sar_raw(href, bbox_wgs84, target_shape):
    """Open a Sentinel-1 GRD asset, handling missing CRS by reprojecting bbox via rasterio.warp."""
    from rasterio.crs import CRS as RioCRS
    from rasterio.warp import transform as warp_transform
    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff")
    with env:
        with rasterio.open(href) as src:
            src_crs = src.crs or RioCRS.from_epsg(4326)
            src_epsg = src_crs.to_epsg() if src_crs else 4326
            wgs84 = RioCRS.from_epsg(4326)
            if src_epsg and src_epsg != 4326:
                # Reproject bbox corners from WGS84 → file's CRS
                xs, ys = warp_transform(
                    wgs84, src_crs,
                    [bbox_wgs84[0], bbox_wgs84[2]],
                    [bbox_wgs84[1], bbox_wgs84[3]],
                )
                minx, maxx = min(xs), max(xs)
                miny, maxy = min(ys), max(ys)
            else:
                minx, miny, maxx, maxy = bbox_wgs84
            win = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
            arr = src.read(
                1,
                window=win,
                out_shape=target_shape,
                resampling=Resampling.bilinear,
                boundless=True,
                fill_value=0,
            ).astype("float32")
    return arr


def _read_sar_band(item, bbox, ref_shape):
    """Read the VV polarization band from a Sentinel-1 GRD item."""
    if item is None:
        return None
    # Try VV first, then vh as fallback
    asset_key = None
    for k in ["vv", "VV", "vh", "VH"]:
        if k in item.assets:
            asset_key = k
            break
    if asset_key is None:
        logger.warning("SAR item has no VV/VH asset: %s", list(item.assets.keys()))
        return None
    try:
        vv = _read_sar_raw(item.assets[asset_key].href, bbox, ref_shape)
        # Sentinel-1 GRD values are linear power — convert to dB log scale
        vv_db = 10.0 * np.log10(np.clip(vv, 1e-6, None))
        # Typical VV dB range for built-up: -5 to +5 dB; bare soil: -15 to -5 dB
        # Normalize [-25 dB, +5 dB] → [0, 1]
        vv_norm = np.clip((vv_db + 25.0) / 30.0, 0, 1)
        logger.info("SAR VV loaded: mean=%.3f dB, shape=%s", float(vv_db.mean()), vv.shape)
        return vv_norm
    except Exception as exc:
        logger.warning("Failed to read SAR VV band: %s", exc)
        return None



def _safe_div(num, den):
    den = np.where(den == 0, 1e-6, den)
    return num / den


def _compute_indices(b):
    ndvi = _safe_div(b["nir"] - b["red"], b["nir"] + b["red"])
    ndbi = _safe_div(b["swir"] - b["nir"], b["swir"] + b["nir"])
    ndwi = _safe_div(b["green"] - b["nir"], b["green"] + b["nir"])
    # Bare Soil Index (Rikimaru 1997)
    bsi_num = (b["swir"] + b["red"]) - (b["nir"] + b["blue"])
    bsi_den = (b["swir"] + b["red"]) + (b["nir"] + b["blue"])
    bsi = _safe_div(bsi_num, bsi_den)
    return {"ndvi": ndvi.clip(-1, 1), "ndbi": ndbi.clip(-1, 1),
            "ndwi": ndwi.clip(-1, 1), "bsi": bsi.clip(-1, 1)}


def _classify(idx):
    """Multi-index land-cover classifier. Thresholds from satellite_config.json."""
    ndvi, ndbi, ndwi, bsi = idx["ndvi"], idx["ndbi"], idx["ndwi"], idx["bsi"]
    cls = np.full(ndvi.shape, OTHER, dtype=np.uint8)
    water_mask = ndwi > _lc_thresh["ndwi_water"]
    veg_mask   = (ndvi > _lc_thresh["ndvi_vegetation"]) & ~water_mask
    built_mask = (~water_mask) & (~veg_mask) & (ndbi > _lc_thresh["ndbi_built_min"]) & (ndvi < _lc_thresh["ndvi_built_max"])
    bare_mask  = (~water_mask) & (~veg_mask) & (~built_mask) & ((bsi > _lc_thresh["bsi_bare_min"]) | (ndvi < _lc_thresh["ndvi_bare_max"]))
    cls[water_mask] = WATER
    cls[veg_mask]   = VEGETATION
    cls[built_mask] = BUILT_UP
    cls[bare_mask]  = BARE_SOIL
    return cls


def _class_to_png(cls, out_path):
    h, w = cls.shape
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for code, color in CLASS_COLORS.items():
        m = cls == code
        img[m] = color
    Image.fromarray(img).save(out_path)


def _ndvi_to_png(ndvi, out_path):
    """NDVI colormap: dark navy=bare/dead → olive=sparse → vivid green=healthy vegetation."""
    arr = np.clip((ndvi + 1) / 2, 0, 1)  # 0–1 normalised
    # Dark navy → brown → yellow-green → vivid green
    r = np.where(arr < 0.5,
        (arr * 2 * 120).astype(float),          # 0–60: dark→olive
        (120 - (arr - 0.5) * 2 * 80).astype(float)  # 120⅂40: olive→green
    )
    g = np.where(arr < 0.5,
        (arr * 2 * 100).astype(float),          # 0→100
        (100 + (arr - 0.5) * 2 * 155).astype(float) # 100→255
    )
    b = np.where(arr < 0.5,
        (arr * 2 * 60).astype(float),           # 0‒60: slight blue tint in bare
        (60 - (arr - 0.5) * 2 * 50).astype(float)   # fade to 10
    )
    Image.fromarray(np.stack([
        np.clip(r, 0, 255).astype(np.uint8),
        np.clip(g, 0, 255).astype(np.uint8),
        np.clip(b, 0, 255).astype(np.uint8),
    ], axis=-1)).save(out_path)


def _rgb_to_png(bands, out_path):
    """True-colour RGB composite from Sentinel-2 B04/B03/B02 with 2–98 percentile stretch."""
    rgb = np.stack([bands["red"], bands["green"], bands["blue"]], axis=-1)
    lo, hi = np.percentile(rgb, [2, 98])
    rgb = np.clip((rgb - lo) / max(hi - lo, 1e-6), 0, 1)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(out_path)


def _transition_png(cls_t1, cls_t2, out_path):
    """High-contrast transition map for satellite governance oversight.
    
    Colour legend:
      Veg → Built-up  : bright red   (critical — illegal construction)
      Bare → Built-up : orange       (warning — construction progress)
      Veg → Bare      : yellow       (clearance — vegetation loss)
      Built → Veg     : teal         (positive — revegetation)
      Stable Veg      : dark green   (unchanged healthy vegetation)
      Stable Built    : dark grey    (unchanged built-up)
      Other stable    : near-black   (background)
    """
    h, w = cls_t1.shape
    img = np.full((h, w, 3), 18, dtype=np.uint8)  # near-black background

    # Stable classes (dimmed)
    stable_veg   = (cls_t1 == VEGETATION) & (cls_t2 == VEGETATION)
    stable_built = (cls_t1 == BUILT_UP)   & (cls_t2 == BUILT_UP)
    img[stable_veg]   = (20, 80, 25)     # dark green
    img[stable_built] = (55, 55, 65)     # dark grey

    # Change classes (vivid)
    veg_to_built  = (cls_t1 == VEGETATION) & (cls_t2 == BUILT_UP)
    veg_to_bare   = (cls_t1 == VEGETATION) & (cls_t2 == BARE_SOIL)
    bare_to_built = (cls_t1 == BARE_SOIL)  & (cls_t2 == BUILT_UP)
    built_to_veg  = (cls_t1 == BUILT_UP)   & (cls_t2 == VEGETATION)

    img[veg_to_built]  = (239, 35,  35)   # bright red
    img[bare_to_built] = (245, 130, 20)   # orange
    img[veg_to_bare]   = (230, 210, 30)   # yellow
    img[built_to_veg]  = (30,  210, 150)  # teal

    Image.fromarray(img).save(out_path)


def _class_fractions(cls):
    total = cls.size
    return {CLASS_NAMES[c]: round(float(np.sum(cls == c)) / total * 100, 2) for c in CLASS_NAMES}


def _load_dpr(project_id):
    f = DPR_DIR / f"{project_id}.json"
    if f.exists():
        with open(f) as fh:
            return json.load(fh)
    return None


def save_dpr_record(project_id, reported_pct, source, source_url=None, reported_date=None, raw_excerpt=None):
    record = {
        "project_id": project_id,
        "reported_progress_pct": float(reported_pct),
        "source": source,
        "source_url": source_url,
        "reported_date": reported_date or datetime.now(timezone.utc).date().isoformat(),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "raw_excerpt": raw_excerpt,
    }
    with open(DPR_DIR / f"{project_id}.json", "w") as f:
        json.dump(record, f, indent=2)
    return record


def analyze_project(project_id, current_date=None, run_ml=False):
    p = PROJECTS.get(project_id)
    if not p:
        return {"error": f"Unknown project {project_id}"}
    if current_date is None:
        current_date = datetime.now(timezone.utc).date().isoformat()

    bbox = p["bbox"]
    baseline = _search_scene(bbox, p["baseline_date"])
    if not baseline:
        return {"id": project_id, "error": "No cloud-free baseline scene found"}
    current = _search_scene(bbox, current_date)
    if not current:
        return {"id": project_id, "error": "No cloud-free current scene found"}

    bands_t1 = _read_scene_bands(baseline, bbox)
    bands_t2 = _read_scene_bands(current, bbox)
    h = min(bands_t1["red"].shape[0], bands_t2["red"].shape[0])
    w = min(bands_t1["red"].shape[1], bands_t2["red"].shape[1])
    for k in list(bands_t1.keys()):
        bands_t1[k] = bands_t1[k][:h, :w]
    for k in list(bands_t2.keys()):
        bands_t2[k] = bands_t2[k][:h, :w]

    # --- Phase 5: Sentinel-1 SAR Integration ---
    # SAR disabled per user request to speed up scanning
    sar_vv_t1, sar_vv_t2 = None, None

    if sar_vv_t1 is not None and sar_vv_t2 is not None:
        bands_t1["sar_vv"] = sar_vv_t1[:h, :w]
        bands_t2["sar_vv"] = sar_vv_t2[:h, :w]
    # -------------------------------------------


    # ── Phase 1a: Cloud masking ───────────────────────────────────────────────
    scl_t1 = bands_t1.pop("scl", None)
    scl_t2 = bands_t2.pop("scl", None)
    scl_stats_t1 = cloud_stats(scl_t1) if scl_t1 is not None else None
    scl_stats_t2 = cloud_stats(scl_t2) if scl_t2 is not None else None
    cloud_mask_t1 = scl_stats_t1["mask"] if scl_stats_t1 else None
    cloud_mask_t2 = scl_stats_t2["mask"] if scl_stats_t2 else None

    # ── Phase 1b: Seasonal normalization ─────────────────────────────────────
    season_info = season_mismatch_warning(baseline.datetime, current.datetime)

    # ── Phase 1c: Multi-temporal consistency stack ───────────────────────────
    temporal_result = None
    try:
        temporal_items = _search_temporal_stack(
            bbox,
            anchor_date_str=current_date,
            months_back=5,
            max_cloud=30,
        )
        if len(temporal_items) > 1:
            temporal_bands_list = []
            temporal_scl_list   = []
            for t_item in temporal_items:
                try:
                    t_bands = _read_scene_bands(t_item, bbox)
                    t_scl   = t_bands.pop("scl", None)
                    # Crop to common size
                    th = min(t_bands["red"].shape[0], h)
                    tw = min(t_bands["red"].shape[1], w)
                    t_bands = {k: v[:th, :tw] for k, v in t_bands.items()}
                    temporal_bands_list.append(t_bands)
                    temporal_scl_list.append(t_scl[:th, :tw] if t_scl is not None else None)
                except Exception as exc:
                    logger.warning("Failed to read temporal scene %s: %s", t_item.id, exc)
            if temporal_bands_list:
                temporal_result = multi_temporal_consistency(
                    baseline_bands=bands_t1,
                    temporal_scenes_bands=temporal_bands_list,
                    baseline_scl=scl_t1,
                    temporal_scls=temporal_scl_list,
                )
    except Exception as exc:
        logger.warning("Temporal stack fetch failed: %s", exc)

    # ── Compute indices with cloud-masked NDVI for seasonal correction ────────
    idx_t1 = _compute_indices(bands_t1)
    idx_t2 = _compute_indices(bands_t2)

    # Apply seasonal correction to NDVI before classification
    ndvi_t1_corrected, ndvi_t2_corrected = ndvi_seasonal_correction(
        idx_t1["ndvi"], idx_t2["ndvi"], season_info["season_matched"]
    )
    idx_t1["ndvi"] = ndvi_t1_corrected
    idx_t2["ndvi"] = ndvi_t2_corrected

    cls_t1 = _classify(idx_t1)
    cls_t2 = _classify(idx_t2)

    # Apply cloud mask to classification: masked pixels → class OTHER (no data)
    if cloud_mask_t1 is not None:
        cm1 = cloud_mask_t1[:cls_t1.shape[0], :cls_t1.shape[1]]
        cls_t1[~cm1] = OTHER
    if cloud_mask_t2 is not None:
        cm2 = cloud_mask_t2[:cls_t2.shape[0], :cls_t2.shape[1]]
        cls_t2[~cm2] = OTHER

    # Exclude OTHER (cloud/no-data) pixels from transition counts
    valid_mask = (cls_t1 != OTHER) & (cls_t2 != OTHER)

    veg_to_built  = float(np.sum((cls_t1 == VEGETATION) & (cls_t2 == BUILT_UP)  & valid_mask))
    veg_to_bare   = float(np.sum((cls_t1 == VEGETATION) & (cls_t2 == BARE_SOIL) & valid_mask))
    bare_to_built = float(np.sum((cls_t1 == BARE_SOIL)  & (cls_t2 == BUILT_UP)  & valid_mask))
    built_to_veg  = float(np.sum((cls_t1 == BUILT_UP)   & (cls_t2 == VEGETATION)& valid_mask))
    total_px      = float(valid_mask.sum())  # only valid (non-cloudy) pixels

    construction_activity_pct = round(
        (veg_to_built + veg_to_bare + bare_to_built) / max(total_px, 1) * 100.0, 2
    )
    weighted = (veg_to_built * 1.0 + bare_to_built * 1.0 + veg_to_bare * 0.5)
    raw_satellite_actual_pct = round(min(weighted / max(total_px, 1) * 100.0 * 2.0, 100.0), 2)

    # ── Apply temporal confidence scaling ────────────────────────────────────
    if temporal_result and temporal_result["usable_scene_count"] > 1:
        from satellite_quality import adjust_activity_for_temporal_confidence
        construction_activity_pct, _ = adjust_activity_for_temporal_confidence(
            construction_activity_pct,
            temporal_result["temporal_confidence"],
            temporal_result["usable_scene_count"],
        )
        satellite_actual_pct, reliability = adjust_activity_for_temporal_confidence(
            raw_satellite_actual_pct,
            temporal_result["temporal_confidence"],
            temporal_result["usable_scene_count"],
        )
    else:
        satellite_actual_pct = raw_satellite_actual_pct
        reliability = 0.5

    # Visual outputs
    _rgb_to_png(bands_t1, CACHE_DIR / f"{project_id}_rgb_baseline.png")
    _rgb_to_png(bands_t2, CACHE_DIR / f"{project_id}_rgb_current.png")
    _ndvi_to_png(idx_t1["ndvi"], CACHE_DIR / f"{project_id}_ndvi_baseline.png")
    _ndvi_to_png(idx_t2["ndvi"], CACHE_DIR / f"{project_id}_ndvi_current.png")
    _class_to_png(cls_t1, CACHE_DIR / f"{project_id}_landcover_baseline.png")
    _class_to_png(cls_t2, CACHE_DIR / f"{project_id}_landcover_current.png")
    _transition_png(cls_t1, cls_t2, CACHE_DIR / f"{project_id}_transitions.png")

    dpr = _load_dpr(project_id)
    if dpr:
        reported    = dpr["reported_progress_pct"]
        discrepancy = round(reported - satellite_actual_pct, 2)
        high_conf   = bool(
            temporal_result and
            temporal_result.get("temporal_confidence", 0) > _alert_thresh["high_confidence_temporal_min"]
        )
        ghost_thresh = _alert_thresh["ghost_alert_pct_high_confidence"] if high_conf else _alert_thresh["ghost_alert_pct"]
        lag_thresh   = _alert_thresh["lag_warning_pct_high_confidence"] if high_conf else _alert_thresh["lag_warning_pct"]
        unrep_thresh = _alert_thresh["unreported_progress_pct"]
        if discrepancy > ghost_thresh:
            status = "GHOST_ALERT"
        elif discrepancy > lag_thresh:
            status = "LAG_WARNING"
        elif discrepancy < unrep_thresh:
            status = "UNREPORTED_PROGRESS"
        else:
            status = "NORMAL"
        dpr_block = dpr
    else:
        reported    = None
        discrepancy = None
        status      = "AWAITING_DPR"
        dpr_block   = None

    ml_block = None
    if run_ml:
        try:
            from change_detector_ml import detect_change_ml
            ml_block = detect_change_ml(bands_t1, bands_t2, project_id, CACHE_DIR)
        except Exception as e:
            ml_block = {"error": f"ML pass failed: {e}"}

    cloud_baseline = baseline.properties.get("eo:cloud_cover", 0)
    cloud_current  = current.properties.get("eo:cloud_cover", 0)

    # ── Quality block (Phase 1 outputs) ──────────────────────────────────────
    quality_block = build_quality_block(
        baseline_scl_stats=scl_stats_t1,
        current_scl_stats=scl_stats_t2,
        temporal_result=temporal_result,
        season_info=season_info,
        raw_activity_pct=raw_satellite_actual_pct,
    )

    # Confidence: cloud cover + temporal reliability, penalised for season mismatch
    max_cloud_pen   = _CFG["confidence"]["max_cloud_penalty_pct"]
    season_penalty  = _CFG["seasonal_normalization"]["mismatch_confidence_penalty"]
    base_confidence = round(1.0 - min((cloud_baseline + cloud_current) / max_cloud_pen, 0.5), 3)
    final_confidence = round((base_confidence + reliability) / 2.0, 3)
    if not season_info["season_matched"]:
        final_confidence = round(final_confidence * season_penalty, 3)

    result = {
        "id":                     project_id,
        "project":                p["name"],
        "contractor":             p["contractor"],
        "location":               p["location"],
        "bbox":                   bbox,
        "baseline_date":          baseline.datetime.date().isoformat(),
        "current_date":           current.datetime.date().isoformat(),
        "baseline_scene_id":      baseline.id,
        "current_scene_id":       current.id,
        "baseline_cloud_cover":   cloud_baseline,
        "current_cloud_cover":    cloud_current,
        "landcover_baseline_pct": _class_fractions(cls_t1),
        "landcover_current_pct":  _class_fractions(cls_t2),
        "transitions_px": {
            "vegetation_to_built_up":  int(veg_to_built),
            "vegetation_to_bare_soil": int(veg_to_bare),
            "bare_soil_to_built_up":   int(bare_to_built),
            "built_up_to_vegetation":  int(built_to_veg),
            "total_aoi_px":            int(total_px),
        },
        "construction_activity_pct": construction_activity_pct,
        "satellite_actual_pct":      satellite_actual_pct,
        "reported_progress_pct":     reported,
        "discrepancy_pct":           discrepancy,
        "status":                    status,
        "dpr_record":                dpr_block,
        "ml_change_detection":       ml_block,
        "confidence":                final_confidence,
        "quality":                   quality_block,
        "evidence": (
            f"Sentinel-2 multi-index classification (cloud-masked, "
            f"{'season-corrected, ' if not season_info['season_matched'] else ''}"
            f"{temporal_result['usable_scene_count'] if temporal_result else 1} temporal scenes): "
            f"{int(veg_to_built + bare_to_built)} px built-up emergence, "
            f"{int(veg_to_bare)} px vegetation cleared, "
            f"{int(built_to_veg)} px reverted, "
            f"between {baseline.datetime.date().isoformat()} and {current.datetime.date().isoformat()}."
            + (f" ⚠ {season_info['warning']}" if season_info.get('warning') else "")
        ),
        "images": {
            "rgb_baseline":       f"/sat/{project_id}_rgb_baseline.png",
            "rgb_current":        f"/sat/{project_id}_rgb_current.png",
            "ndvi_baseline":      f"/sat/{project_id}_ndvi_baseline.png",
            "ndvi_current":       f"/sat/{project_id}_ndvi_current.png",
            "landcover_baseline": f"/sat/{project_id}_landcover_baseline.png",
            "landcover_current":  f"/sat/{project_id}_landcover_current.png",
            "transitions":        f"/sat/{project_id}_transitions.png",
        },
        "data_source": "Sentinel-2 L2A via element84 earth-search STAC",
        "method": "Multi-index land-cover classification (NDVI/NDBI/NDWI/BSI) + bi-temporal transition analysis [Phase 1: cloud-masked, multi-temporal, season-normalised]",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(CACHE_DIR / f"{project_id}.json", "w") as f:
        json.dump(result, f, indent=2)
    return result


def get_satellite_alerts():
    alerts = []
    for pid, p in PROJECTS.items():
        cache_file = CACHE_DIR / f"{pid}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                alerts.append(json.load(f))
        else:
            alerts.append({
                "id": pid,
                "project": p["name"],
                "contractor": p["contractor"],
                "location": p["location"],
                "status": "AWAITING_SCAN",
                "evidence": "Run `python backend/satellite.py` or POST /refresh-satellite to populate.",
            })
    return alerts


def refresh_all(run_ml=False):
    results = []
    for pid in PROJECTS:
        print(f"[satellite] analyzing {pid} ...")
        try:
            r = analyze_project(pid, run_ml=run_ml)
            if "error" in r:
                print(f"  ! {r['error']}")
            else:
                lc1 = r["landcover_baseline_pct"]
                lc2 = r["landcover_current_pct"]
                print(
                    f"  ok  status={r['status']:<18} "
                    f"sat_actual={r['satellite_actual_pct']:>5}% "
                    f"activity={r['construction_activity_pct']:>5}% "
                    f"reported={str(r['reported_progress_pct'])} "
                    f"\n      baseline LC: veg={lc1['vegetation']}% built={lc1['built_up']}% bare={lc1['bare_soil']}% water={lc1['water']}%"
                    f"\n      current  LC: veg={lc2['vegetation']}% built={lc2['built_up']}% bare={lc2['bare_soil']}% water={lc2['water']}%"
                )
            results.append(r)
        except Exception as e:
            print(f"  x  failed: {e}")
            results.append({"id": pid, "error": str(e)})
    return results


if __name__ == "__main__":
    import sys
    refresh_all(run_ml="--ml" in sys.argv)
