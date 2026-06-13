"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Gavel,
  IndianRupee,
  Clock,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Award,
  ChevronRight,
  Loader2,
  Star,
  Ban,
  X,
  FileText,
  User,
  TrendingDown,
  TrendingUp,
  Info,
  CalendarDays,
  MapPin,
  CircleCheck,
  CircleX,
} from "lucide-react";
import {
  fetchTenders,
  fetchTenderDetail,
  awardTenderContract,
  submitBid,
  verifyGstin,
  Tender,
  Bid,
  TenderDetail,
  TenderRecommendation,
  GstinVerification,
} from "@/lib/api";

// ── Helpers ────────────────────────────────────────────────────────────────

function daysUntil(dateStr: string): number {
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function formatCr(cr: number): string {
  return `₹${cr.toLocaleString("en-IN")} Cr`;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function ncriColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  if (score >= 40) return "#f97316";
  return "#ef4444";
}
function ncriBg(score: number): string {
  if (score >= 80) return "rgba(34,197,94,0.12)";
  if (score >= 60) return "rgba(245,158,11,0.12)";
  if (score >= 40) return "rgba(249,115,22,0.12)";
  return "rgba(239,68,68,0.12)";
}
function ncriLabel(score: number): string {
  if (score >= 80) return "TIER A";
  if (score >= 60) return "TIER B";
  if (score >= 40) return "TIER C";
  return "TIER F";
}

const FLAG_META: Record<string, { label: string; color: string; bg: string }> = {
  BLACKLISTED:        { label: "Blacklisted",        color: "#ef4444", bg: "rgba(239,68,68,0.12)" },
  HIGH_RISK:          { label: "High Risk",           color: "#f97316", bg: "rgba(249,115,22,0.12)" },
  ABNORMALLY_LOW_BID: { label: "Abnormally Low Bid", color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  SUSPICIOUSLY_LOW:   { label: "Suspicious Price",   color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  NEW_ENTITY:         { label: "New Entity",          color: "#3b82f6", bg: "rgba(59,130,246,0.12)" },
  ACTIVE_VIOLATION:   { label: "Active Violation",   color: "#ef4444", bg: "rgba(239,68,68,0.12)" },
  CARTEL_SUSPECT:     { label: "Cartel Suspect",     color: "#a855f7", bg: "rgba(168,85,247,0.12)" },
};

// ── Micro components ───────────────────────────────────────────────────────

function FlagPill({ flag }: { flag: string }) {
  const m = FLAG_META[flag];
  if (!m) return null;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide border"
      style={{ color: m.color, background: m.bg, borderColor: `${m.color}30` }}
    >
      {m.label}
    </span>
  );
}

function NcriBadge({ score, size = "sm" }: { score: number; size?: "sm" | "lg" }) {
  const textSize = size === "lg" ? "text-lg" : "text-[12px]";
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-bold ${textSize} tabular-nums`}
      style={{ color: ncriColor(score), background: ncriBg(score) }}
    >
      <ShieldCheck className={size === "lg" ? "w-4 h-4" : "w-3 h-3"} />
      {score}<span className="opacity-50 font-medium text-[10px]">/100</span>
      <span className="text-[9px] opacity-70 font-semibold">{ncriLabel(score)}</span>
    </span>
  );
}

function StatusChip({ status }: { status: Tender["status"] }) {
  if (status === "OPEN")
    return <span className="chip chip-success"><span className="dot bg-[color:var(--success)]" />Open for Bids</span>;
  if (status === "AWARDED")
    return <span className="chip chip-info"><Award className="w-3 h-3" />Awarded</span>;
  return <span className="chip chip-muted">Closed</span>;
}

// ── Tender Rail Card ───────────────────────────────────────────────────────

function TenderRailCard({ tender, selected, onSelect }: { tender: Tender; selected: boolean; onSelect: () => void }) {
  const days = daysUntil(tender.deadline);
  const urgency = days <= 2 ? "danger" : days <= 5 ? "warning" : "success";
  const urgencyColor = urgency === "danger" ? "var(--danger)" : urgency === "warning" ? "var(--warning)" : "var(--success)";

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-4 rounded-xl border transition-all duration-150 ${
        selected
          ? "bg-[color:var(--surface-3)] border-[color:var(--primary)] shadow-[0_0_0_1px_var(--primary)]"
          : "bg-[color:var(--surface-2)] border-[color:var(--border)] hover:border-[color:var(--border-strong)]"
      }`}
    >
      <div className="flex items-start gap-2 mb-3">
        <div
          className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: selected ? "var(--primary-soft)" : "var(--surface-3)" }}
        >
          <Gavel className="w-4 h-4" style={{ color: selected ? "var(--primary)" : "var(--muted)" }} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-semibold leading-snug line-clamp-2">{tender.project_name}</p>
          <p className="text-[10px] text-[color:var(--muted)] mt-0.5">{tender.location}</p>
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] mb-2">
        <span className="font-bold text-[color:var(--primary)]">{formatCr(tender.estimated_value_cr)}</span>
        <StatusChip status={tender.status} />
      </div>

      <div className="flex items-center justify-between text-[10px] text-[color:var(--muted)]">
        <span>{tender.bid_count ?? 0} bids received</span>
        {days >= 0 ? (
          <span className="font-semibold" style={{ color: urgencyColor }}>
            <Clock className="w-3 h-3 inline mr-0.5" />{days}d left
          </span>
        ) : (
          <span className="text-[color:var(--muted)]">Closed {Math.abs(days)}d ago</span>
        )}
      </div>
    </button>
  );
}

// ── Bid Table Row ──────────────────────────────────────────────────────────

