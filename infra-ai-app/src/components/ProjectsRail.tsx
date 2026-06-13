"use client";

import React, { useEffect, useState } from "react";
import { Building2, RefreshCw, Gavel, ShieldCheck } from "lucide-react";
import { fetchAlerts, SatelliteAlert } from "@/lib/api";

type Props = {
  selected: string | null;
  onSelect: (id: string) => void;
  onOpenTenders?: () => void;
};

const STATUS_CHIP: Record<string, string> = {
  GHOST_ALERT: "chip-danger",
  LAG_WARNING: "chip-warning",
  UNREPORTED_PROGRESS: "chip-info",
  NORMAL: "chip-success",
  AWAITING_DPR: "chip-muted",
  AWAITING_SCAN: "chip-muted",
};

const STATUS_LABEL: Record<string, string> = {
  GHOST_ALERT: "Ghost alert",
  LAG_WARNING: "Lagging",
  UNREPORTED_PROGRESS: "Unreported",
  NORMAL: "On track",
  AWAITING_DPR: "Needs DPR",
  AWAITING_SCAN: "Needs scan",
};

export function ProjectsRail({ selected, onSelect, onOpenTenders }: Props) {
  const [alerts, setAlerts] = useState<SatelliteAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAlerts();
      setAlerts(data.alerts);
      setLastRefresh(new Date());
      if (!selected && data.alerts.length > 0) onSelect(data.alerts[0].id);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <aside className="w-72 shrink-0 border-r border-[color:var(--border)] flex flex-col bg-[color:var(--surface)]">
      {/* ── ATLAS Brand Header ── */}
      <div className="px-5 py-5 border-b border-[color:var(--border)] flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[color:var(--primary)] to-[color:var(--primary-hover)] flex items-center justify-center shadow-lg shadow-[color:var(--primary)]/20">
          <ShieldCheck className="w-4.5 h-4.5 text-black" style={{ width: "18px", height: "18px" }} />
        </div>
        <div>
          <p className="font-black text-sm leading-none tracking-widest text-[color:var(--foreground)]">ATLAS ASSURANCE</p>
          <p className="text-[10px] text-[color:var(--primary)] mt-0.5 font-medium tracking-wide">Autonomous Assurance for Physical Infrastructure</p>
        </div>
      </div>

      {/* ── Project list header ── */}
      <div className="px-5 py-4 flex items-center justify-between">
        <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">
          Registered Projects
        </p>
        <button
          onClick={load}
          className="btn-ghost p-1.5 rounded-md hover:bg-[color:var(--surface-2)]"
          aria-label="Refresh"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* ── Project cards ── */}
      <div className="flex-1 overflow-y-auto scroll-thin px-3 pb-4 space-y-2">
        {loading && alerts.length === 0 && (
          <>
            <div className="skeleton h-20 rounded-lg" />
            <div className="skeleton h-20 rounded-lg" />
            <div className="skeleton h-20 rounded-lg" />
          </>
        )}
        {error && (
          <div className="px-3 py-2 text-xs text-[color:var(--danger)]">
            Backend offline.<br />
            <span className="text-[color:var(--muted)]">{error}</span>
          </div>
        )}
        {alerts.map((a) => {
          const isActive = a.id === selected;
          const chip = STATUS_CHIP[a.status] || "chip-muted";
          const label = STATUS_LABEL[a.status] || a.status;
          return (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              className={`w-full text-left px-3 py-3 rounded-lg border transition-all ${
                isActive
                  ? "bg-[color:var(--primary)]/5 border-[color:var(--primary)]/30"
                  : "border-transparent hover:bg-[color:var(--surface-2)] hover:border-[color:var(--border)]"
              }`}
            >
              <div className="flex items-start gap-2 mb-1.5">
                <div className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${
                  isActive
                    ? "bg-[color:var(--primary)]/10 border border-[color:var(--primary)]/20"
                    : "bg-[color:var(--surface-2)] border border-[color:var(--border)]"
                }`}>
                  <Building2 className={`w-3.5 h-3.5 ${isActive ? "text-[color:var(--primary)]" : "text-[color:var(--muted)]"}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-semibold truncate ${isActive ? "text-[color:var(--foreground)]" : "text-[color:var(--foreground)]"}`}>{a.project}</p>
                  <p className="text-[10px] text-[color:var(--muted)] truncate">{a.contractor}</p>
                </div>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className={`chip ${chip}`}>{label}</span>
                {typeof a.satellite_actual_pct === "number" && (
                  <span className="text-[10px] text-[color:var(--muted)] metric-value">
                    sat <span className="text-[color:var(--foreground)] font-semibold">{a.satellite_actual_pct}%</span>
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* ── Procurement Intelligence ── */}
      <div className="px-3 pb-3 border-t border-[color:var(--border)] pt-3">
        <button
          onClick={onOpenTenders}
          className="w-full text-left px-3 py-3 rounded-lg border border-[color:var(--border)] hover:border-[color:var(--border-strong)] hover:bg-[color:var(--surface-2)] transition-all group"
        >
          <div className="flex items-center gap-2">
            <Gavel className="w-3.5 h-3.5 text-[color:var(--muted)] group-hover:text-[color:var(--foreground)] transition-colors" />
            <div className="flex-1 min-w-0">
              <p className="text-[11px] font-semibold text-[color:var(--muted)] group-hover:text-[color:var(--foreground)] transition-colors">Procurement Intelligence</p>
              <p className="text-[9px] text-[color:var(--muted-2)] uppercase tracking-wider mt-0.5">Tender Registry</p>
            </div>
          </div>
        </button>
      </div>

      {/* ── Last refresh footer ── */}
      <div className="px-5 py-3 border-t border-[color:var(--border)] text-[10px] text-[color:var(--muted-2)]">
        {lastRefresh ? `Refreshed ${lastRefresh.toLocaleTimeString()}` : "—"}
      </div>
    </aside>
  );
}
