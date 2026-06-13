"use client";

import { useEffect, useRef, useState } from "react";
import {
  FileText,
  Upload,
  Loader2,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  FileWarning,
  Search,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Lightbulb,
  TrendingUp,
  RotateCcw,
  Eye,
  EyeOff,
} from "lucide-react";
import {
  analyzeDpr,
  fetchLatestCycle,
  fetchCycles,
  type Investigation,
  type DprScanResult,
  type AssuranceCycle,
  type ContextAdjustment,
} from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";

// ── Severity / Confidence colour mapping ─────────────────────────────────────

const SEV_STYLES: Record<
  string,
  { border: string; bg: string; badge: string; badgeBg: string; dot: string }
> = {
  HIGH: {
    border: "border-[color:var(--danger)]/30",
    bg: "bg-[color:var(--danger)]/5",
    badge: "text-[color:var(--danger)]",
    badgeBg: "bg-[color:var(--danger)]/10",
    dot: "bg-[color:var(--danger)]",
  },
  MEDIUM: {
    border: "border-[color:var(--warning)]/30",
    bg: "bg-[color:var(--warning)]/5",
    badge: "text-[color:var(--warning)]",
    badgeBg: "bg-[color:var(--warning)]/10",
    dot: "bg-[color:var(--warning)]",
  },
  LOW: {
    border: "border-[color:var(--border)]",
    bg: "bg-[color:var(--surface-2)]",
    badge: "text-[color:var(--muted)]",
    badgeBg: "bg-[color:var(--surface-3)]",
    dot: "bg-[color:var(--muted)]",
  },
};

const CONF_LABEL: Record<string, string> = {
  HIGH: "High Confidence",
  MEDIUM: "Medium Confidence",
  LOW: "Low Confidence",
};

// ── Helper: format cycle_id → "Cycle #1" ────────────────────────────────────

function formatCycleId(id: string): string {
  const num = parseInt(id.replace(/^cycle-/i, ""), 10);
  return isNaN(num) ? id : `Cycle #${num}`;
}

// ── Accordion Evidence Item ───────────────────────────────────────────────────