function BidTableRow({
  bid, isRecommended, onAward, awarding, tenderStatus,
}: {
  bid: Bid; isRecommended: boolean; onAward: (b: Bid) => void; awarding: boolean; tenderStatus: Tender["status"];
}) {
  return (
    <tr
      className="border-b border-[color:var(--border)] transition-colors"
      style={{
        background: bid.eligibility === "REJECTED"
          ? "rgba(239,68,68,0.03)"
          : isRecommended
          ? "rgba(34,197,94,0.04)"
          : "transparent",
      }}
    >
      {/* Rank */}
      <td className="px-4 py-3.5 w-12">
        <div className="flex items-center gap-1">
          <span
            className="text-[12px] font-black tabular-nums"
            style={{ color: bid.eligibility === "REJECTED" ? "var(--danger)" : "var(--muted)" }}
          >
            {bid.rank}
          </span>
          {isRecommended && <Star className="w-3 h-3 text-[color:var(--success)]" fill="currentColor" />}
        </div>
      </td>

      {/* Contractor */}
      <td className="px-4 py-3.5">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[12px] font-semibold">{bid.contractor_name}</span>
            {bid.eligibility === "REJECTED" && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-[color:var(--danger-soft)] text-[color:var(--danger)]">
                <Ban className="w-2.5 h-2.5" /> Disqualified
              </span>
            )}
            {isRecommended && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-[color:var(--success-soft)] text-[color:var(--success)]">
                Recommended
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {bid.flags.slice(0, 2).map((f) => <FlagPill key={f} flag={f} />)}
            {bid.flags.length > 2 && (
              <span className="text-[9px] text-[color:var(--muted)] font-semibold">+{bid.flags.length - 2} more</span>
            )}
            <span className="text-[10px] text-[color:var(--muted-2)]">{bid.years_of_experience}yr exp</span>
          </div>
        </div>
      </td>

      {/* NCRI */}
      <td className="px-4 py-3.5 text-center">
        <NcriBadge score={bid.ncri_score} />
      </td>

      {/* Bid Amount */}
      <td className="px-4 py-3.5 text-right">
        <p className="text-[13px] font-bold tabular-nums">{formatCr(bid.bid_amount_cr)}</p>
      </td>

      {/* Anomaly */}
      <td className="px-4 py-3.5 text-center">
        <div className="flex flex-col items-center gap-1">
          <span
            className="text-[12px] font-bold tabular-nums"
            style={{
              color: bid.anomaly_score > 50 ? "var(--danger)" : bid.anomaly_score > 25 ? "var(--warning)" : "var(--success)",
            }}
          >
            {bid.anomaly_score}
          </span>
          <div className="w-12 h-1 rounded-full bg-[color:var(--surface-3)] overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${bid.anomaly_score}%`,
                background: bid.anomaly_score > 50 ? "var(--danger)" : bid.anomaly_score > 25 ? "var(--warning)" : "var(--success)",
              }}
            />
          </div>
        </div>
      </td>

      {/* Action */}
      <td className="px-4 py-3.5 text-right">
        {tenderStatus === "OPEN" && bid.eligibility !== "REJECTED" ? (
          <button
            onClick={() => onAward(bid)}
            disabled={awarding}
            className="btn btn-secondary text-[11px] px-3 py-1.5"
            style={isRecommended ? { borderColor: "var(--success)", color: "var(--success)" } : {}}
          >
            {awarding ? <Loader2 className="w-3 h-3 animate-spin" /> : "Award Contract"}
          </button>
        ) : tenderStatus === "AWARDED" ? (
          <span className="text-[10px] text-[color:var(--muted)]">Closed</span>
        ) : null}
      </td>
    </tr>
  );
}

// ── AI Recommendation Banner ───────────────────────────────────────────────

function RecommendationBanner({ rec }: { rec: TenderRecommendation }) {
  const color = rec.risk_level === "LOW" ? "var(--success)" : rec.risk_level === "MODERATE" ? "var(--warning)" : "var(--danger)";
  const bg = rec.risk_level === "LOW" ? "rgba(34,197,94,0.06)" : rec.risk_level === "MODERATE" ? "rgba(245,158,11,0.06)" : "rgba(239,68,68,0.06)";
  const Icon = rec.risk_level === "LOW" ? CircleCheck : rec.risk_level === "MODERATE" ? Info : AlertTriangle;

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: `${color}50`, background: bg }}>
      <div className="flex items-start gap-3">
        <Icon className="w-4 h-4 shrink-0 mt-0.5" style={{ color }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="text-[11px] font-bold uppercase tracking-widest" style={{ color }}>
              Atlas Assessment
            </span>
            <span
              className="text-[9px] font-bold uppercase px-2 py-0.5 rounded border"
              style={{ color, borderColor: `${color}40`, background: "transparent" }}
            >
              {rec.risk_level} RISK
            </span>
          </div>
          <p className="text-[12px] leading-relaxed text-[color:var(--foreground)]">{rec.reason}</p>
          <div className="mt-2.5 flex gap-5 text-[11px]">
            <span className="flex items-center gap-1"><CircleCheck className="w-3 h-3 text-[color:var(--success)]" /><span className="text-[color:var(--muted)]">{rec.eligible_count} Eligible</span></span>
            <span className="flex items-center gap-1"><Info className="w-3 h-3 text-[color:var(--warning)]" /><span className="text-[color:var(--muted)]">{rec.flagged_count} Flagged</span></span>
            <span className="flex items-center gap-1"><CircleX className="w-3 h-3 text-[color:var(--danger)]" /><span className="text-[color:var(--muted)]">{rec.rejected_count} Rejected</span></span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Award Confirm Modal ────────────────────────────────────────────────────

function AwardModal({ bid, tender, onConfirm, onCancel, loading }: {
  bid: Bid; tender: Tender; onConfirm: () => void; onCancel: () => void; loading: boolean;
}) {
  const [confirmText, setConfirmText] = useState("");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-[color:var(--surface)] border border-[color:var(--border-strong)] rounded-2xl max-w-lg w-full mx-4 fade-in overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-[color:var(--border)]">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-base font-semibold">Confirm Contract Award</h3>
              <p className="text-[11px] text-[color:var(--muted)] mt-0.5">
                This award will be permanently recorded in the Atlas Assurance audit ledger and cannot be undone.
              </p>
            </div>
            <button onClick={onCancel} className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] p-1">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="px-6 py-5 space-y-4">
          {/* Tender ref */}
          <div className="surface-elev px-4 py-3 rounded-xl">
            <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)] mb-0.5">Project Tender</p>
            <p className="text-[13px] font-medium">{tender.project_name}</p>
            <p className="text-[10px] text-[color:var(--muted)] mt-0.5">Ref: {tender.tender_id}</p>
          </div>

          {/* Key stats */}
          <div className="grid grid-cols-3 gap-2.5">
            {[
              { label: "Contractor", value: bid.contractor_name, color: undefined },
              { label: "Contract Value", value: formatCr(bid.bid_amount_cr), color: "var(--success)" },
              { label: "NCRI Score", value: `${bid.ncri_score}/100`, color: ncriColor(bid.ncri_score) },
            ].map((s) => (
              <div key={s.label} className="surface-elev px-3 py-2.5 rounded-lg">
                <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)] mb-1">{s.label}</p>
                <p className="text-[12px] font-bold" style={{ color: s.color }}>{s.value}</p>
              </div>
            ))}
          </div>

          {/* Flags warning */}
          {bid.flags.length > 0 && (
            <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-[color:var(--warning-soft)] border border-[color:var(--warning)]/25">
              <AlertTriangle className="w-4 h-4 text-[color:var(--warning)] shrink-0 mt-0.5" />
              <p className="text-[11px] text-[color:var(--warning)] leading-relaxed">
                <span className="font-semibold">Active flags:</span>{" "}
                {bid.flags.map((f) => FLAG_META[f]?.label || f).join(", ")}.{" "}
                You are proceeding despite flagged risks. Ensure physical verification is complete.
              </p>
            </div>
          )}

          {/* Confirm input */}
          <div>
            <label className="text-[11px] text-[color:var(--muted)] mb-2 block">
              Type <span className="font-bold text-[color:var(--foreground)] font-mono">AWARD</span> to confirm this contract
            </label>
            <input
              className="input w-full font-mono tracking-widest uppercase"
              placeholder="AWARD"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value.toUpperCase())}
            />
          </div>

          <div className="flex gap-3">
            <button onClick={onCancel} className="btn btn-secondary flex-1">Cancel</button>
            <button
              onClick={onConfirm}
              disabled={confirmText !== "AWARD" || loading}
              className="btn btn-primary flex-1"
              style={confirmText === "AWARD" ? { background: "var(--success)", borderColor: "var(--success)" } : {}}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Award className="w-4 h-4" /> Award Contract</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Professional Bid Form ──────────────────────────────────────────────────

