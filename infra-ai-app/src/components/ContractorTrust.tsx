"use client";

import { useEffect, useRef, useState } from "react";
import {
  ShieldAlert,
  TrendingDown,
  AlertTriangle,
  Ban,
  CheckCircle2,
  Eye,
  Calendar,
  FileText,
  ChevronLeft,
  ChevronRight,
  Loader2,
  IndianRupee,
  RefreshCw,
} from "lucide-react";
import {
  fetchNcri,
  assetUrl,
  API_BASE,
  NcriData,
  NcriLedgerEntry,
  NcriTimelineEntry,
  SeverityLevel,
} from "@/lib/api";
import { useGovernanceEvents } from "@/lib/governanceEvents";

// ── Recommended Action Meta ───────────────────────────────────────────────────

const ACTION_META: Record<string, { icon: string; label: string; color: string; bg: string }> = {
  ISSUE_SHOW_CAUSE_NOTICE:   { icon: "⚠",  label: "Issue Show-Cause Notice",  color: "#d97706", bg: "rgba(254,243,199,0.15)" },
  FREEZE_DISBURSEMENT:       { icon: "⛔", label: "Freeze Disbursement",       color: "#dc2626", bg: "rgba(254,226,226,0.15)" },
  ESCALATE_PHYSICAL_AUDIT:   { icon: "🔎", label: "Escalate Physical Audit",   color: "#7c3aed", bg: "rgba(237,233,254,0.15)" },
  INITIATE_BLACKLIST_REVIEW: { icon: "🚫", label: "Initiate Blacklist Review", color: "#fca5a5", bg: "rgba(127,29,29,0.35)"  },
};