function EvidenceLockerItem({
  evidence,
  index,
  openIndex,
  onToggle,
}: {
  evidence: string;
  index: number;
  openIndex: number | null;
  onToggle: (i: number) => void;
}) {
  const parts = evidence.split(" - ");
  const title   = parts[0];
  const excerpt = parts.slice(1).join(" - ");
  const isOpen  = openIndex === index;

  return (
    <li className="border-b border-[color:var(--border)] last:border-b-0">
      <button
        className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-[color:var(--surface-2)]/50 transition-colors"
        onClick={() => onToggle(index)}
      >
        <AlertTriangle className="w-3.5 h-3.5 text-[color:var(--danger)] shrink-0" />
        <span className="flex-1 text-xs font-semibold text-[color:var(--danger)] truncate">{title}</span>
        <span className="shrink-0 text-[color:var(--muted)]">
          {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </span>
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="evidence-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-4">
              <div className="bg-[color:var(--surface-2)] border border-[color:var(--border)] rounded-lg p-3">
                <p className="text-[11px] font-mono text-[color:var(--muted)] leading-relaxed italic">
                  {excerpt || "No excerpt available."}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

// ── Investigation Card (all collapsed by default) ────────────────────────────

function InvestigationCard({ inv, index, openIndex, onToggle }: {
  inv: Investigation;
  index: number;
  openIndex: number | null;
  onToggle: (i: number) => void;
}) {
  const sev   = SEV_STYLES[inv.severity] ?? SEV_STYLES.LOW;
  const isOpen = openIndex === index;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={`rounded-xl border ${sev.border} ${sev.bg} overflow-hidden`}
    >
      <button
        className="w-full flex items-center gap-3 px-5 py-4 text-left"
        onClick={() => onToggle(index)}
      >
        <span className={`w-2 h-2 shrink-0 rounded-full ${sev.dot}`} aria-hidden="true" />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold tracking-tight">{inv.title}</span>
            <span className={`inline-flex px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-widest ${sev.badge} ${sev.badgeBg}`}>
              {inv.severity}
            </span>
            <span className="inline-flex px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[color:var(--surface-3)] text-[color:var(--muted)]">
              {CONF_LABEL[inv.confidence]}
            </span>
            {!isOpen && (
              <span className="text-[10px] text-[color:var(--muted)] ml-auto">
                {inv.supporting_findings.length} finding{inv.supporting_findings.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          {!isOpen && (
            <p className="text-[11px] text-[color:var(--muted)] leading-relaxed mt-1 line-clamp-1">
              {inv.summary}
            </p>
          )}
        </div>
        <span className="shrink-0 text-[color:var(--muted)]">
          {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-4 border-t border-[color:var(--border)]">
              <p className="text-[12px] text-[color:var(--muted)] leading-relaxed pt-4">{inv.summary}</p>

              {inv.supporting_findings.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <ClipboardList className="w-3 h-3 text-[color:var(--muted)]" />
                    <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">
                      Supporting Findings
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {inv.supporting_findings.map((f, i) => (
                      <span
                        key={i}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${sev.badge} ${sev.badgeBg} ${sev.border}`}
                      >
                        <AlertTriangle className="w-2.5 h-2.5 shrink-0" />
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {inv.evidence.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Search className="w-3 h-3 text-[color:var(--muted)]" />
                    <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">
                      Source Evidence
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    {inv.evidence.map((e, i) => {
                      const parts   = e.split(" - ");
                      const label   = parts[0];
                      const excerpt = parts.slice(1).join(" - ");
                      return (
                        <div key={i} className="bg-[color:var(--surface-2)] border border-[color:var(--border)] rounded-lg px-3 py-2">
                          <p className="text-[9px] font-semibold text-[color:var(--danger)] mb-0.5">{label}</p>
                          <p className="text-[10px] font-mono text-[color:var(--muted)] leading-relaxed italic">{excerpt}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {inv.recommendations.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Lightbulb className="w-3 h-3 text-[color:var(--warning)]" />
                    <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">
                      Recommendations
                    </p>
                  </div>
                  <ol className="space-y-1.5">
                    {inv.recommendations.map((rec, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="shrink-0 w-4 h-4 rounded-full bg-[color:var(--surface-3)] border border-[color:var(--border)] flex items-center justify-center text-[8px] font-bold text-[color:var(--muted)]">
                          {i + 1}
                        </span>
                        <p className="text-[11px] text-[color:var(--foreground)] leading-relaxed">{rec}</p>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Result display type ────────────────────────────────────────────────────────

export type ResultDisplay = DprScanResult & { cycle_id?: string };

// Convert an AssuranceCycle → ResultDisplay
function cycleToResult(c: AssuranceCycle): ResultDisplay {
  const a = c.dpr_analysis;
  return {
    cycle_id: c.cycle_id,
    department: "Infrastructure / Government Project",
    risk_level: a.verdict === "HIGH_RISK" ? "HIGH_RISK" : "LOW_RISK",
    approval_probability: 100 - a.risk_score,
    rejection_probability: a.risk_score,
    critical_evidence_found: a.findings,
    findings: a.findings,
    investigations: a.investigations,
    extracted_ml_features: {
      budget_cr: a.budget_cr,
      time_gap_months: a.time_gap_months,
    },
    context: c.context ?? null,
    cross_evidence: c.cross_evidence ?? null,
    unified_risk: c.unified_risk ?? null,
    governance: c.governance ?? null,
  };
}

// ── Props ─────────────────────────────────────────────────────────────────────

type Props = {
  projectId: string | null;
  onResult: (result: ResultDisplay | null) => void;
  onCycleCount: (count: number) => void;
  /** Called by the Reset button in page.tsx — triggers hydration reset */
  externalReset?: number;
};

// ── Main Component ────────────────────────────────────────────────────────────

export function FraudAnalytics({ projectId, onResult, onCycleCount, externalReset }: Props) {
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult]           = useState<ResultDisplay | null>(null);
  const [error, setError]             = useState<string | null>(null);
  const [scanStep, setScanStep]       = useState(0);
  const [cycleSource, setCycleSource] = useState<"upload" | "twin" | null>(null);
  const [hydratingCycle, setHydratingCycle] = useState(false);
  const [noCycles, setNoCycles]       = useState(false);
  const [cycleCount, setCycleCount]   = useState(0);

  // Detail expanded state
  const [showDetails, setShowDetails]       = useState(false);
  const [openInvIndex, setOpenInvIndex]     = useState<number | null>(null);
  const [openEvidIndex, setOpenEvidIndex]   = useState<number | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // Emit result up whenever it changes
  useEffect(() => { onResult(result); }, [result]);
  useEffect(() => { onCycleCount(cycleCount); }, [cycleCount]);

  // ── Load / hydrate ─────────────────────────────────────────────────────────
  const loadCycles = (pid: string) => {
    setHydratingCycle(true);
    Promise.allSettled([
      fetchCycles(pid),
      fetchLatestCycle(pid),
    ]).then(([cyclesResult, latestResult]) => {
      const count = cyclesResult.status === "fulfilled" ? cyclesResult.value.length : 0;
      setCycleCount(count);
      if (latestResult.status === "fulfilled") {
        setResult(cycleToResult(latestResult.value));
        setCycleSource("twin");
        setNoCycles(false);
      } else {
        setResult(null);
        setNoCycles(true);
      }
    }).finally(() => setHydratingCycle(false));
  };

  // ── Reset + hydrate when projectId changes ─────────────────────────────────
  useEffect(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setResult(null);
    setError(null);
    setScanStep(0);
    setIsUploading(false);
    setCycleSource(null);
    setNoCycles(false);
    setCycleCount(0);
    setShowDetails(false);
    setOpenInvIndex(null);
    setOpenEvidIndex(null);

    if (!projectId) return;
    loadCycles(projectId);
  }, [projectId]);

  // ── External reset trigger (from page.tsx after DELETE) ───────────────────
  useEffect(() => {
    if (externalReset === undefined || externalReset === 0) return;
    // Reset to blank upload state
    setResult(null);
    setError(null);
    setCycleSource(null);
    setNoCycles(true);
    setCycleCount(0);
    setShowDetails(false);
    setOpenInvIndex(null);
    setOpenEvidIndex(null);
  }, [externalReset]);

  // ── Upload handler ─────────────────────────────────────────────────────────
  const handle = async (file: File) => {
    if (!projectId) {
      setError("Select a project from the sidebar before uploading a DPR.");
      return;
    }

    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsUploading(true);
    setError(null);
    setResult(null);
    setNoCycles(false);
    setShowDetails(false);
    setOpenInvIndex(null);
    setOpenEvidIndex(null);
    setScanStep(1);

    const interval          = setInterval(() => setScanStep((s) => (s < 4 ? s + 1 : s)), 3000);
    const uploadedForProject = projectId;

    try {
      const res = await analyzeDpr(file, projectId, controller.signal);
      if (uploadedForProject !== projectId) return;
      setResult(res as ResultDisplay);
      setCycleSource("upload");
      setCycleCount((n) => n + 1);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") return;
      if (uploadedForProject !== projectId) return;
      setError(String(e));
    } finally {
      clearInterval(interval);
      setIsUploading(false);
      setScanStep(6);
    }
  };

  const nextCycleLabel = `Cycle #${cycleCount + 1}`;

  const SCAN_STEPS = [
    "Initializing Atlas Intelligence engine...",
    "Extracting structured content from document...",
    "Running budget & timeline heuristics...",
    "Semantic evidence search across violation database...",
    "Multi-variate risk classification...",
    `Persisting ${nextCycleLabel} to Assurance Record...`,
    "Analysis complete",
  ];

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5">
      {/* ── Cycle hydration skeleton ── */}
      {hydratingCycle && (
        <div className="space-y-3 mt-2">
          <div className="flex items-center gap-3 py-3 text-[color:var(--muted)]">
            <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            <span className="text-sm">Loading assurance record…</span>
          </div>
          <div className="skeleton h-10 rounded-xl w-3/4" />
          <div className="skeleton h-24 rounded-xl" />
        </div>
      )}

      {/* ── No-project guard ── */}
      {!hydratingCycle && !projectId && (
        <div className="mt-4 rounded-xl bg-[color:var(--warning)]/10 border border-[color:var(--warning)]/30 px-4 py-3 text-sm text-[color:var(--warning)] flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          Select a project from the sidebar to enable DPR upload.
        </div>
      )}

      {/* ── No cycles yet ── */}
      {!hydratingCycle && projectId && noCycles && !result && !isUploading && !error && (
        <div className="mt-2 mb-3 rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-2)] px-5 py-4">
          <p className="text-sm font-semibold text-[color:var(--foreground)]">No Assurance History Exists Yet.</p>
          <p className="text-xs text-[color:var(--muted)] mt-1">Upload a DPR to create Assurance {nextCycleLabel}.</p>
        </div>
      )}

      {/* ── Upload zone ── */}
      {!hydratingCycle && !isUploading && !result && !error && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-2">
          <label className={!projectId ? "pointer-events-none opacity-50 block" : "block"}>
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && handle(e.target.files[0])}
            />
            <div className="group relative border-2 border-dashed border-[color:var(--border-strong)] rounded-2xl py-12 flex flex-col items-center justify-center cursor-pointer hover:border-[color:var(--primary)] hover:bg-[color:var(--primary)]/5 transition-all overflow-hidden bg-[color:var(--surface-2)]">
              <div className="absolute inset-0 bg-gradient-to-b from-transparent to-[color:var(--primary)]/10 opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="w-14 h-14 rounded-full bg-[color:var(--surface)] border border-[color:var(--border)] shadow-md flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                <Upload className="w-7 h-7 text-[color:var(--primary)]" />
              </div>
              <p className="text-sm font-bold text-[color:var(--foreground)]">Drag & Drop DPR Document</p>
              <p className="text-xs text-[color:var(--muted)] mt-1.5 font-mono">PDF · Max 250MB</p>
              {projectId && (
                <p className="text-xs text-[color:var(--primary)] font-semibold mt-2">
                  Creates Assurance Record · {nextCycleLabel}
                </p>
              )}
            </div>
          </label>
        </motion.div>
      )}

      {/* ── Scanning animation ── */}
      {isUploading && (
        <div className="py-14 flex flex-col items-center justify-center text-center">
          <div className="relative w-20 h-20 flex items-center justify-center">
            <div className="absolute inset-0 border-4 border-[color:var(--primary)]/20 rounded-full" />
            <div className="absolute inset-0 border-4 border-[color:var(--primary)] border-t-transparent rounded-full animate-spin" />
            <Search className="w-7 h-7 text-[color:var(--primary)] animate-pulse" />
          </div>
          <h4 className="text-base font-bold mt-5 mb-1.5">Analyzing DPR…</h4>
          <div className="h-5 overflow-hidden">
            <AnimatePresence mode="wait">
              <motion.p
                key={scanStep}
                initial={{ y: 16, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: -16, opacity: 0 }}
                className="text-xs font-mono text-[color:var(--muted)]"
              >
                {SCAN_STEPS[Math.min(scanStep, SCAN_STEPS.length - 1)]}
              </motion.p>
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* ── Error state ── */}
      {error && (
        <div className="rounded-xl bg-[color:var(--danger)]/10 border border-[color:var(--danger)]/30 p-5 flex items-start gap-4">
          <FileWarning className="w-5 h-5 text-[color:var(--danger)] shrink-0 mt-0.5" />
          <div>
            <p className="font-bold text-[color:var(--danger)]">Analysis Failed</p>
            <p className="text-xs text-[color:var(--danger)]/80 mt-1 font-mono">{error}</p>
            <button
              onClick={() => setError(null)}
              className="btn mt-3 bg-[color:var(--surface)] hover:bg-[color:var(--surface-2)] text-[color:var(--foreground)] border border-[color:var(--border)] text-xs"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* ── Results ── */}
      {result && (
        <motion.div
          initial={{ opacity: 0, scale: 0.99 }}
          animate={{ opacity: 1, scale: 1 }}
          className="space-y-5"
        >
          {/* Provenance banner */}
          {result.cycle_id && (
            <div className={`flex items-center gap-2.5 rounded-xl px-4 py-2.5 border text-xs font-semibold ${
              cycleSource === "twin"
                ? "bg-[color:var(--primary)]/5 border-[color:var(--primary)]/20 text-[color:var(--primary)]"
                : "bg-[color:var(--success)]/10 border-[color:var(--success)]/30 text-[color:var(--success)]"
            }`}>
              {cycleSource === "twin"
                ? <RotateCcw className="w-3.5 h-3.5 shrink-0" />
                : <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              }
              {cycleSource === "twin"
                ? `${formatCycleId(result.cycle_id)} restored`
                : `${formatCycleId(result.cycle_id)} saved to Assurance Record`}
            </div>
          )}

          {/* ── SUMMARY CARD (always visible) ──────────────────────────── */}
          <div className={`rounded-2xl border p-5 relative overflow-hidden ${
            result.risk_level === "HIGH_RISK"
              ? "bg-[color:var(--danger)]/5 border-[color:var(--danger)]/30"
              : "bg-[color:var(--success)]/5 border-[color:var(--success)]/30"
          }`}>
            <div className={`absolute top-0 right-0 w-48 h-48 rounded-full blur-[80px] opacity-15 pointer-events-none ${
              result.risk_level === "HIGH_RISK" ? "bg-[color:var(--danger)]" : "bg-[color:var(--success)]"
            }`} />
            <div className="relative z-10 flex items-center gap-6 flex-wrap">
              {/* Mini circle */}
              <div className="relative flex-shrink-0">
                <svg width="80" height="80" viewBox="0 0 80 80" className="-rotate-90">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="currentColor" strokeWidth="8"
                    className="text-[color:var(--surface-2)]" />
                  <motion.circle
                    initial={{ strokeDasharray: "0 300" }}
                    animate={{ strokeDasharray: `${(result.rejection_probability / 100) * 213.6} 300` }}
                    transition={{ duration: 1.2, ease: "easeOut" }}
                    cx="40" cy="40" r="34" fill="none" stroke="currentColor" strokeWidth="8"
                    className={result.risk_level === "HIGH_RISK" ? "text-[color:var(--danger)]" : "text-[color:var(--success)]"}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-lg font-black">{result.rejection_probability.toFixed(0)}%</span>
                  <span className="text-[8px] uppercase tracking-wider text-[color:var(--muted)]">Risk</span>
                </div>
              </div>

              {/* Verdict */}
              <div className="flex-1 min-w-0">
                <h3 className={`text-2xl font-black tracking-tight ${
                  result.risk_level === "HIGH_RISK" ? "text-[color:var(--danger)]" : "text-[color:var(--success)]"
                }`}>
                  {result.risk_level.replace("_", " ")}
                </h3>
                <p className="text-xs text-[color:var(--muted)] mt-0.5">
                  {result.risk_level === "HIGH_RISK"
                    ? "Critical violations or impossible budget physics detected."
                    : "Document verified clean. No fraud heuristics triggered."}
                </p>
              </div>

              {/* Key metrics */}
              <div className="flex gap-4 flex-shrink-0">
                <MetricPill label="Budget" value={`₹${result.extracted_ml_features.budget_cr.toLocaleString()} Cr`} />
                <MetricPill label="Delay" value={`${result.extracted_ml_features.time_gap_months}mo`} />
                <MetricPill
                  label="Findings"
                  value={`${result.critical_evidence_found.length}`}
                  tone={result.critical_evidence_found.length > 0 ? "danger" : undefined}
                />
              </div>
            </div>

            {/* Context Adjustment inline */}
            {result.context && result.context.budget_adjustment_pct !== 0 && (
              <div className="mt-4 pt-3 border-t border-[color:var(--border)] flex items-center gap-4 flex-wrap">
                <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">Context Adjusted</p>
                <div className="flex items-baseline gap-2 text-xs">
                  <span className="text-[color:var(--muted)] line-through font-mono">
                    ₹{result.context.original_budget_cr.toLocaleString(undefined, { maximumFractionDigits: 1 })} Cr
                  </span>
                  <span className="font-bold font-mono">
                    ₹{result.context.adjusted_budget_cr.toLocaleString(undefined, { maximumFractionDigits: 1 })} Cr
                  </span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    result.context.budget_adjustment_pct > 0
                      ? "bg-[color:var(--warning)]/10 text-[color:var(--warning)]"
                      : "bg-[color:var(--success)]/10 text-[color:var(--success)]"
                  }`}>
                    {result.context.budget_adjustment_pct > 0 ? "+" : ""}{result.context.budget_adjustment_pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            )}

            {/* Expand / collapse button */}
            {(result.investigations?.length > 0 || result.critical_evidence_found.length > 0) && (
              <button
                onClick={() => setShowDetails((v) => !v)}
                className={`mt-4 flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors ${
                  showDetails
                    ? "bg-[color:var(--surface)] border-[color:var(--border)] text-[color:var(--muted)]"
                    : "bg-[color:var(--surface)] border-[color:var(--border)] hover:border-[color:var(--border-strong)] text-[color:var(--foreground)]"
                }`}
              >
                {showDetails
                  ? <><EyeOff className="w-3.5 h-3.5" /> Hide Investigation Details</>
                  : <><Eye className="w-3.5 h-3.5" /> View Investigation Details</>
                }
              </button>
            )}
          </div>

          {/* ── DETAILS (collapsible) ────────────────────────────────────── */}
          <AnimatePresence>
            {showDetails && (
              <motion.div
                key="details"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
                className="space-y-5"
              >
                {/* Investigation Clusters */}
                {result.investigations && result.investigations.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2.5 mb-3">
                      <TrendingUp className="w-4 h-4 text-[color:var(--primary)]" />
                      <h3 className="text-sm font-bold tracking-tight">Risk Investigation Clusters</h3>
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-[color:var(--primary)]/10 text-[color:var(--primary)]">
                        {result.investigations.length}
                      </span>
                    </div>
                    <div className="space-y-2.5">
                      {result.investigations.map((inv, i) => (
                        <InvestigationCard
                          key={i}
                          inv={inv}
                          index={i}
                          openIndex={openInvIndex}
                          onToggle={(idx) => setOpenInvIndex((prev) => prev === idx ? null : idx)}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Evidence Locker — accordion */}
                <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] overflow-hidden">
                  <div className="bg-[color:var(--surface-2)] px-5 py-3.5 border-b border-[color:var(--border)] flex items-center gap-2.5">
                    <ShieldAlert className="w-4 h-4 text-[color:var(--muted)]" />
                    <h3 className="text-sm font-bold tracking-tight">Evidence Locker</h3>
                    {result.critical_evidence_found.length > 0 && (
                      <span className="ml-auto text-[10px] font-semibold text-[color:var(--muted)]">
                        {result.critical_evidence_found.length} finding{result.critical_evidence_found.length !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                  {result.critical_evidence_found.length === 0 ? (
                    <div className="p-6 text-center flex flex-col items-center">
                      <CheckCircle2 className="w-10 h-10 text-[color:var(--success)]/50 mb-2" />
                      <p className="font-semibold text-sm text-[color:var(--foreground)]">No Legal Risks Found</p>
                      <p className="text-xs text-[color:var(--muted)] mt-1">
                        The semantic search returned zero matches for fraudulent clauses.
                      </p>
                    </div>
                  ) : (
                    <ul>
                      {result.critical_evidence_found.map((evidence, i) => (
                        <EvidenceLockerItem
                          key={i}
                          evidence={evidence}
                          index={i}
                          openIndex={openEvidIndex}
                          onToggle={(idx) => setOpenEvidIndex((prev) => prev === idx ? null : idx)}
                        />
                      ))}
                    </ul>
                  )}
                </div>

                {/* Cross-Evidence Intelligence */}
                {result.cross_evidence && result.cross_evidence.length > 0 && (
                  <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] overflow-hidden">
                    <div className="bg-[color:var(--surface-2)] px-5 py-3.5 border-b border-[color:var(--border)] flex items-center gap-2.5">
                      <TrendingUp className="w-4 h-4 text-[color:var(--danger)]" />
                      <h3 className="text-sm font-bold tracking-tight">Cross-Evidence Intelligence</h3>
                      <span className="ml-auto inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-[color:var(--danger)]/10 text-[color:var(--danger)]">
                        {result.cross_evidence.length} corroborated
                      </span>
                    </div>
                    <div className="divide-y divide-[color:var(--border)]">
                      {result.cross_evidence.map((finding, idx) => (
                        <div key={idx} className="p-5">
                          <div className="flex flex-wrap items-start gap-2 mb-2">
                            <div className="flex-1 min-w-0">
                              <p className="font-semibold text-xs leading-tight">{finding.title}</p>
                              {finding.supporting_modules.length > 0 && (
                                <div className="flex gap-1 flex-wrap mt-1">
                                  {finding.supporting_modules.map((mod, mi) => (
                                    <span key={mi} className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[color:var(--surface-2)] border border-[color:var(--border)] text-[color:var(--muted)]">
                                      {mod}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                            <span className={`shrink-0 text-[9px] font-black px-2 py-0.5 rounded ${
                              finding.severity === "CRITICAL" || finding.severity === "HIGH"
                                ? "bg-[color:var(--danger)]/10 text-[color:var(--danger)]"
                                : finding.severity === "MEDIUM"
                                ? "bg-[color:var(--warning)]/10 text-[color:var(--warning)]"
                                : "bg-[color:var(--muted)]/10 text-[color:var(--muted)]"
                            }`}>
                              {finding.severity}
                            </span>
                          </div>
                          <p className="text-xs text-[color:var(--muted)] leading-relaxed">{finding.summary}</p>
                          {finding.recommendations.length > 0 && (
                            <ul className="mt-3 space-y-1">
                              {finding.recommendations.map((rec, ri) => (
                                <li key={ri} className="text-[10px] text-[color:var(--muted)] flex items-start gap-1.5">
                                  <span className="shrink-0 mt-1 w-1 h-1 rounded-full bg-[color:var(--danger)]/60" />
                                  {rec}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}

// ── Metric Pill ───────────────────────────────────────────────────────────────

function MetricPill({ label, value, tone }: { label: string; value: string; tone?: "danger" }) {
  return (
    <div className="text-center">
      <p className="text-[9px] uppercase tracking-widest text-[color:var(--muted)]">{label}</p>
      <p className={`text-sm font-black metric-value mt-0.5 ${tone === "danger" ? "text-[color:var(--danger)]" : "text-[color:var(--foreground)]"}`}>
        {value}
      </p>
    </div>
  );
}