function BidSubmissionPanel({
  tenderId,
  tender,
  onBidSubmitted,
}: {
  tenderId: string;
  tender: Tender;
  onBidSubmitted: () => void;
}) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [gstin, setGstin]         = useState("");
  const [gstVerifying, setGstVerifying] = useState(false);
  const [gstResult, setGstResult] = useState<GstinVerification | null>(null);
  const [name, setName]           = useState("");
  const [cin, setCin]             = useState("");
  const [yearsExp, setYearsExp]   = useState("5");
  const [isNew, setIsNew]         = useState(false);
  const [bidAmount, setBidAmount] = useState("");
  const [declared, setDeclared]   = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult]       = useState<Bid | null>(null);
  const [error, setError]         = useState("");

  // GSTIN format is 15 chars matching the standard regex
  const gstinFormatOk = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/.test(
    gstin.trim().toUpperCase()
  );

  const handleVerifyGstin = async () => {
    setGstVerifying(true);
    setGstResult(null);
    try {
      const res = await verifyGstin(gstin);
      setGstResult(res);
      // Auto-fill company name from government registry
      if (res.company_name) {
        setName(res.company_name);
      }
    } catch {
      setGstResult(null);
    } finally {
      setGstVerifying(false);
    }
  };

  const contractorId = name
    ? "CONT-" + name.trim().toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6)
    : (gstin ? "CONT-" + gstin.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(5, 11) : "");

  const bidNum = parseFloat(bidAmount);
  const bidRatio = !isNaN(bidNum) && tender.estimated_value_cr > 0
    ? bidNum / tender.estimated_value_cr : null;

  const priceSeverity = bidRatio === null ? null
    : bidRatio < 0.80 ? "danger"
    : bidRatio < 0.90 ? "warning"
    : "good";

  // Step 1 is complete only if GSTIN is verified and not rejected
  const canStep1 = gstResult !== null && gstResult.trust_level !== "REJECTED" && name.trim().length >= 3;
  const canStep2 = yearsExp.trim() !== "" && parseInt(yearsExp) > 0;
  const canSubmit = !isNaN(bidNum) && bidNum > 0 && declared;

  const reset = () => {
    setStep(1); setName(""); setCin(""); setYearsExp("5");
    setIsNew(false); setBidAmount(""); setDeclared(false);
    setResult(null); setError("");
    setGstin(""); setGstResult(null);
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError("");
    try {
      const bid = await submitBid(tenderId, {
        contractor_id: contractorId,
        contractor_name: name.trim(),
        bid_amount_cr: bidNum,
        is_new_entity: isNew,
        years_of_experience: parseInt(yearsExp) || 1,
      });
      setResult(bid);
      onBidSubmitted();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Bid submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Receipt view ────────────────────────────────────────────────────────
  if (result) {
    const statusColor = result.eligibility === "ELIGIBLE" ? "var(--success)"
      : result.eligibility === "FLAGGED" ? "var(--warning)" : "var(--danger)";

    return (
      <div className="flex flex-col h-full fade-in">
        <div className="px-6 py-5 border-b border-[color:var(--border)]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">Official Bid Receipt</p>
              <h3 className="text-base font-semibold mt-0.5">Bid Registered</h3>
            </div>
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: `${statusColor}15` }}
            >
              {result.eligibility === "ELIGIBLE" ? (
                <CircleCheck className="w-5 h-5" style={{ color: statusColor }} />
              ) : result.eligibility === "FLAGGED" ? (
                <AlertTriangle className="w-5 h-5" style={{ color: statusColor }} />
              ) : (
                <CircleX className="w-5 h-5" style={{ color: statusColor }} />
              )}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto scroll-thin px-6 py-5 space-y-5">
          {/* Bid ID */}
          <div className="surface p-4 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">Bid Reference</span>
              <span className="font-mono text-[11px] text-[color:var(--foreground)] font-bold">{result.bid_id}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">Contractor</span>
              <span className="text-[12px] font-semibold">{result.contractor_name}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">Bid Amount</span>
              <span className="text-[13px] font-bold text-[color:var(--primary)]">{formatCr(result.bid_amount_cr)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">Submitted At</span>
              <span className="text-[11px]">{new Date(result.submitted_at).toLocaleString("en-IN")}</span>
            </div>
          </div>

          {/* NCRI + Anomaly */}
          <div className="grid grid-cols-2 gap-3">
            <div className="surface-elev rounded-xl p-4 text-center">
              <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)] mb-2">NCRI Auto-Fetched</p>
              <p className="text-2xl font-black tabular-nums" style={{ color: ncriColor(result.ncri_score) }}>
                {result.ncri_score}
              </p>
              <p className="text-[9px] text-[color:var(--muted)] mt-0.5">out of 100</p>
            </div>
            <div className="surface-elev rounded-xl p-4 text-center">
              <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)] mb-2">Anomaly Score</p>
              <p className="text-2xl font-black tabular-nums"
                style={{ color: result.anomaly_score > 50 ? "var(--danger)" : result.anomaly_score > 25 ? "var(--warning)" : "var(--success)" }}
              >
                {result.anomaly_score}
              </p>
              <p className="text-[9px] text-[color:var(--muted)] mt-0.5">out of 100</p>
            </div>
          </div>

          {/* Eligibility */}
          <div
            className="rounded-xl border p-4"
            style={{ borderColor: `${statusColor}40`, background: `${statusColor}08` }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: statusColor }}>
                Eligibility Status
              </span>
            </div>
            <p className="text-base font-black" style={{ color: statusColor }}>{result.eligibility}</p>
            {result.eligibility === "REJECTED" && (
              <p className="text-[11px] text-[color:var(--muted)] mt-1.5 leading-relaxed">
                Your NCRI score ({result.ncri_score}) is below the minimum requirement of{" "}
                <strong>{tender.min_ncri_required}</strong> for this tender. This bid has been automatically rejected.
              </p>
            )}
            {result.eligibility === "FLAGGED" && (
              <p className="text-[11px] text-[color:var(--muted)] mt-1.5 leading-relaxed">
                Your bid has been accepted but flagged for additional scrutiny by the procurement committee.
              </p>
            )}
            {result.eligibility === "ELIGIBLE" && (
              <p className="text-[11px] text-[color:var(--muted)] mt-1.5 leading-relaxed">
                Your bid meets all eligibility criteria and is now visible in the procurement leaderboard.
              </p>
            )}
          </div>

          {/* Flags */}
          {result.flags.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)] mb-2">Active Flags</p>
              <div className="flex flex-wrap gap-1.5">
                {result.flags.map((f) => <FlagPill key={f} flag={f} />)}
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-[color:var(--border)]">
          <button onClick={reset} className="btn btn-secondary w-full text-[12px]">
            Submit Another Bid
          </button>
        </div>
      </div>
    );
  }

  // ── Step progress ───────────────────────────────────────────────────────
  const steps = [
    { n: 1, label: "Identity" },
    { n: 2, label: "Qualification" },
    { n: 3, label: "Financial Bid" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-5 border-b border-[color:var(--border)] shrink-0">
        <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">Government Procurement Portal</p>
        <h3 className="text-[14px] font-bold mt-0.5">Submit Your Bid</h3>
        <p className="text-[10px] text-[color:var(--muted)] mt-0.5">Ref: {tenderId}</p>

        {/* Step indicator */}
        <div className="flex items-center gap-0 mt-4">
          {steps.map((s, i) => (
            <div key={s.n} className="flex items-center flex-1">
              <div className="flex flex-col items-center gap-1 flex-1">
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all"
                  style={{
                    background: step > s.n ? "var(--success)" : step === s.n ? "var(--primary)" : "var(--surface-3)",
                    color: step >= s.n ? "white" : "var(--muted)",
                  }}
                >
                  {step > s.n ? "✓" : s.n}
                </div>
                <span className="text-[9px] uppercase tracking-wide"
                  style={{ color: step === s.n ? "var(--foreground)" : "var(--muted)" }}>
                  {s.label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div
                  className="flex-1 h-px mb-4"
                  style={{ background: step > s.n ? "var(--success)" : "var(--border)" }}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step content */}
      <div className="flex-1 overflow-y-auto scroll-thin px-6 py-5 space-y-4">

        {/* Step 1: Contractor Identity + GSTIN Verification */}
        {step === 1 && (
          <div className="space-y-4 fade-in">
            <div className="flex items-center gap-2 mb-2">
              <User className="w-4 h-4 text-[color:var(--primary)]" />
              <h4 className="text-[12px] font-bold uppercase tracking-widest">Contractor Identity</h4>
            </div>

            {/* GSTIN input */}
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--muted)] mb-1.5 block">
                GSTIN (GST Identification Number) <span className="text-[color:var(--danger)]">*</span>
              </label>
              <div className="flex gap-2">
                <input
                  className="input flex-1 font-mono tracking-widest uppercase"
                  placeholder="e.g. 27AAACL0548C1Z5"
                  maxLength={15}
                  value={gstin}
                  onChange={(e) => {
                    setGstin(e.target.value.toUpperCase());
                    setGstResult(null); // reset on change
                    if (e.target.value.toUpperCase() !== name.toUpperCase()) {
                      // only clear auto-filled name if user changes GSTIN
                    }
                  }}
                />
                <button
                  onClick={handleVerifyGstin}
                  disabled={!gstinFormatOk || gstVerifying}
                  className="btn btn-secondary px-3 text-[11px] shrink-0 whitespace-nowrap"
                  style={gstinFormatOk ? { borderColor: "var(--primary)", color: "var(--primary)" } : {}}
                >
                  {gstVerifying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><ShieldCheck className="w-3.5 h-3.5" /> Verify</>}
                </button>
              </div>

              {/* Real-time format indicator */}
              {gstin.length > 0 && (
                <div className="mt-1.5 flex items-center gap-1.5">
                  {gstin.length < 15 ? (
                    <span className="text-[10px] text-[color:var(--muted)]">{15 - gstin.length} more characters needed</span>
                  ) : gstinFormatOk ? (
                    <span className="text-[10px] text-[color:var(--success)] flex items-center gap-1">
                      <CircleCheck className="w-3 h-3" /> Valid format — click Verify to check government registry
                    </span>
                  ) : (
                    <span className="text-[10px] text-[color:var(--danger)] flex items-center gap-1">
                      <CircleX className="w-3 h-3" /> Invalid GSTIN format
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Verification result */}
            {gstResult && (
              <div
                className="rounded-xl border p-4 space-y-3 fade-in"
                style={{
                  borderColor: gstResult.trust_level === "HIGH" ? "var(--success)"
                    : gstResult.trust_level === "MEDIUM" ? "var(--warning)"
                    : gstResult.trust_level === "REJECTED" ? "var(--danger)" : "var(--border)",
                  background: gstResult.trust_level === "HIGH" ? "rgba(34,197,94,0.05)"
                    : gstResult.trust_level === "MEDIUM" ? "rgba(245,158,11,0.05)"
                    : gstResult.trust_level === "REJECTED" ? "rgba(239,68,68,0.05)" : "transparent",
                }}
              >
                {/* Trust badge */}
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest"
                    style={{
                      color: gstResult.trust_level === "HIGH" ? "var(--success)"
                        : gstResult.trust_level === "MEDIUM" ? "var(--warning)"
                        : gstResult.trust_level === "REJECTED" ? "var(--danger)" : "var(--muted)",
                    }}
                  >
                    {gstResult.trust_level === "HIGH" && <CircleCheck className="w-3 h-3 inline mr-1" />}
                    {gstResult.trust_level === "REJECTED" && <CircleX className="w-3 h-3 inline mr-1" />}
                    {gstResult.trust_level === "MEDIUM" && <AlertTriangle className="w-3 h-3 inline mr-1" />}
                    Trust Level: {gstResult.trust_level}
                  </span>
                  <span className="text-[9px] text-[color:var(--muted)]">{gstResult.source}</span>
                </div>

                {/* Verified company details */}
                {gstResult.format_valid && (
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: "State", value: gstResult.state },
                      { label: "Entity Type", value: gstResult.entity_type },
                      { label: "PAN (embedded)", value: gstResult.pan },
                      { label: "GST Status", value: gstResult.gst_status },
                    ].map((item) => item.value ? (
                      <div key={item.label} className="surface-elev px-3 py-2 rounded-lg">
                        <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)]">{item.label}</p>
                        <p className="text-[11px] font-semibold mt-0.5">{item.value}</p>
                      </div>
                    ) : null)}
                  </div>
                )}

                {/* NCRI cross-reference */}
                {gstResult.ncri.found && (
                  <div className="flex items-start gap-2 p-2.5 rounded-lg"
                    style={{
                      background: (gstResult.ncri.violation_count ?? 0) > 0 ? "rgba(239,68,68,0.08)" : "rgba(34,197,94,0.08)",
                    }}
                  >
                    <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-0.5"
                      style={{ color: (gstResult.ncri.violation_count ?? 0) > 0 ? "var(--danger)" : "var(--success)" }}
                    />
                    <p className="text-[10px] leading-relaxed" style={{
                      color: (gstResult.ncri.violation_count ?? 0) > 0 ? "var(--danger)" : "var(--success)"
                    }}>
                      Atlas Ledger: <strong>{gstResult.ncri.project_name}</strong>
                      {" · "}NCRI Score: <strong>{gstResult.ncri.ncri_score}/100</strong>
                      {" · "}{gstResult.ncri.violation_count} violations
                    </p>
                  </div>
                )}

                <p className="text-[11px] text-[color:var(--muted)] leading-relaxed">{gstResult.trust_reason}</p>

                {gstResult.trust_level === "REJECTED" && (
                  <p className="text-[11px] font-semibold text-[color:var(--danger)]">
                    Bid submission is blocked for this contractor.
                  </p>
                )}
              </div>
            )}

            {/* Company name — auto-filled from registry */}
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--muted)] mb-1.5 block">
                Registered Company Name
                {gstResult?.live_verified && (
                  <span className="ml-2 text-[9px] text-[color:var(--success)] normal-case font-normal">
                    Auto-filled from government registry
                  </span>
                )}
              </label>
              <input
                className="input w-full"
                placeholder={gstResult ? "Auto-filled from GST registry" : "Verify GSTIN first to fetch name"}
                value={name}
                readOnly={!!gstResult?.live_verified}
                onChange={(e) => { if (!gstResult?.live_verified) setName(e.target.value); }}
                style={gstResult?.live_verified ? { background: "var(--surface-3)", cursor: "not-allowed" } : {}}
              />
              {gstResult?.live_verified && (
                <p className="text-[10px] text-[color:var(--success)] mt-1 flex items-center gap-1">
                  <CircleCheck className="w-3 h-3" /> Name sourced from government GST registry — cannot be edited
                </p>
              )}
              {gstResult && !gstResult.live_verified && gstResult.format_valid && (
                <p className="text-[10px] text-[color:var(--warning)] mt-1">
                  Registry offline — enter your registered company name manually.
                </p>
              )}
            </div>

            {/* Notice */}
            <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-[color:var(--primary-soft)] border border-[color:var(--primary)]/20">
              <ShieldCheck className="w-4 h-4 text-[color:var(--primary)] shrink-0 mt-0.5" />
              <p className="text-[11px] text-[color:var(--muted)] leading-relaxed">
                GSTIN verified.
                {" "}Contractor identity is sourced from the government registry — not self-reported.
                {" "}NCRI eligibility and violation history are automatically validated.
                {" "}Minimum NCRI required: <strong className="text-[color:var(--foreground)]">{tender.min_ncri_required}/100</strong>.
              </p>
            </div>
          </div>
        )}

        {/* Step 2: Technical Qualification */}
        {step === 2 && (
          <div className="space-y-4 fade-in">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-[color:var(--primary)]" />
              <h4 className="text-[12px] font-bold uppercase tracking-widest">Technical Qualification</h4>
            </div>

            <div>
              <label className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--muted)] mb-1.5 block">
                Years of Industry Experience <span className="text-[color:var(--danger)]">*</span>
              </label>
              <div className="relative">
                <input
                  className="input w-full pr-16"
                  type="number"
                  min="1"
                  max="100"
                  value={yearsExp}
                  onChange={(e) => setYearsExp(e.target.value)}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-[color:var(--muted)]">years</span>
              </div>
            </div>

            <div>
              <label className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--muted)] mb-2 block">
                Entity Classification <span className="text-[color:var(--danger)]">*</span>
              </label>
              <div className="grid grid-cols-2 gap-2.5">
                {[
                  { value: false, label: "Established Entity", sub: "Incorporated 2+ years ago" },
                  { value: true, label: "New Entity", sub: "Incorporated < 2 years ago" },
                ].map((opt) => (
                  <button
                    key={String(opt.value)}
                    onClick={() => setIsNew(opt.value)}
                    className={`text-left p-3 rounded-xl border transition-all ${
                      isNew === opt.value
                        ? "border-[color:var(--primary)] bg-[color:var(--primary-soft)]"
                        : "border-[color:var(--border)] hover:border-[color:var(--border-strong)]"
                    }`}
                  >
                    <p className="text-[12px] font-semibold" style={{ color: isNew === opt.value ? "var(--primary)" : undefined }}>
                      {opt.label}
                    </p>
                    <p className="text-[10px] text-[color:var(--muted)] mt-0.5">{opt.sub}</p>
                  </button>
                ))}
              </div>
            </div>

            {isNew && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-[color:var(--warning-soft)] border border-[color:var(--warning)]/25">
                <AlertTriangle className="w-3.5 h-3.5 text-[color:var(--warning)] shrink-0 mt-0.5" />
                <p className="text-[10px] text-[color:var(--warning)]">
                  New entity status adds +15 to your anomaly score and may reduce your bid ranking.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Step 3: Financial Bid */}
        {step === 3 && (
          <div className="space-y-4 fade-in">
            <div className="flex items-center gap-2 mb-2">
              <IndianRupee className="w-4 h-4 text-[color:var(--primary)]" />
              <h4 className="text-[12px] font-bold uppercase tracking-widest">Financial Bid</h4>
            </div>

            {/* Reference stats */}
            <div className="grid grid-cols-2 gap-2.5">
              <div className="surface-elev px-3 py-2.5 rounded-lg">
                <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)]">Estimated Value</p>
                <p className="text-[13px] font-bold text-[color:var(--primary)] mt-0.5">{formatCr(tender.estimated_value_cr)}</p>
              </div>
              <div className="surface-elev px-3 py-2.5 rounded-lg">
                <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)]">ALB Threshold (80%)</p>
                <p className="text-[13px] font-bold text-[color:var(--warning)] mt-0.5">
                  {formatCr(tender.estimated_value_cr * 0.80)}
                </p>
              </div>
            </div>

            <div>
              <label className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--muted)] mb-1.5 block">
                Your Quoted Price (in Crore INR) <span className="text-[color:var(--danger)]">*</span>
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-[color:var(--muted)] font-semibold">₹</span>
                <input
                  className="input w-full pl-8 text-lg font-bold tabular-nums"
                  type="number"
                  step="0.01"
                  min="1"
                  placeholder={String(Math.round(tender.estimated_value_cr * 0.95))}
                  value={bidAmount}
                  onChange={(e) => setBidAmount(e.target.value)}
                />
                <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[11px] text-[color:var(--muted)]">Crore</span>
              </div>

              {/* Live analysis */}
              {bidRatio !== null && (
                <div className="mt-3 space-y-2">
                  {/* Progress bar */}
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 rounded-full bg-[color:var(--surface-3)] overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${Math.min(bidRatio * 100, 100)}%`,
                          background: priceSeverity === "danger" ? "var(--danger)"
                            : priceSeverity === "warning" ? "var(--warning)" : "var(--success)",
                        }}
                      />
                    </div>
                    <span
                      className="text-[11px] font-bold tabular-nums w-12 text-right"
                      style={{
                        color: priceSeverity === "danger" ? "var(--danger)"
                          : priceSeverity === "warning" ? "var(--warning)" : "var(--success)",
                      }}
                    >
                      {(bidRatio * 100).toFixed(1)}%
                    </span>
                  </div>

                  {/* Flag preview */}
                  <div
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border text-[10px] font-semibold"
                    style={{
                      color: priceSeverity === "danger" ? "var(--danger)"
                        : priceSeverity === "warning" ? "var(--warning)" : "var(--success)",
                      borderColor: priceSeverity === "danger" ? "rgba(239,68,68,0.3)"
                        : priceSeverity === "warning" ? "rgba(245,158,11,0.3)" : "rgba(34,197,94,0.3)",
                      background: priceSeverity === "danger" ? "rgba(239,68,68,0.05)"
                        : priceSeverity === "warning" ? "rgba(245,158,11,0.05)" : "rgba(34,197,94,0.05)",
                    }}
                  >
                    {priceSeverity === "danger" && <><TrendingDown className="w-3 h-3" /> Abnormally Low Bid — will be flagged under ALB policy</>}
                    {priceSeverity === "warning" && <><AlertTriangle className="w-3 h-3" /> Suspiciously low — may attract scrutiny</>}
                    {priceSeverity === "good" && <><TrendingUp className="w-3 h-3" /> Price is within acceptable range</>}
                  </div>
                </div>
              )}
            </div>

            {/* Declaration */}
            <div className="surface p-4 rounded-xl space-y-3">
              <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)] font-semibold">
                Bidder Declaration
              </p>
              <p className="text-[11px] text-[color:var(--muted)] leading-relaxed">
                I hereby certify that the information provided is accurate and complete. I understand that my NCRI
                score has been auto-fetched from the Atlas Assurance governance ledger and cannot be disputed. I acknowledge
                that any false declaration is liable for blacklisting under applicable procurement rules.
              </p>
              <button
                onClick={() => setDeclared((v) => !v)}
                className={`flex items-center gap-2.5 w-full px-3 py-2.5 rounded-lg border transition-all text-[11px] font-semibold ${
                  declared
                    ? "border-[color:var(--success)] bg-[color:var(--success-soft)] text-[color:var(--success)]"
                    : "border-[color:var(--border)] text-[color:var(--muted)] hover:border-[color:var(--border-strong)]"
                }`}
              >
                <div
                  className="w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 transition-all"
                  style={{ borderColor: declared ? "var(--success)" : "var(--muted)", background: declared ? "var(--success)" : "transparent" }}
                >
                  {declared && <span className="text-white text-[8px]">✓</span>}
                </div>
                I accept the above declaration and submit this bid in good faith
              </button>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-[color:var(--danger-soft)] border border-[color:var(--danger)]/30">
                <AlertTriangle className="w-3.5 h-3.5 text-[color:var(--danger)] shrink-0" />
                <p className="text-[11px] text-[color:var(--danger)]">{error}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer nav */}
      <div className="px-6 py-4 border-t border-[color:var(--border)] flex gap-3 shrink-0">
        {step > 1 && (
          <button
            onClick={() => setStep((s) => (s - 1) as 1 | 2 | 3)}
            className="btn btn-secondary flex-1"
          >
            Back
          </button>
        )}
        {step < 3 ? (
          <button
            onClick={() => setStep((s) => (s + 1) as 2 | 3)}
            disabled={step === 1 ? !canStep1 : !canStep2}
            className="btn btn-primary flex-1"
          >
            Continue <ChevronRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
            className="btn btn-primary flex-1"
          >
            {submitting
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</>
              : <><Gavel className="w-4 h-4" /> Submit Bid</>
            }
          </button>
        )}
      </div>
    </div>
  );
}

// ── Tender Detail (main area) ──────────────────────────────────────────────

function TenderDetailPanel({ tenderId }: { tenderId: string }) {
  const [detail, setDetail]       = useState<TenderDetail | null>(null);
  const [loading, setLoading]     = useState(true);
  const [awardingBid, setAwardingBid] = useState<Bid | null>(null);
  const [awarding, setAwarding]   = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetchTenderDetail(tenderId).then(setDetail).catch(console.error).finally(() => setLoading(false));
  }, [tenderId]);

  useEffect(() => { load(); }, [load]);

  const handleAward = async () => {
    if (!awardingBid) return;
    setAwarding(true);
    try {
      await awardTenderContract(tenderId, awardingBid.contractor_id);
      setAwardingBid(null);
      load();
    } catch (e) { console.error(e); }
    finally { setAwarding(false); }
  };

  if (loading) return (
    <div className="flex-1 p-8 space-y-4">
      {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-16 w-full rounded-xl" />)}
    </div>
  );

  if (!detail) return <div className="p-8 text-[color:var(--muted)] text-sm">Failed to load tender details.</div>;

  const { tender, leaderboard, recommendation } = detail;
  const recId = recommendation.recommended_contractor_id;

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* ── Left: Tender info + leaderboard ── */}
      <div className="flex-1 overflow-y-auto scroll-thin">
        {/* Tender header */}
        <div className="px-8 py-6 border-b border-[color:var(--border)] bg-[color:var(--surface)]">
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3 mb-2 flex-wrap">
                <StatusChip status={tender.status} />
                <span className="text-[10px] font-mono text-[color:var(--muted-2)]">{tender.tender_id}</span>
              </div>
              <h2 className="text-xl font-bold leading-snug">{tender.project_name}</h2>
              <div className="flex items-center gap-4 mt-2 text-[11px] text-[color:var(--muted)] flex-wrap">
                <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{tender.location}</span>
                <span className="flex items-center gap-1">
                  <CalendarDays className="w-3 h-3" />
                  Deadline: {fmtDate(tender.deadline)}
                  {daysUntil(tender.deadline) >= 0 && (
                    <span className="ml-1" style={{
                      color: daysUntil(tender.deadline) <= 2 ? "var(--danger)" : daysUntil(tender.deadline) <= 5 ? "var(--warning)" : "var(--success)"
                    }}>({daysUntil(tender.deadline)}d left)</span>
                  )}
                </span>
                <span className="flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" />
                  Min NCRI: <strong style={{ color: ncriColor(tender.min_ncri_required) }}>{tender.min_ncri_required}</strong>
                </span>
              </div>
            </div>
            <div className="flex gap-3 flex-wrap">
              <div className="surface-elev px-4 py-3 rounded-xl text-center min-w-[100px]">
                <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)]">Estimated Value</p>
                <p className="text-lg font-black mt-1 text-[color:var(--primary)]">{formatCr(tender.estimated_value_cr)}</p>
              </div>
              <div className="surface-elev px-4 py-3 rounded-xl text-center min-w-[80px]">
                <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)]">Total Bids</p>
                <p className="text-lg font-black mt-1">{leaderboard.length}</p>
              </div>
            </div>
          </div>
          {tender.description && (
            <p className="text-[12px] text-[color:var(--muted)] mt-4 max-w-3xl leading-relaxed border-t border-[color:var(--border)] pt-4">
              {tender.description}
            </p>
          )}
          {/* Awarded notice */}
          {tender.status === "AWARDED" && (
            <div className="mt-4 flex items-center gap-3 p-4 rounded-xl bg-[color:var(--success-soft)] border border-[color:var(--success)]/30">
              <CheckCircle2 className="w-5 h-5 text-[color:var(--success)] shrink-0" />
              <div>
                <p className="text-[12px] font-bold text-[color:var(--success)]">Contract Awarded</p>
                <p className="text-[11px] text-[color:var(--muted)] mt-0.5">
                  Awarded to{" "}
                  <strong className="text-[color:var(--foreground)]">{tender.awarded_contractor_name}</strong>{" "}
                  at <strong className="text-[color:var(--success)]">{formatCr(tender.awarded_bid_cr ?? 0)}</strong>
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="p-8 space-y-6">
          {/* AI Recommendation */}
          <RecommendationBanner rec={recommendation} />

          {/* Bid Leaderboard Table */}
          <div>
            <h3 className="text-[11px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-3 flex items-center gap-2">
              <Gavel className="w-3.5 h-3.5" /> Bid Leaderboard
            </h3>
            <div className="surface rounded-xl overflow-hidden">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-[color:var(--border)]">
                    {["Rank", "Contractor", "NCRI Score", "Bid Amount", "Anomaly", "Action"].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-[9px] font-bold uppercase tracking-widest text-[color:var(--muted)] text-left"
                        style={{ textAlign: h === "Action" || h === "Anomaly" || h === "Bid Amount" ? "center" : "left" }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-10 text-center text-[color:var(--muted)] text-sm">
                        No bids submitted yet. Be the first to bid.
                      </td>
                    </tr>
                  ) : (
                    leaderboard.map((bid) => (
                      <BidTableRow
                        key={bid.bid_id}
                        bid={bid}
                        isRecommended={bid.contractor_id === recId && tender.status === "OPEN"}
                        onAward={setAwardingBid}
                        awarding={awarding}
                        tenderStatus={tender.status}
                      />
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* ── Right: Bid submission panel ── */}
      {tender.status === "OPEN" && (
        <aside className="w-80 shrink-0 border-l border-[color:var(--border)] bg-[color:var(--surface)] flex flex-col overflow-hidden">
          <BidSubmissionPanel
            tenderId={tenderId}
            tender={tender}
            onBidSubmitted={load}
          />
        </aside>
      )}

      {/* Award modal */}
      {awardingBid && (
        <AwardModal
          bid={awardingBid}
          tender={tender}
          onConfirm={handleAward}
          onCancel={() => setAwardingBid(null)}
          loading={awarding}
        />
      )}
    </div>
  );
}

// ── Main TenderRegistry ────────────────────────────────────────────────────

export function TenderRegistry() {
  const [tenders, setTenders]   = useState<Tender[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    fetchTenders()
      .then((d) => {
        setTenders(d.tenders);
        if (d.tenders.length > 0) {
          const open = d.tenders.find((t) => t.status === "OPEN");
          setSelectedId((open ?? d.tenders[0]).tender_id);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const openCount    = tenders.filter((t) => t.status === "OPEN").length;
  const awardedCount = tenders.filter((t) => t.status === "AWARDED").length;
  const totalBids    = tenders.reduce((s, t) => s + (t.bid_count ?? 0), 0);

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">

      {/* Left Rail */}
      <aside className="w-[17rem] shrink-0 border-r border-[color:var(--border)] bg-[color:var(--surface)] flex flex-col overflow-hidden">
        {/* Rail header */}
        <div className="px-4 pt-5 pb-4 border-b border-[color:var(--border)] shrink-0">
          <div className="flex items-center gap-2 mb-0.5">
            <div className="w-7 h-7 rounded-lg bg-[color:var(--primary-soft)] flex items-center justify-center">
              <Gavel className="w-3.5 h-3.5 text-[color:var(--primary)]" />
            </div>
            <span className="text-[13px] font-bold tracking-tight">Tender Registry</span>
          </div>
          <p className="text-[10px] text-[color:var(--muted)] ml-9">Evidence-driven procurement</p>
          <div className="mt-3 grid grid-cols-3 gap-1.5 text-center">
            {[
              { label: "Open", value: openCount, color: "var(--success)" },
              { label: "Awarded", value: awardedCount, color: "var(--primary)" },
              { label: "Bids", value: totalBids, color: "var(--muted)" },
            ].map((s) => (
              <div key={s.label} className="surface-elev py-2 rounded-lg">
                <p className="text-[13px] font-bold tabular-nums" style={{ color: s.color }}>{s.value}</p>
                <p className="text-[9px] text-[color:var(--muted)] uppercase tracking-wide">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Tender list */}
        <div className="flex-1 overflow-y-auto scroll-thin p-3 space-y-2">
          {loading ? (
            [1, 2, 3].map((i) => <div key={i} className="skeleton h-24 w-full rounded-xl" />)
          ) : tenders.length === 0 ? (
            <p className="text-xs text-center text-[color:var(--muted)] py-8">No tenders found.</p>
          ) : (
            tenders.map((t) => (
              <TenderRailCard
                key={t.tender_id}
                tender={t}
                selected={selectedId === t.tender_id}
                onSelect={() => setSelectedId(t.tender_id)}
              />
            ))
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 min-w-0 flex-col overflow-hidden">
        {/* Main header */}
        <header className="px-8 py-3.5 border-b border-[color:var(--border)] bg-[color:var(--surface)] flex items-center justify-between gap-4 shrink-0">
          <div>
            <h1 className="text-[14px] font-bold">Procurement Intelligence</h1>
            <p className="text-[11px] text-[color:var(--muted)] mt-0.5">
              Atlas continuously updates contractor eligibility using assurance findings, violation history, and NCRI reliability scores.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[color:var(--surface-2)] border border-[color:var(--border)] text-[10px]">
              <ShieldCheck className="w-3.5 h-3.5 text-[color:var(--success)]" />
              <span className="text-[color:var(--muted)]">Auto-reject NCRI below threshold</span>
            </div>
          </div>
        </header>

        {/* Detail panel */}
        {!selectedId ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-sm">
              <div className="w-14 h-14 rounded-2xl bg-[color:var(--surface-2)] border border-[color:var(--border)] flex items-center justify-center mx-auto mb-4">
                <Gavel className="w-6 h-6 text-[color:var(--muted)]" />
              </div>
              <h2 className="text-base font-semibold">Select a Tender</h2>
              <p className="text-sm text-[color:var(--muted)] mt-1.5 leading-relaxed">
                Choose a tender from the registry to view the bid leaderboard, AI recommendation, and submit a live bid.
              </p>
            </div>
          </div>
        ) : (
          <TenderDetailPanel key={selectedId} tenderId={selectedId} />
        )}
      </div>
    </div>
  );
}