function ActionChip({ action, projectId }: { action: string, projectId: string }) {
  const meta = ACTION_META[action];
  const [status, setStatus] = useState<"idle" | "loading" | "sent">("idle");

  if (!meta) return null;

  const handleFire = async () => {
    setStatus("loading");
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/issue-advisory`, {
        method: "POST"
      });
      if (res.ok) {
        setStatus("sent");
      } else {
        setStatus("idle");
        alert("Failed to send advisory");
      }
    } catch (e) {
      setStatus("idle");
      alert("Error sending advisory");
    }
  };

  if (status === "sent") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold mt-1 text-green-500 bg-green-500/10 border border-green-500/20">
        <span>✅</span>
        Alert Sent to Mobile
      </span>
    );
  }

  return (
    <button
      onClick={handleFire}
      disabled={status === "loading"}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold mt-1 transition-all hover:brightness-125 disabled:opacity-50"
      style={{ color: meta.color, background: meta.bg, border: `1px solid ${meta.color}30` }}
    >
      {status === "loading" ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : (
        <span>{meta.icon}</span>
      )}
      {meta.label}
    </button>
  );
}

// ── Severity helpers ──────────────────────────────────────────────────────────

const SEVERITY_CONFIG: Record<
  SeverityLevel,
  { chip: string; dot: string; label: string; ring: string }
> = {
  LOW: {
    chip: "chip-success",
    dot: "bg-[#4ade80]",
    label: "LOW",
    ring: "rgba(34,197,94,0.35)",
  },
  MODERATE: {
    chip: "chip-warning",
    dot: "bg-[#fbbf24]",
    label: "MODERATE",
    ring: "rgba(245,158,11,0.35)",
  },
  CRITICAL: {
    chip: "chip-danger",
    dot: "bg-[#f87171]",
    label: "CRITICAL",
    ring: "rgba(239,68,68,0.35)",
  },
  "FRAUD RISK": {
    chip: "chip-danger",
    dot: "bg-[#ef4444]",
    label: "FRAUD RISK",
    ring: "rgba(239,68,68,0.6)",
  },
};

function SeverityChip({ level }: { level: SeverityLevel }) {
  const cfg = SEVERITY_CONFIG[level] ?? SEVERITY_CONFIG["LOW"];
  return (
    <span className={`chip ${cfg.chip} gap-1.5`}>
      <span className={`dot ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ── NCRI Gauge (SVG arc) ──────────────────────────────────────────────────────

function NcriGauge({ score }: { score: number }) {
  const radius = 72;
  const stroke = 9;
  const cx = 90;
  const cy = 90;
  const startAngle = -210;
  const sweepTotal = 240;

  function polarToCartesian(angle: number) {
    const rad = ((angle - 90) * Math.PI) / 180;
    return {
      x: cx + radius * Math.cos(rad),
      y: cy + radius * Math.sin(rad),
    };
  }

  function arcPath(from: number, to: number) {
    const s = polarToCartesian(from);
    const e = polarToCartesian(to);
    const large = to - from > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  const endAngle = startAngle + (sweepTotal * score) / 100;

  // Color gradient based on score
  const color =
    score >= 90
      ? "#22c55e"
      : score >= 80
      ? "#f59e0b"
      : score >= 60
      ? "#ef4444"
      : "#7f1d1d";

  const glowColor =
    score >= 90
      ? "rgba(34,197,94,0.35)"
      : score >= 80
      ? "rgba(245,158,11,0.35)"
      : "rgba(239,68,68,0.45)";

  return (
    <div className="relative flex items-center justify-center">
      <svg width="180" height="160" viewBox="0 0 180 180">
        {/* Track arc */}
        <path
          d={arcPath(startAngle, startAngle + sweepTotal)}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        {/* Score arc */}
        {score > 0 && (
          <path
            d={arcPath(startAngle, endAngle)}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            style={{
              filter: `drop-shadow(0 0 6px ${glowColor})`,
              transition: "all 800ms cubic-bezier(0.4,0,0.2,1)",
            }}
          />
        )}
        {/* Score text */}
        <text
          x={cx}
          y={cy - 8}
          textAnchor="middle"
          fill={color}
          fontSize="32"
          fontWeight="700"
          fontFamily="'Inter', system-ui, sans-serif"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {score}
        </text>
        <text
          x={cx}
          y={cy + 14}
          textAnchor="middle"
          fill="var(--muted)"
          fontSize="10"
          fontWeight="500"
          letterSpacing="2"
          fontFamily="'Inter', system-ui, sans-serif"
        >
          / 100
        </text>
        <text
          x={cx}
          y={cy + 30}
          textAnchor="middle"
          fill="var(--muted-2)"
          fontSize="8.5"
          fontWeight="500"
          letterSpacing="1.5"
          fontFamily="'Inter', system-ui, sans-serif"
        >
          NCRI SCORE
        </text>
        {/* Min/Max labels */}
        <text x="14" y="158" fill="var(--muted-2)" fontSize="9" fontFamily="'Inter',sans-serif">0</text>
        <text x="148" y="158" fill="var(--muted-2)" fontSize="9" fontFamily="'Inter',sans-serif">100</text>
      </svg>
    </div>
  );
}

// ── Eligibility Badge ────────────────────────────────────────────────────────

function EligibilityBadge({ data }: { data: NcriData }) {
  const { eligibility } = data;
  const tierIcons: Record<string, typeof CheckCircle2> = {
    A: CheckCircle2,
    B: Eye,
    C: AlertTriangle,
    F: Ban,
  };
  const Icon = tierIcons[eligibility.tier] ?? AlertTriangle;

  const borderColor =
    eligibility.tier === "A"
      ? "border-[#22c55e]"
      : eligibility.tier === "B"
      ? "border-[#f59e0b]"
      : eligibility.tier === "F"
      ? "border-[#7f1d1d]"
      : "border-[#ef4444]";

  return (
    <div
      className={`surface-elev p-4 border-l-4 ${borderColor} flex flex-col gap-1.5`}
    >
      <div className="flex items-center gap-2">
        <Icon
          className="w-4 h-4 flex-shrink-0"
          style={{ color: eligibility.color }}
        />
        <p
          className="text-xs font-bold uppercase tracking-widest"
          style={{ color: eligibility.color }}
        >
          {eligibility.status}
        </p>
      </div>
      <p className="text-[11px] text-[color:var(--muted)] leading-relaxed">
        {eligibility.description}
      </p>
      <div className="flex items-center gap-2 pt-1">
        <span className="text-[10px] uppercase tracking-widest text-[color:var(--muted-2)]">
          Tier
        </span>
        <span
          className="text-sm font-bold metric-value"
          style={{ color: eligibility.color }}
        >
          {eligibility.tier}
        </span>
        <span className="text-[10px] text-[color:var(--muted-2)]">
          · {data.contractor}
        </span>
      </div>
    </div>
  );
}

// ── Financial Risk Card ──────────────────────────────────────────────────────

function FinancialRiskCard({ data }: { data: NcriData }) {
  const { financial_risk } = data;
  const isCritical =
    financial_risk.severity === "CRITICAL" ||
    financial_risk.severity === "FRAUD RISK";

  return (
    <div className="surface-elev p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <IndianRupee className="w-3.5 h-3.5 text-[color:var(--muted)]" />
        <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">
          Estimated Financial Risk
        </p>
      </div>
      <div className="flex items-end gap-3">
        <p
          className={`text-3xl font-bold metric-value ${
            isCritical ? "text-[color:var(--danger)]" : "text-[color:var(--warning)]"
          }`}
          style={{
            textShadow: isCritical
              ? "0 0 20px rgba(239,68,68,0.4)"
              : "0 0 20px rgba(245,158,11,0.3)",
          }}
        >
          {financial_risk.display}
        </p>
        <SeverityChip level={financial_risk.severity} />
      </div>
      <p className="text-[10px] text-[color:var(--muted-2)] leading-relaxed">
        {financial_risk.disclaimer}
      </p>
    </div>
  );
}

// ── Timeline Replay ──────────────────────────────────────────────────────────

function TimelineReplay({
  timeline,
}: {
  timeline: NcriTimelineEntry[];
}) {
  const [idx, setIdx] = useState(timeline.length - 1);
  const current = timeline[idx];

  if (!timeline.length) return null;

  const discrepancyMax = Math.max(...timeline.map((t) => t.discrepancy), 1);

  return (
    <div className="surface p-5 flex flex-col gap-4 fade-in">
      <div className="flex items-center gap-2">
        <Calendar className="w-3.5 h-3.5 text-[color:var(--muted)]" />
        <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">
          Timeline Replay
        </p>
        <span className="ml-auto text-xs font-semibold text-[color:var(--foreground)]">
          {current.month}
        </span>
      </div>

      {/* Month scrubber */}
      <div className="flex items-center gap-2">
        <button
          className="btn btn-ghost p-1 rounded-lg"
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
          disabled={idx === 0}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        <div className="flex-1 flex items-center gap-1">
          {timeline.map((t, i) => {
            const cfg = SEVERITY_CONFIG[t.severity] ?? SEVERITY_CONFIG["LOW"];
            return (
              <button
                key={i}
                onClick={() => setIdx(i)}
                title={t.month}
                className={`flex-1 h-2 rounded-full transition-all duration-200 ${
                  i === idx ? "scale-y-150" : "opacity-50 hover:opacity-80"
                }`}
                style={{
                  background:
                    i === idx
                      ? cfg.dot.replace("bg-[", "").replace("]", "")
                      : "var(--surface-3)",
                  boxShadow:
                    i === idx ? `0 0 8px ${cfg.ring}` : "none",
                }}
              />
            );
          })}
        </div>

        <button
          className="btn btn-ghost p-1 rounded-lg"
          onClick={() => setIdx((i) => Math.min(timeline.length - 1, i + 1))}
          disabled={idx === timeline.length - 1}
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Snapshot content */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Satellite image */}
        <div className="rounded-xl overflow-hidden border border-[color:var(--border)] bg-[color:var(--surface-2)] aspect-video flex items-center justify-center">
          {assetUrl(current.satellite_image) ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={assetUrl(current.satellite_image)!}
              alt={`Satellite ${current.month}`}
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          ) : null}
          <p className="absolute text-[10px] text-[color:var(--muted-2)]">
            Sentinel-2 · {current.month}
          </p>
        </div>

        {/* Stats panel */}
        <div className="flex flex-col gap-3">
          <StatRow
            label="DPR Claimed"
            value={`${current.dpr_claimed_pct}%`}
            color="var(--foreground)"
          />
          <StatRow
            label="Satellite Verified"
            value={`${current.satellite_verified_pct}%`}
            color="var(--primary)"
          />
          <StatRow
            label="Discrepancy"
            value={`+${current.discrepancy}%`}
            color={
              current.severity === "FRAUD RISK" || current.severity === "CRITICAL"
                ? "var(--danger)"
                : "var(--warning)"
            }
          />
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">
              Severity
            </span>
            <SeverityChip level={current.severity} />
          </div>
        </div>
      </div>

      {/* Discrepancy bar chart */}
      <div>
        <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)] mb-2">
          Billing vs Reality — 6 Months
        </p>
        <div className="flex items-end gap-1 h-16">
          {timeline.map((t, i) => {
            const heightPct = (t.discrepancy / discrepancyMax) * 100;
            const cfg = SEVERITY_CONFIG[t.severity];
            const dotHex = cfg.dot.replace("bg-[", "").replace("]", "");
            return (
              <div
                key={i}
                className="flex-1 flex flex-col items-center gap-1 cursor-pointer"
                onClick={() => setIdx(i)}
              >
                <div className="w-full relative flex items-end" style={{ height: "52px" }}>
                  <div
                    className="w-full rounded-t transition-all duration-300"
                    style={{
                      height: `${Math.max(heightPct, 4)}%`,
                      background: i === idx ? dotHex : "var(--surface-3)",
                      boxShadow: i === idx ? `0 0 8px ${dotHex}55` : "none",
                    }}
                  />
                </div>
                <span className="text-[8px] text-[color:var(--muted-2)]">
                  {t.month.split(" ")[0].slice(0, 3)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StatRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-[color:var(--muted)]">{label}</span>
      <span className="text-sm font-semibold metric-value" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

// ── Audit Ledger ─────────────────────────────────────────────────────────────

const VIOLATION_ICON: Record<string, typeof ShieldAlert> = {
  IMAGE_TAMPERING: Ban,
  GHOST_ALERT: AlertTriangle,
  LAG_WARNING: TrendingDown,
  SAFETY_VIOLATION: ShieldAlert,
  ROUTINE_INSPECTION: CheckCircle2,
};

function AuditLedger({ entries }: { entries: NcriLedgerEntry[] }) {
  return (
    <div className="surface p-5 flex flex-col gap-3 fade-in">
      <div className="flex items-center gap-2">
        <FileText className="w-3.5 h-3.5 text-[color:var(--muted)]" />
        <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">
          Compliance Audit Ledger
        </p>
      </div>

      <div className="flex flex-col gap-0">
        {[...entries].reverse().map((entry, i) => {
          const Icon = VIOLATION_ICON[entry.type] ?? FileText;
          const cfg = SEVERITY_CONFIG[entry.severity] ?? SEVERITY_CONFIG["LOW"];
          const isNegative = entry.deduction < 0;

          return (
            <div key={i} className="relative pl-8 pb-4 last:pb-0">
              {/* Timeline line */}
              {i < entries.length - 1 && (
                <div className="absolute left-[13px] top-6 bottom-0 w-px bg-[color:var(--border)]" />
              )}
              {/* Icon dot */}
              <div
                className="absolute left-0 top-0.5 w-7 h-7 rounded-full flex items-center justify-center border"
                style={{
                  background: isNegative ? "var(--surface-3)" : "var(--surface-2)",
                  borderColor: isNegative ? cfg.ring : "var(--border)",
                  boxShadow: isNegative ? `0 0 8px ${cfg.ring}` : "none",
                }}
              >
                <Icon
                  className="w-3 h-3"
                  style={{ color: isNegative ? cfg.dot.replace("bg-[", "").replace("]", "") : "var(--muted)" }}
                />
              </div>

              <div className="surface-elev px-3 py-2.5 flex flex-col gap-1">
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <SeverityChip level={entry.severity} />
                    <span className="text-[10px] text-[color:var(--muted-2)]">
                      {entry.date}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isNegative && (
                      <span className="text-xs font-bold metric-value text-[color:var(--danger)]">
                        {entry.deduction} pts
                      </span>
                    )}
                    <span className="text-[10px] text-[color:var(--muted-2)]">
                      Balance: <strong className="text-[color:var(--foreground)]">{entry.balance_after}</strong>
                    </span>
                  </div>
                </div>
                <p className="text-[11px] text-[color:var(--muted)] leading-relaxed">
                  {entry.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

type FetchState =
  | { forId: string; status: "success"; data: NcriData; error: null }
  | { forId: string; status: "error"; data: null; error: string }
  | { forId: null; status: "idle"; data: null; error: null };

const IDLE_STATE: FetchState = { forId: null, status: "idle", data: null, error: null };

export function ContractorTrust({ projectId }: { projectId: string }) {
  const [state, setState] = useState<FetchState>(IDLE_STATE);
  const [displayScore, setDisplayScore] = useState(0);
  const [syncTime, setSyncTime] = useState<string | null>(null);
  const animRef = useRef<number | null>(null);
  const { version } = useGovernanceEvents();

  useEffect(() => {
    let cancelled = false;
    fetchNcri(projectId)
      .then((d) => {
        if (!cancelled) {
          setState({ forId: projectId, status: "success", data: d, error: null });
          setSyncTime(
            new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })
          );
        }
      })
      .catch((e) => {
        if (!cancelled)
          setState({ forId: projectId, status: "error", data: null, error: e.message });
      });
    return () => { cancelled = true; };
  }, [projectId, version]);

  // Animate score counter whenever the real score changes
  const liveScore = state.status === "success" ? state.data.ncri_score : 0;
  useEffect(() => {
    if (animRef.current) cancelAnimationFrame(animRef.current);
    const start = displayScore;
    const end = liveScore;
    if (start === end) return;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - t0) / 1200, 1);
      const eased = 1 - Math.pow(1 - p, 3); // cubic ease-out
      setDisplayScore(Math.round(start + (end - start) * eased));
      if (p < 1) { animRef.current = requestAnimationFrame(tick); }
    };
    animRef.current = requestAnimationFrame(tick);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveScore]);

  // Derive loading: no result yet, or the result is for a different project
  const loading = state.forId !== projectId;
  const error = !loading && state.status === "error" ? state.error : null;
  const data = !loading && state.status === "success" ? state.data : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 gap-3 text-[color:var(--muted)]">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span className="text-sm">Loading NCRI scorecard…</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="surface p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-[color:var(--warning)] mx-auto mb-2" />
        <p className="text-sm text-[color:var(--muted)]">
          {error ?? "No governance data available for this project."}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 fade-in">
      {/* Header */}
      <div>
        <h3 className="text-base font-semibold tracking-tight">
          National Contractor Reliability Index
        </h3>
        <div className="flex items-center gap-3 mt-0.5">
          <p className="text-xs text-[color:var(--muted)]">
            {data.project_name} · {data.contractor}
          </p>
          {syncTime && (
            <p className="flex items-center gap-1 text-[10px] text-[color:var(--muted-2)]">
              <RefreshCw className="w-2.5 h-2.5" />
              Last telemetry sync: {syncTime} IST
            </p>
          )}
        </div>
      </div>

      {/* Top row — Gauge + Eligibility + Financial Risk */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Gauge card */}
        <div className="surface p-5 flex flex-col items-center gap-2">
          <NcriGauge score={displayScore} />
          <div className="flex flex-wrap gap-2 justify-center">
            {data.active_violations.map((v, i) => (
              <SeverityChip key={i} level={v.severity} />
            ))}
            {data.active_violations.length === 0 && (
              <SeverityChip level="LOW" />
            )}
          </div>
        </div>

        {/* Eligibility + Financial Risk stacked */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <EligibilityBadge data={data} />
          <FinancialRiskCard data={data} />
        </div>
      </div>

      {/* Active violations summary */}
      {data.active_violations.length > 0 && (() => {
        const shown = data.active_violations.slice(0, 3);
        const overflow = data.active_violations.length - 3;
        return (
          <div className="surface p-4 flex flex-col gap-3 fade-in">
            <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">
              Active Violations ({data.active_violations.length})
            </p>
            <div className="flex flex-col gap-2">
              {shown.map((v, i) => (
                <div
                  key={i}
                  className="surface-elev px-3 py-2.5 flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <SeverityChip level={v.severity} />
                      <span className="text-[10px] text-[color:var(--muted-2)]">{v.date}</span>
                    </div>
                  </div>
                  <p className="text-[11px] font-medium text-[color:var(--foreground)]">
                    {v.type.replace(/_/g, " ")}
                  </p>
                  <p className="text-[10px] text-[color:var(--muted)] leading-relaxed">
                    {v.description}
                  </p>
                  {v.recommended_action && (
                    <ActionChip action={v.recommended_action} projectId={data.project_id || projectId} />
                  )}
                </div>
              ))}
              {overflow > 0 && (
                <div className="surface-elev px-3 py-2 text-center">
                  <span className="text-[10px] text-[color:var(--muted)]">+{overflow} more violation{overflow > 1 ? "s" : ""}</span>
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {/* Timeline Replay */}
      {data.timeline.length > 0 && (
        <TimelineReplay timeline={data.timeline} />
      )}

      {/* Audit Ledger */}
      {data.audit_ledger.length > 0 && (
        <AuditLedger entries={data.audit_ledger} />
      )}
    </div>
  );
}
