"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeftRight,
  ExternalLink,
  Layers,
  RefreshCw,
  Satellite,
  ZapOff,
  Clock,
  ChevronDown,
  ChevronUp,
  ScanLine,
} from "lucide-react";
import { API_BASE, assetUrl, SatelliteAlert } from "@/lib/api";

type Props = { projectId: string };

type RefreshResult = SatelliteAlert & {
  landcover_baseline_pct?: Record<string, number>;
  landcover_current_pct?: Record<string, number>;
  transitions_px?: Record<string, number>;
  construction_activity_pct?: number;
  baseline_scene_id?: string;
  current_scene_id?: string;
  baseline_cloud_cover?: number;
  current_cloud_cover?: number;
  confidence?: number;
  scanned_at?: string;
  evidence?: string;
  ml_change_detection?: {
    model: string;
    method: string;
    mean_change_score: number;
    max_change_score: number;
    high_change_cells_pct: number;
    rgb_baseline_image: string;
    rgb_current_image: string;
    change_heatmap: string;
  } | null;
};

// ─── Swipe Slider ────────────────────────────────────────────────────────────

function SwipeSlider({
  beforeSrc, afterSrc, beforeLabel, afterLabel,
}: {
  beforeSrc: string; afterSrc: string; beforeLabel: string; afterLabel: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState(50);
  const [widthPx, setWidthPx] = useState(0);
  const dragging = useRef(false);
  const [hintVisible, setHintVisible] = useState(true);

  const clamp = (v: number) => Math.min(100, Math.max(0, v));
  const getPos = useCallback((clientX: number) => {
    const el = containerRef.current;
    if (!el) return 50;
    const { left, width } = el.getBoundingClientRect();
    return clamp(((clientX - left) / width) * 100);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    setWidthPx(el.getBoundingClientRect().width);
    const ro = new ResizeObserver(entries => {
      setWidthPx(entries[0].contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => { if (dragging.current) setPos(getPos(e.clientX)); };
    const onUp = () => { dragging.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [getPos]);

  useEffect(() => {
    const onMove = (e: TouchEvent) => {
      if (!dragging.current) return;
      e.preventDefault();
      setPos(getPos(e.touches[0].clientX));
    };
    const onEnd = () => { dragging.current = false; };
    window.addEventListener("touchmove", onMove, { passive: false });
    window.addEventListener("touchend", onEnd);
    return () => { window.removeEventListener("touchmove", onMove); window.removeEventListener("touchend", onEnd); };
  }, [getPos]);

  useEffect(() => {
    const t = setTimeout(() => setHintVisible(false), 2500);
    return () => clearTimeout(t);
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-[500px] select-none overflow-hidden rounded-xl border border-[color:var(--border)] bg-black cursor-col-resize"
      onMouseDown={(e) => { dragging.current = true; setHintVisible(false); setPos(getPos(e.clientX)); }}
      onTouchStart={(e) => { dragging.current = true; setHintVisible(false); setPos(getPos(e.touches[0].clientX)); }}
      style={{ touchAction: "none" }}
    >
      <div 
        className="absolute inset-0 w-full h-full bg-cover bg-center" 
        style={{ backgroundImage: `url(${afterSrc})` }} 
      />
      <div className="absolute inset-y-0 left-0 overflow-hidden" style={{ width: `${pos}%` }}>
        <div 
          className="absolute inset-y-0 left-0 bg-cover bg-center" 
          style={{ 
            width: widthPx > 0 ? `${widthPx}px` : '100vw', 
            backgroundImage: `url(${beforeSrc})` 
          }} 
        />
      </div>
      <div className="absolute inset-y-0 w-0.5 bg-white shadow-[0_0_12px_3px_rgba(255,255,255,0.6)]" style={{ left: `${pos}%`, transform: "translateX(-50%)" }} />
      <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-9 h-9 rounded-full bg-white shadow-xl flex items-center justify-center z-10 border-2 border-[color:var(--primary)]" style={{ left: `${pos}%` }}>
        <ArrowLeftRight className="w-4 h-4 text-[color:var(--primary)]" />
      </div>
      <div className="absolute top-2 left-3 pointer-events-none">
        <span className="text-[10px] font-bold uppercase tracking-widest bg-black/70 text-green-400 px-2 py-0.5 rounded-full backdrop-blur-sm">◀ {beforeLabel}</span>
      </div>
      <div className="absolute top-2 right-3 pointer-events-none">
        <span className="text-[10px] font-bold uppercase tracking-widest bg-black/70 text-red-400 px-2 py-0.5 rounded-full backdrop-blur-sm">{afterLabel} ▶</span>
      </div>
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 pointer-events-none">
        <span className="text-[10px] font-mono bg-black/60 text-white px-2 py-0.5 rounded-full backdrop-blur-sm">
          {Math.round(pos)}% baseline · {Math.round(100 - pos)}% current
        </span>
      </div>
      {hintVisible && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="flex items-center gap-2 bg-black/70 backdrop-blur-sm text-white text-xs px-4 py-2 rounded-full animate-pulse">
            <ArrowLeftRight className="w-3.5 h-3.5" /> Drag to compare
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Freshness Badge ──────────────────────────────────────────────────────────

function FreshnessBadge({ scannedAt }: { scannedAt?: string }) {
  if (!scannedAt) return null;
  const diffH = (Date.now() - new Date(scannedAt).getTime()) / 3600000;
  const label = diffH < 1 ? `${Math.round(diffH * 60)}m ago` : diffH < 24 ? `${Math.round(diffH)}h ago` : `${Math.round(diffH / 24)}d ago`;
  const color = diffH < 24 ? "text-[color:var(--success)] bg-[color:var(--success-soft)]" : diffH < 168 ? "text-[color:var(--warning)] bg-amber-500/10" : "text-[color:var(--danger)] bg-red-500/10";
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${color}`}>
      <Clock className="w-2.5 h-2.5" />{label}
    </span>
  );
}

// ─── Status Chip ──────────────────────────────────────────────────────────────

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string; pulse: boolean }> = {
    GHOST_ALERT:         { label: "Ghost Alert",          cls: "bg-red-500/15 text-red-400 border border-red-500/30",      pulse: true },
    LAG_WARNING:         { label: "Lag Warning",          cls: "bg-amber-500/15 text-amber-400 border border-amber-500/30", pulse: false },
    UNREPORTED_PROGRESS: { label: "Unreported Progress",  cls: "bg-blue-500/15 text-blue-400 border border-blue-500/30",   pulse: false },
    NORMAL:              { label: "On Track",             cls: "bg-green-500/15 text-green-400 border border-green-500/30", pulse: false },
    AWAITING_DPR:        { label: "Awaiting DPR",         cls: "bg-[color:var(--surface-2)] text-[color:var(--muted)] border border-[color:var(--border)]", pulse: false },
    AWAITING_SCAN:       { label: "Awaiting Scan",        cls: "bg-[color:var(--surface-2)] text-[color:var(--muted)] border border-[color:var(--border)]", pulse: false },
  };
  const s = map[status] ?? { label: status, cls: "bg-[color:var(--surface-2)] text-[color:var(--muted)]", pulse: false };
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1 rounded-full ${s.cls}`}>
      {s.pulse ? (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
        </span>
      ) : (
        <span className="w-2 h-2 rounded-full bg-current opacity-60" />
      )}
      {s.label}
    </span>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Metric({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "danger" | "warning" | "default" }) {
  const color = tone === "danger" ? "text-[color:var(--danger)]" : tone === "warning" ? "text-[color:var(--warning)]" : "text-[color:var(--foreground)]";
  return (
    <div className="surface-elev p-3">
      <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">{label}</p>
      <p className={`text-xl font-semibold mt-1 metric-value ${color}`}>{value}</p>
      {sub && <p className="text-[10px] text-[color:var(--muted-2)] mt-1">{sub}</p>}
    </div>
  );
}

function ImagePanel({ title, sub, src, highlight }: { title: string; sub?: string; src: string | null; highlight?: boolean }) {
  return (
    <div className={`rounded-lg overflow-hidden border ${highlight ? "border-[color:var(--primary)]" : "border-[color:var(--border)]"} bg-black/40`}>
      <div className="px-3 py-2 flex items-center justify-between border-b border-[color:var(--border)]">
        <p className="text-[11px] font-semibold">{title}</p>
        {sub && <p className="text-[10px] text-[color:var(--muted-2)] font-mono truncate ml-3">{sub}</p>}
      </div>
      {src ? (
        <div 
          className="w-full h-[500px] bg-cover bg-center" 
          style={{ backgroundImage: `url(${src})` }} 
        />
      ) : (
        <div className="h-[500px] flex items-center justify-center text-[color:var(--muted-2)] text-xs">no image</div>
      )}
    </div>
  );
}

function Delta({ a, b }: { a: number; b: number }) {
  const d = +(a - b).toFixed(2);
  const tone = d > 0 ? "text-[color:var(--success)]" : d < 0 ? "text-[color:var(--danger)]" : "text-[color:var(--muted)]";
  return <p className={`text-[10px] mt-0.5 ${tone}`}>Δ {d > 0 ? "+" : ""}{d}</p>;
}

function Transition({ label, v, tone }: { label: string; v: number; tone: "danger" | "warning" | "success" }) {
  const color = tone === "danger" ? "text-[color:var(--danger)]" : tone === "warning" ? "text-[color:var(--warning)]" : "text-[color:var(--success)]";
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-[color:var(--muted)]">{label}</p>
      <p className={`text-base font-semibold mt-1 ${color}`}>{v.toLocaleString()} px</p>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function SatelliteView({ projectId }: Props) {
  const [data, setData] = useState<RefreshResult | null>(null);
  const [layer, setLayer] = useState<"photo" | "ndvi" | "landcover" | "transitions" | "ml">("photo");
  const [viewMode, setViewMode] = useState<"slider" | "sidebyside">("slider");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [techOpen, setTechOpen] = useState(false);

  const loadCached = async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/satellite-alerts`);
      const j = await r.json();
      const match = j.alerts.find((a: SatelliteAlert) => a.id === projectId);
      setData(match ?? null);
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  };

  const refresh = async (withMl: boolean) => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/refresh-satellite/${projectId}?ml=${withMl}`, { method: "POST" });
      if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
      const result = await r.json();
      setData(result);
      if (result.status === "GHOST_ALERT") setLayer("transitions");
      else if (result.images?.rgb_baseline) setLayer("photo");
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadCached(); }, [projectId]);

  useEffect(() => {
    if (!data) return;
    if (data.status === "GHOST_ALERT" && data.images?.transitions) setLayer("transitions");
    else if (data.images?.rgb_baseline) setLayer("photo");
  }, [data?.id]);

  // ── Loading state ──
  if (loading && !data) {
    return (
      <div className="surface p-6 space-y-3">
        <div className="flex items-center gap-2 text-[color:var(--muted)] text-sm">
          <ScanLine className="w-4 h-4 animate-pulse" /> Loading satellite data…
        </div>
        <div className="skeleton h-[500px] w-full rounded-xl" />
        <div className="grid grid-cols-3 gap-3">{[...Array(3)].map((_, i) => <div key={i} className="skeleton h-20 rounded-lg" />)}</div>
      </div>
    );
  }

  // ── Error / no data ──
  if (!data || error) {
    return (
      <div className="surface p-8 text-center space-y-3">
        <ZapOff className="w-8 h-8 text-[color:var(--muted)] mx-auto" />
        <p className="text-sm text-[color:var(--muted)]">{error ?? "No satellite scan found for this project."}</p>
        <button onClick={() => refresh(false)} className="btn btn-primary">
          <Satellite className="w-3.5 h-3.5" /> Run First Scan
        </button>
      </div>
    );
  }

  const lcCurrent = data.landcover_current_pct;
  const lcBase = data.landcover_baseline_pct;
  const transitions = data.transitions_px;
  const ml = data.ml_change_detection;

  // ── Image sources ──
  const hasRealPhotos = !!(data.images?.rgb_baseline && data.images?.rgb_current);
  const sliderBefore = assetUrl(hasRealPhotos ? data.images!.rgb_baseline : (data.images?.ndvi_baseline ?? data.images?.landcover_baseline));
  const sliderAfter  = assetUrl(hasRealPhotos ? data.images!.rgb_current  : (data.images?.transitions    ?? data.images?.landcover_current));
  const sliderBeforeLabel = hasRealPhotos ? `Baseline · ${data.baseline_date ?? ""}` : "🟢 Vegetation (baseline)";
  const sliderAfterLabel  = hasRealPhotos ? `Current · ${data.current_date ?? ""}`   : "🔴 Construction change";

  const analysisOverlaySrc = assetUrl(
    layer === "photo"       ? null :
    layer === "ndvi"        ? data.images?.ndvi_current :
    layer === "landcover"   ? data.images?.landcover_current :
    layer === "transitions" ? data.images?.transitions :
    layer === "ml" && ml    ? ml.change_heatmap : null
  );
  const analysisBaselineSrc = assetUrl(
    layer === "ndvi"      ? data.images?.ndvi_baseline :
    layer === "landcover" ? data.images?.landcover_baseline : null
  );

  const layerTabs = [
    { key: "photo" as const,       label: "🛰 Real Photo",  hint: "Actual Sentinel-2 RGB imagery" },
    { key: "ndvi" as const,        label: "NDVI",           hint: "Vegetation index" },
    { key: "landcover" as const,   label: "Land Cover",     hint: "Classified land types" },
    { key: "transitions" as const, label: "Transitions",    hint: "Change map" },
    ...(ml ? [{ key: "ml" as const, label: "ML Change",    hint: "ResNet18 heatmap" }] : []),
  ];

  const statusDesc: Record<string, string> = {
    GHOST_ALERT:         "Contractor may be inflating progress claims",
    LAG_WARNING:         "Reported progress is ahead of satellite evidence",
    UNREPORTED_PROGRESS: "Actual work exceeds what was reported",
    NORMAL:              "Satellite confirms reported progress",
    AWAITING_DPR:        "No DPR uploaded — cannot compare",
    AWAITING_SCAN:       "Satellite scan not yet run",
  };

  return (
    <div className="space-y-4 fade-in">
      <div className="surface p-5">

        {/* ── Header ── */}
        <div className="flex items-start justify-between mb-4 gap-4 flex-wrap">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-[color:var(--primary-soft)] flex items-center justify-center shrink-0">
              <Satellite className="w-4 h-4 text-[color:var(--primary)]" />
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-widest text-[color:var(--muted)]">Sentinel-2 Analysis</p>
              <div className="flex items-center gap-2 flex-wrap mt-0.5">
                <h3 className="text-base font-semibold">Satellite Change Detection</h3>
                <FreshnessBadge scannedAt={data.scanned_at} />
              </div>
            </div>
          </div>
          <div className="flex gap-2 shrink-0">
            <button onClick={() => refresh(false)} disabled={loading} className="btn btn-secondary">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
            </button>
            <button onClick={() => refresh(true)} disabled={loading} className="btn btn-primary">
              <Layers className="w-3.5 h-3.5" /> + ML
            </button>
          </div>
        </div>

        {/* ══ VERDICT CARD — supervisor sees this first ══ */}
        <div className={`rounded-xl p-4 mb-5 border-2 ${
          data.status === "GHOST_ALERT"         ? "bg-red-500/8 border-red-500/40" :
          data.status === "LAG_WARNING"         ? "bg-amber-500/8 border-amber-500/35" :
          data.status === "UNREPORTED_PROGRESS" ? "bg-blue-500/8 border-blue-500/35" :
          "bg-green-500/8 border-green-500/30"
        }`}>
          {/* Status + description */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <StatusChip status={data.status} />
            <span className="text-[12px] text-[color:var(--muted)]">{statusDesc[data.status] ?? data.status}</span>
          </div>

          {/* The 3 numbers a supervisor cares about */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-black/20 p-3 text-center">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-1">Contractor Claims</p>
              <p className="text-2xl font-bold metric-value">{data.reported_progress_pct != null ? `${data.reported_progress_pct}%` : "—"}</p>
              <p className="text-[10px] text-[color:var(--muted)] mt-0.5">from DPR report</p>
            </div>
            <div className="rounded-lg bg-black/20 p-3 text-center">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-1">Satellite Sees</p>
              <p className="text-2xl font-bold metric-value">{data.satellite_actual_pct != null ? `${data.satellite_actual_pct}%` : "—"}</p>
              <p className="text-[10px] text-[color:var(--muted)] mt-0.5">actual on ground</p>
            </div>
            <div className={`rounded-lg p-3 text-center border ${
              data.status === "GHOST_ALERT" ? "bg-red-500/15 border-red-500/30" :
              data.status === "LAG_WARNING" ? "bg-amber-500/15 border-amber-500/30" :
              "bg-green-500/10 border-green-500/20"
            }`}>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-1">Gap (Fraud Risk)</p>
              <p className={`text-2xl font-bold metric-value ${
                data.status === "GHOST_ALERT" ? "text-red-400" :
                data.status === "LAG_WARNING" ? "text-amber-400" : "text-green-400"
              }`}>
                {data.discrepancy_pct != null ? `${data.discrepancy_pct > 0 ? "+" : ""}${data.discrepancy_pct}%` : "—"}
              </p>
              <p className="text-[10px] text-[color:var(--muted)] mt-0.5">
                {data.confidence != null ? `${Math.round(data.confidence * 100)}% confidence` : ""}
              </p>
            </div>
          </div>

          {/* Phase 1 quality badges */}
          {data.quality && (
            <div className="mt-3 pt-3 border-t border-white/5 flex flex-wrap gap-2">
              {/* Cloud masking badge */}
              {data.quality.cloud_mask && !data.quality.cloud_mask.note && (
                <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                  (data.quality.cloud_mask.current_pct_masked ?? 0) < 10
                    ? "bg-green-500/15 text-green-400"
                    : (data.quality.cloud_mask.current_pct_masked ?? 0) < 30
                    ? "bg-amber-500/15 text-amber-400"
                    : "bg-red-500/15 text-red-400"
                }`}>
                  ☁ {data.quality.cloud_mask.current_pct_masked ?? 0}% cloud masked
                </span>
              )}
              {/* Temporal consistency badge */}
              {data.quality.temporal_consistency?.confidence != null ? (
                <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                  data.quality.temporal_consistency.confidence >= 0.6
                    ? "bg-green-500/15 text-green-400"
                    : "bg-amber-500/15 text-amber-400"
                }`}>
                  🕒 {data.quality.temporal_consistency.scenes_usable} scenes · {Math.round((data.quality.temporal_consistency.confidence ?? 0) * 100)}% consistent
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[color:var(--surface-2)] text-[color:var(--muted)]">
                  🕒 Single-scene (no temporal check)
                </span>
              )}
              {/* Season badge */}
              {data.quality.seasonal_normalization && (
                data.quality.seasonal_normalization.season_matched
                  ? <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-green-500/15 text-green-400">🌤 Same season</span>
                  : <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400" title={data.quality.seasonal_normalization.warning ?? ""}>⚠ Season corrected</span>
              )}
            </div>
          )}

          {/* One-line evidence */}
          {data.evidence && (
            <p className="mt-3 text-[11px] text-[color:var(--muted)] leading-relaxed border-t border-white/5 pt-3">
              📡 {data.evidence}
            </p>
          )}
        </div>

        {/* ══ VISUAL PROOF — swipe before/after ══ */}
        <div className="mb-2">
          <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
            <p className="text-[11px] font-bold uppercase tracking-widest text-[color:var(--muted)]">Visual Proof — drag to compare</p>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex flex-wrap gap-1">
                {layerTabs.map((t) => (
                  <button key={t.key} onClick={() => setLayer(t.key)} title={t.hint}
                    className={`tab text-[11px] py-1 px-2 ${layer === t.key ? "tab-active" : ""}`}>
                    {t.label}
                    {t.key === "transitions" && data.status === "GHOST_ALERT" && (
                      <span className="ml-1 text-[9px] font-bold text-red-400">⚡</span>
                    )}
                  </button>
                ))}
              </div>
              <div className="flex gap-1 p-0.5 rounded-lg bg-[color:var(--surface-2)] border border-[color:var(--border)]">
                <button onClick={() => setViewMode("slider")}
                  className={`px-3 py-1 text-[11px] font-semibold rounded-md transition-all ${viewMode === "slider" ? "bg-[color:var(--primary)] text-white shadow-sm" : "text-[color:var(--muted)] hover:text-[color:var(--foreground)]"}`}>
                  <span className="flex items-center gap-1.5"><ArrowLeftRight className="w-3 h-3" /> Swipe</span>
                </button>
                <button onClick={() => setViewMode("sidebyside")}
                  className={`px-3 py-1 text-[11px] font-semibold rounded-md transition-all ${viewMode === "sidebyside" ? "bg-[color:var(--primary)] text-white shadow-sm" : "text-[color:var(--muted)] hover:text-[color:var(--foreground)]"}`}>
                  Side-by-Side
                </button>
              </div>
            </div>
          </div>

          {!hasRealPhotos && viewMode === "slider" && (
            <div className="mb-2 flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-400">
              <span className="font-bold">⚠ No real photos yet.</span>
              <span>Showing NDVI vs Change Map. Click <strong>Refresh</strong> for actual satellite imagery.</span>
            </div>
          )}

          {viewMode === "slider" ? (
            sliderBefore && sliderAfter ? (
              <>
                <SwipeSlider beforeSrc={sliderBefore} afterSrc={sliderAfter} beforeLabel={sliderBeforeLabel} afterLabel={sliderAfterLabel} />
                {layer !== "photo" && (analysisBaselineSrc || analysisOverlaySrc) && (
                  <div className="mt-3 rounded-xl border border-[color:var(--border)] overflow-hidden">
                    <div className="px-3 py-2 bg-[color:var(--surface-2)] flex items-center gap-2 border-b border-[color:var(--border)]">
                      <span className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">Analysis —</span>
                      <span className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--primary)]">
                        {layerTabs.find(t => t.key === layer)?.hint}
                      </span>
                      {layer === "ml" && ml && (
                        <span className="ml-auto text-[10px] text-[color:var(--muted)]">mean Δ {ml.mean_change_score} · {ml.high_change_cells_pct}% high-change</span>
                      )}
                    </div>
                    <div className={`grid gap-0 ${analysisBaselineSrc ? "grid-cols-2" : "grid-cols-1"}`}>
                      {analysisBaselineSrc && (
                        <div className="relative">
                          <img src={analysisBaselineSrc} alt="baseline analysis" className="w-full h-[300px] object-cover" />
                          <div className="absolute bottom-1 left-2 text-[9px] font-bold uppercase tracking-widest bg-black/60 text-green-400 px-2 py-0.5 rounded-full">Baseline</div>
                        </div>
                      )}
                      {analysisOverlaySrc && (
                        <div className="relative">
                          <img src={analysisOverlaySrc} alt="current analysis" className="w-full h-[300px] object-cover" />
                          <div className="absolute bottom-1 left-2 text-[9px] font-bold uppercase tracking-widest bg-black/60 text-red-400 px-2 py-0.5 rounded-full">
                            {layer === "transitions" ? "Δ Change Map" : "Current"}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="h-[500px] rounded-xl border border-[color:var(--border)] bg-black/30 flex items-center justify-center text-[color:var(--muted)] text-sm">
                No imagery — click Refresh to run a satellite scan
              </div>
            )
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <ImagePanel title={`Baseline · ${data.baseline_date ?? ""}`} sub={data.baseline_scene_id} src={analysisBaselineSrc ?? sliderBefore} />
              <ImagePanel
                title={layer === "transitions" ? `Δ Transitions · ${data.current_date ?? ""}` : `Current · ${data.current_date ?? ""}`}
                sub={layer === "ml" && ml ? `mean Δ ${ml.mean_change_score}` : data.current_scene_id}
                src={analysisOverlaySrc ?? sliderAfter}
                highlight={layer === "transitions" || layer === "ml"}
              />
            </div>
          )}
        </div>



        {/* ══ TECHNICAL DETAILS — collapsible for analysts ══ */}
        <div className="mt-4 rounded-lg border border-[color:var(--border)] overflow-hidden">
          <button
            onClick={() => setTechOpen((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-2.5 bg-[color:var(--surface-2)] text-[11px] font-semibold uppercase tracking-widest text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors"
          >
            <span className="flex items-center gap-2"><ScanLine className="w-3.5 h-3.5" /> Technical Details (for analysts)</span>
            {techOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {techOpen && (
            <div className="p-4 space-y-4 bg-black/10">
              {/* Land cover */}
              {lcBase && lcCurrent && (
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-2">Land-cover share (% of AOI pixels)</p>
                  <div className="grid grid-cols-4 gap-3 text-xs">
                    {(["vegetation", "built_up", "bare_soil", "water"] as const).map((c) => (
                      <div key={c}>
                        <p className="text-[color:var(--muted)] text-[10px] uppercase tracking-wide">{c.replace("_", " ")}</p>
                        <p className="metric-value font-semibold mt-1">{lcBase[c]}% <span className="text-[color:var(--muted)]">→</span> {lcCurrent[c]}%</p>
                        <Delta a={lcCurrent[c]} b={lcBase[c]} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Pixel transitions */}
              {transitions && (
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-2">Pixel Transitions</p>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs metric-value">
                    <Transition label="Veg → Built-up"    v={transitions.vegetation_to_built_up}  tone="danger" />
                    <Transition label="Veg → Bare"         v={transitions.vegetation_to_bare_soil} tone="warning" />
                    <Transition label="Bare → Built-up"   v={transitions.bare_soil_to_built_up}   tone="warning" />
                    <Transition label="Built → Veg"        v={transitions.built_up_to_vegetation}  tone="success" />
                  </div>
                  <p className="text-[10px] text-[color:var(--muted-2)] mt-2">Total AOI pixels: {transitions.total_aoi_px.toLocaleString()}</p>
                </div>
              )}
              {/* ML (Moved to main view) */}
              {/* Scene metadata */}
              <div className="pt-2 border-t border-[color:var(--border)] text-[10px] text-[color:var(--muted-2)] flex flex-wrap gap-x-4 gap-y-1 font-mono">
                <span>Source: {data.data_source}</span>
                <span>Baseline: {data.baseline_scene_id ?? "—"} (cloud {Math.round(data.baseline_cloud_cover ?? 0)}%)</span>
                <span>Current: {data.current_scene_id ?? "—"} (cloud {Math.round(data.current_cloud_cover ?? 0)}%)</span>
                {data.dpr_record?.source_url && (
                  <a href={data.dpr_record.source_url} target="_blank" rel="noreferrer"
                    className="text-[color:var(--primary)] hover:underline inline-flex items-center gap-1">
                    DPR source <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
