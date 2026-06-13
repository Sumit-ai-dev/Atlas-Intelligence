"use client";

import { useEffect, useState } from "react";
import {
  Satellite,
  FileText,
  Shield,
  SearchCode,
  ShieldCheck,
  ExternalLink,
  AlertTriangle,
  CheckCircle2,
  Activity,
  BarChart3,
  Layers,
  ChevronRight,
  FileSpreadsheet,
  Printer,
  Eye,
  ClipboardList,
  Loader2,
  Download,
  Trash2,
  X,
} from "lucide-react";
import { GovernanceEventsProvider } from "@/lib/governanceEvents";
import { MountedTab } from "@/components/MountedTab";
import { ProjectsRail } from "@/components/ProjectsRail";
import { SatelliteView } from "@/components/SatelliteView";
import { FraudAnalytics, type ResultDisplay } from "@/components/FraudAnalytics";
import { SiteGuard } from "@/components/SiteGuard";
import { TruthLens } from "@/components/TruthLens";
import { ContractorTrust } from "@/components/ContractorTrust";
import { TenderRegistry } from "@/components/TenderRegistry";
import { fetchAlerts, SatelliteAlert, API_BASE, deleteAssuranceHistory } from "@/lib/api";

// ── Tab definitions ───────────────────────────────────────────────────────────

type EvidenceTab = "dpr" | "satellite" | "ppe" | "forensics" | "governance";

const EVIDENCE_TABS: { key: EvidenceTab; label: string; icon: typeof Satellite }[] = [
  { key: "dpr",        label: "Documents",  icon: FileText    },
  { key: "satellite",  label: "Satellite",  icon: Satellite   },
  { key: "ppe",        label: "Safety",     icon: Shield      },
  { key: "forensics",  label: "Authenticity", icon: SearchCode  },
  { key: "governance", label: "Contractor", icon: ShieldCheck },
];

// ── Status maps ───────────────────────────────────────────────────────────────

const STATUS_TONE: Record<string, { chip: string; label: string }> = {
  GHOST_ALERT:         { chip: "chip-danger",  label: "Ghost Alert"         },
  LAG_WARNING:         { chip: "chip-warning", label: "Lagging Behind"      },
  UNREPORTED_PROGRESS: { chip: "chip-info",    label: "Unreported Progress" },
  NORMAL:              { chip: "chip-success", label: "On Track"            },
  AWAITING_DPR:        { chip: "chip-muted",   label: "Awaiting DPR"       },
  AWAITING_SCAN:       { chip: "chip-muted",   label: "Awaiting Scan"      },
};

// ── Assurance Lifecycle stages ────────────────────────────────────────────────

type StageStatus = "done" | "active" | "pending";

type LifecycleStage = {
  key: string;
  label: string;
  icon: typeof Activity;
  getStatus: (alert: SatelliteAlert, result: ResultDisplay | null) => StageStatus;
};

const LIFECYCLE_STAGES: LifecycleStage[] = [
  {
    key: "baseline",
    label: "DPR",
    icon: FileText,
    getStatus: (_a, r) => (r ? "done" : "pending"),
  },
  {
    key: "satellite",
    label: "Satellite",
    icon: Satellite,
    getStatus: (a) => (a.satellite_actual_pct != null ? "done" : "active"),
  },
  {
    key: "cross",
    label: "Correlation",
    icon: Layers,
    getStatus: (_a, r) =>
      r?.cross_evidence && r.cross_evidence.length > 0 ? "done" : r ? "active" : "pending",
  },
  {
    key: "risk",
    label: "Risk",
    icon: BarChart3,
    getStatus: (_a, r) => (r?.unified_risk ? "done" : r ? "active" : "pending"),
  },
  {
    key: "governance",
    label: "Governance",
    icon: ShieldCheck,
    getStatus: (_a, r) => {
      if (!r?.governance) return "pending";
      return r.governance.status === "PENDING_REVIEW" ? "active" : "done";
    },
  },
  {
    key: "report",
    label: "Report",
    icon: FileSpreadsheet,
    getStatus: (_a, r) =>
      r?.cycle_id && r?.governance && r.governance.status !== "PENDING_REVIEW" ? "done" : r?.cycle_id ? "active" : "pending",
  },
];

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [showTenders, setShowTenders]     = useState(false);
  const [selected, setSelected]           = useState<string | null>(null);
  const [evidenceTab, setEvidenceTab]     = useState<EvidenceTab>("dpr");
  const [alerts, setAlerts]               = useState<SatelliteAlert[]>([]);
  const [backendOk, setBackendOk]         = useState<boolean | null>(null);

  // Lifted state from FraudAnalytics
  const [dprResult, setDprResult]         = useState<ResultDisplay | null>(null);
  const [cycleCount, setCycleCount]       = useState(0);
  const [resetTick, setResetTick]         = useState(0);

  // Governance modal state
  const [activeGovModal, setActiveGovModal] = useState<"approve" | "reinvestigate" | "override" | null>(null);
  const [performedBy, setPerformedBy]       = useState("");
  const [govReason, setGovReason]           = useState("");
  const [govNotes, setGovNotes]             = useState("");
  const [govSubmitting, setGovSubmitting]   = useState(false);

  // Report modal
  const [viewReportOpen, setViewReportOpen] = useState(false);

  // Reset confirmation modal
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetLoading, setResetLoading]     = useState(false);

  useEffect(() => {
    fetchAlerts()
      .then((d) => { setAlerts(d.alerts); setBackendOk(true); })
      .catch(() => setBackendOk(false));
  }, []);

  // Reset DPR result when project changes
  useEffect(() => {
    setDprResult(null);
    setCycleCount(0);
    setActiveGovModal(null);
    setViewReportOpen(false);
    setShowResetModal(false);
  }, [selected]);

  const current      = alerts.find((a) => a.id === selected) ?? null;
  const ghostCount   = alerts.filter((a) => a.status === "GHOST_ALERT").length;
  const awaitingCount = alerts.filter(
    (a) => a.status === "AWAITING_DPR" || a.status === "AWAITING_SCAN"
  ).length;

  // Governance handler
  const handleGovernanceAction = async (
    actionType: "approve" | "reinvestigate" | "override",
    data: { performed_by: string; reason: string; notes?: string }
  ) => {
    if (!selected || !dprResult?.cycle_id) return;
    setGovSubmitting(true);
    try {
      const r = await fetch(
        `${API_BASE}/projects/${selected}/cycles/${dprResult.cycle_id}/${actionType}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      );
      if (!r.ok) throw new Error(`Governance action failed: ${r.statusText}`);

      const latestR = await fetch(`${API_BASE}/projects/${selected}/cycles/latest`);
      if (latestR.ok) {
        const cycle = await latestR.json();
        setDprResult((prev) => prev ? { ...prev, governance: cycle.governance } : prev);
      }

      setActiveGovModal(null);
      setPerformedBy("");
      setGovReason("");
      setGovNotes("");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to perform governance action.");
    } finally {
      setGovSubmitting(false);
    }
  };

  // Reset handler
  const handleReset = async () => {
    if (!selected) return;
    setResetLoading(true);
    try {
      await deleteAssuranceHistory(selected);
      setShowResetModal(false);
      setDprResult(null);
      setCycleCount(0);
      setResetTick((t) => t + 1); // signal FraudAnalytics to reset
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to reset assurance history.");
    } finally {
      setResetLoading(false);
    }
  };

  // ── Tender Registry view ───────────────────────────────────────────────────
  if (showTenders) {
    return (
      <GovernanceEventsProvider>
        <div className="flex min-h-screen flex-col">
          <div className="flex items-center gap-3 px-6 py-3 border-b border-[color:var(--border)] bg-[color:var(--surface)]">
            <button
              onClick={() => setShowTenders(false)}
              className="flex items-center gap-1.5 text-xs text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5 rotate-180" />
              Back to ATLAS ASSURANCE
            </button>
            <span className="text-[color:var(--border)]">·</span>
            <p className="text-xs font-semibold text-[color:var(--muted)]">
              Tender Registry <span className="text-[color:var(--muted-2)]">(Future Capability)</span>
            </p>
          </div>
          <TenderRegistry />
        </div>
      </GovernanceEventsProvider>
    );
  }

  return (
    <GovernanceEventsProvider>
      <div className="flex min-h-screen flex-col">
        <div className="flex flex-1 min-h-0">

          {/* ── Sidebar ─────────────────────────────────────────────────────── */}
          <ProjectsRail
            selected={selected}
            onSelect={(id) => { setSelected(id); }}
            onOpenTenders={() => setShowTenders(true)}
          />

          <main className="flex-1 flex flex-col min-w-0 overflow-y-auto scroll-thin">

            {/* ── Executive Command Header (no duplicate ATLAS ASSURANCE) ── */}
            <header className="border-b border-[color:var(--border)] bg-[color:var(--surface)] px-8 py-4 flex items-center justify-between gap-4 shrink-0">
              <div>
                <h1 className="text-lg font-bold tracking-wide">Atlas Assurance</h1>
                <p className="text-xs text-[color:var(--muted)] mt-0.5">Autonomous assurance for public infrastructure</p>
              </div>
              <div className="flex items-center gap-3">
                <Summary icon={AlertTriangle} tone="danger" label="Ghost alerts" value={ghostCount} />
                <Summary icon={FileText} tone="muted" label="Awaiting docs" value={awaitingCount} />
                <BackendIndicator ok={backendOk} />
              </div>
            </header>

            {/* ── Empty state ──────────────────────────────────────────────── */}
            {!selected && <EmptyState />}

            {/* ── Loading skeleton ─────────────────────────────────────────── */}
            {selected && !current && (
              <div className="p-8"><div className="skeleton h-96 w-full" /></div>
            )}

            {selected && current && (
              <div className="flex-1">

                {/* ══ 1. PROJECT HERO ════════════════════════════════════════ */}
                <ProjectHero alert={current} />

                {/* ══ 2. ASSURANCE LIFECYCLE ════════════════════════════════ */}
                <AssuranceLifecycle alert={current} result={dprResult} />

                {/* ══ 3. EVIDENCE EXPLORER ══════════════════════════════════ */}
                <section className="border-b border-[color:var(--border)]">
                  <div className="px-8 pt-7 pb-0 flex items-center justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-bold tracking-tight">Evidence Explorer</h2>
                      <p className="text-xs text-[color:var(--muted)] mt-1">All intelligence layers for this project</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {cycleCount > 0 && (
                        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[color:var(--primary)]/5 border border-[color:var(--primary)]/20 text-[11px] font-semibold text-[color:var(--primary)]">
                          <FileText className="w-3 h-3" />
                          <span>{cycleCount} {cycleCount === 1 ? "cycle" : "cycles"}</span>
                        </div>
                      )}
                      {cycleCount > 0 && (
                        <button
                          onClick={() => setShowResetModal(true)}
                          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-[color:var(--danger)]/30 text-[10px] font-semibold text-[color:var(--danger)] hover:bg-[color:var(--danger)]/5 transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                          Reset History
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Tab bar */}
                  <div className="px-8 pt-4 pb-0 flex flex-wrap gap-2 bg-transparent">
                    {EVIDENCE_TABS.map((t) => {
                      const Icon = t.icon;
                      return (
                        <button
                          key={t.key}
                          onClick={() => setEvidenceTab(t.key)}
                          className={`tab inline-flex items-center gap-2 ${evidenceTab === t.key ? "tab-active" : ""}`}
                        >
                          <Icon className="w-3.5 h-3.5" />
                          {t.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Tab content */}
                  <div className="p-8 max-w-5xl">
                    <MountedTab active={evidenceTab === "dpr"}>
                      <FraudAnalytics
                        projectId={selected}
                        onResult={setDprResult}
                        onCycleCount={setCycleCount}
                        externalReset={resetTick}
                      />
                    </MountedTab>
                    <MountedTab active={evidenceTab === "satellite"}><SatelliteView projectId={current.id} /></MountedTab>
                    <MountedTab active={evidenceTab === "ppe"}><SiteGuard projectId={current.id} /></MountedTab>
                    <MountedTab active={evidenceTab === "forensics"}><TruthLens projectId={current.id} /></MountedTab>
                    <MountedTab active={evidenceTab === "governance"}><ContractorTrust projectId={current.id} /></MountedTab>
                  </div>
                </section>

                {/* ══ 4. ATLAS SYNTHESIS ════════════════════════════════════ */}
                {dprResult?.unified_risk && (
                  <section className="px-8 py-7 border-b border-[color:var(--border)]">
                    <div className="max-w-5xl">
                      <div className="mb-5">
                        <h2 className="text-xl font-bold tracking-tight">Atlas Synthesis</h2>
                        <p className="text-xs text-[color:var(--muted)] mt-1">Unified assurance derived from all evidence layers</p>
                      </div>

                      <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] shadow-sm overflow-hidden">
                        <div className="p-6 flex flex-col md:flex-row gap-6 items-center">

                          {/* Score Circle + Tier */}
                          <div className="flex flex-col items-center justify-center shrink-0 border-b md:border-b-0 md:border-r border-[color:var(--border)] pb-5 md:pb-0 md:pr-6 w-full md:w-auto">
                            <div className="relative w-28 h-28 flex items-center justify-center">
                              <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 112 112">
                                <circle cx="56" cy="56" r="46" stroke="var(--border)" strokeWidth="7" fill="transparent" />
                                <circle
                                  cx="56" cy="56" r="46"
                                  stroke={
                                    dprResult.unified_risk.tier.includes("CRITICAL") ? "var(--danger)"
                                    : dprResult.unified_risk.tier.includes("HIGH") ? "#ef4444"
                                    : dprResult.unified_risk.tier.includes("MODERATE") ? "var(--warning)"
                                    : "#22c55e"
                                  }
                                  strokeWidth="7"
                                  fill="transparent"
                                  strokeDasharray={2 * Math.PI * 46}
                                  strokeDashoffset={2 * Math.PI * 46 * (1 - dprResult.unified_risk.score / 100)}
                                  strokeLinecap="round"
                                  className="transition-all duration-1000 ease-out"
                                />
                              </svg>
                              <div className="text-center z-10">
                                <span className="text-4xl font-extrabold tracking-tight">{dprResult.unified_risk.score}</span>
                                <span className="text-xs text-[color:var(--muted)] block">/ 100</span>
                              </div>
                            </div>
                            <span className={`mt-4 px-3 py-1 rounded-full text-[10px] font-black tracking-widest uppercase ${
                              dprResult.unified_risk.tier.includes("CRITICAL") ? "bg-red-500/10 text-red-400"
                              : dprResult.unified_risk.tier.includes("HIGH") ? "bg-orange-500/10 text-orange-400"
                              : dprResult.unified_risk.tier.includes("MODERATE") ? "bg-amber-500/10 text-amber-400"
                              : "bg-green-500/10 text-green-400"
                            }`}>
                              {dprResult.unified_risk.tier}
                            </span>
                          </div>

                          {/* Rationale — the 3 key findings that matter */}
                          <div className="flex-1 space-y-3">
                            <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">Atlas Assessment</p>
                            <ul className="space-y-2.5">
                              {dprResult.unified_risk.rationale.slice(0, 3).map((r, idx) => (
                                <li key={idx} className="text-sm text-[color:var(--foreground)] flex items-start gap-3 leading-relaxed">
                                  <span className="shrink-0 mt-2 w-1.5 h-1.5 rounded-full bg-[color:var(--primary)]" />
                                  {r}
                                </li>
                              ))}
                            </ul>
                            {/* Confidence badge */}
                            {dprResult.unified_risk.confidence != null && (
                              <div className="pt-3 border-t border-[color:var(--border)]">
                                <span className="text-[10px] text-[color:var(--muted)]">
                                  Confidence: <span className="font-semibold text-[color:var(--foreground)]">{Math.round(dprResult.unified_risk.confidence * 100)}%</span>
                                  {" · "}Evidence sources: DPR · Satellite · Contractor · Cross-Signal
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>
                )}

                {/* ══ 5. FINAL ASSURANCE REPORT ═════════════════════════════ */}
                {dprResult?.cycle_id && (
                  <section className="px-8 py-7 border-b border-[color:var(--border)]">
                    <div className="max-w-5xl">
                      <div className="mb-5">
                        <h2 className="text-xl font-bold tracking-tight">Final Assurance Report</h2>
                        <p className="text-xs text-[color:var(--muted)] mt-1">Complete audit-ready report generated from all intelligence layers</p>
                      </div>

                      <div className="rounded-2xl border border-[color:var(--primary)]/20 bg-gradient-to-br from-[color:var(--primary)]/5 to-transparent p-6 shadow-sm">
                        <div className="flex items-start justify-between gap-6 flex-wrap">
                          <div>
                            <div className="flex items-center gap-3 mb-2">
                              <div className="w-9 h-9 rounded-xl bg-[color:var(--primary)]/10 border border-[color:var(--primary)]/20 flex items-center justify-center">
                                <FileSpreadsheet className="w-4.5 h-4.5 text-[color:var(--primary)]" style={{ width: "18px", height: "18px" }} />
                              </div>
                              <div>
                                <p className="font-bold text-sm">Milestone Clearance Assurance Report</p>
                                <p className="text-[10px] text-[color:var(--muted)] mt-0.5">
                                  {dprResult.cycle_id && <>Cycle: {dprResult.cycle_id}</>}
                                </p>
                              </div>
                            </div>
                            <p className="text-xs text-[color:var(--muted)] max-w-md leading-relaxed">
                              Consolidates all Atlas intelligence — DPR analysis, satellite evidence, cross-evidence correlation, unified risk score, and governance decisions — into a single auditable document.
                            </p>
                          </div>

                          <div className="flex flex-wrap gap-2.5 items-start">
                            <button
                              onClick={() => setViewReportOpen(true)}
                              className="flex items-center gap-2 px-4 py-2.5 bg-[color:var(--primary)] hover:bg-[color:var(--primary-hover)] text-black font-bold text-xs rounded-xl transition-colors shadow-md shadow-[color:var(--primary)]/20"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              View Report
                            </button>
                            <button
                              onClick={() => {
                                const url = `${API_BASE}/projects/${selected}/cycles/${dprResult.cycle_id}/report?format=html&print=true`;
                                window.open(url, "_blank");
                              }}
                              className="flex items-center gap-2 px-4 py-2.5 bg-[color:var(--surface-2)] hover:bg-[color:var(--surface-3)] text-[color:var(--foreground)] font-bold text-xs rounded-xl border border-[color:var(--border)] transition-colors"
                            >
                              <Printer className="w-3.5 h-3.5" />
                              Print Report
                            </button>
                            <button
                              onClick={() => {
                                const url = `${API_BASE}/projects/${selected}/cycles/${dprResult.cycle_id}/report?format=json`;
                                window.open(url, "_blank");
                              }}
                              className="flex items-center gap-2 px-4 py-2.5 bg-[color:var(--surface-2)] hover:bg-[color:var(--surface-3)] text-[color:var(--foreground)] font-bold text-xs rounded-xl border border-[color:var(--border)] transition-colors"
                            >
                              <Download className="w-3.5 h-3.5" />
                              Export JSON
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>
                )}

                {/* ══ 6. HUMAN GOVERNANCE ═══════════════════════════════════ */}
                {dprResult?.governance && (
                  <section className="px-8 py-7">
                    <div className="max-w-5xl">
                      <div className="mb-5">
                        <h2 className="text-xl font-bold tracking-tight">Human Governance</h2>
                        <p className="text-xs text-[color:var(--muted)] mt-1">Atlas recommends. Humans decide.</p>
                      </div>

                      <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] shadow-sm overflow-hidden">
                        {/* Status row */}
                        <div className="px-5 py-3.5 border-b border-[color:var(--border)] flex items-center justify-between bg-[color:var(--surface-2)]">
                          <div className="flex items-center gap-2.5">
                            <ClipboardList className="w-4 h-4 text-[color:var(--primary)]" />
                            <span className="text-sm font-semibold">Governance Status</span>
                          </div>
                          <span className={`px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider ${
                            dprResult.governance.status === "APPROVED" ? "bg-green-500/10 text-green-400"
                            : dprResult.governance.status === "REINVESTIGATION_REQUESTED" ? "bg-amber-500/10 text-amber-400"
                            : dprResult.governance.status === "OVERRIDDEN" ? "bg-orange-500/10 text-orange-400"
                            : "bg-blue-500/10 text-blue-400"
                          }`}>
                            {dprResult.governance.status.replace(/_/g, " ")}
                          </span>
                        </div>

                        <div className="p-5 space-y-4">
                          {/* Action buttons */}
                          <div className="flex flex-wrap gap-2.5">
                            <button
                              onClick={() => setActiveGovModal("approve")}
                              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-xs font-bold transition-colors"
                            >
                              Approve Cycle
                            </button>
                            <button
                              onClick={() => setActiveGovModal("reinvestigate")}
                              className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold transition-colors"
                            >
                              Request Reinvestigation
                            </button>
                            <button
                              onClick={() => setActiveGovModal("override")}
                              className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-xs font-bold transition-colors"
                            >
                              Override Recommendation
                            </button>
                          </div>

                          {/* Compact timeline */}
                          {dprResult.governance.actions && dprResult.governance.actions.length > 0 && (
                            <div className="pt-3 border-t border-[color:var(--border)]">
                              <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-3">Timeline</p>
                              <div className="relative border-l border-[color:var(--border)] ml-3 pl-4 space-y-3">
                                {[...dprResult.governance.actions].reverse().map((act: {
                                  action_type: string;
                                  performed_by: string;
                                  performed_at: string;
                                  reason: string;
                                  notes: string;
                                }, idx: number) => (
                                  <div key={idx} className="relative">
                                    <span className={`absolute -left-[23px] top-1 w-2 h-2 rounded-full border-2 bg-[color:var(--surface)] ${
                                      act.action_type === "APPROVE" ? "border-green-500"
                                      : act.action_type === "REQUEST_REINVESTIGATION" ? "border-amber-500"
                                      : "border-orange-500"
                                    }`} />
                                    <div className="flex flex-wrap items-center gap-2 mb-0.5">
                                      <span className="text-xs font-bold text-[color:var(--foreground)]">
                                        {act.action_type === "APPROVE" ? "Approved"
                                          : act.action_type === "REQUEST_REINVESTIGATION" ? "Reinvestigation Requested"
                                          : "Overridden"}
                                      </span>
                                      <span className="text-[10px] text-[color:var(--muted)] font-mono">
                                        {new Date(act.performed_at).toLocaleString()}
                                      </span>
                                    </div>
                                    <p className="text-[11px] text-[color:var(--muted)]">
                                      <strong>{act.performed_by}</strong> · {act.reason}
                                    </p>
                                    {act.notes && (
                                      <p className="text-[10px] text-[color:var(--muted-2)] italic mt-0.5">{act.notes}</p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </section>
                )}

              </div>
            )}

          </main>
        </div>

        {/* ── Reset Confirmation Modal ─────────────────────────────────────── */}
        {showResetModal && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-[color:var(--surface)] border border-[color:var(--border)] rounded-2xl w-full max-w-sm shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              <div className="bg-[color:var(--surface-2)] px-6 py-4 border-b border-[color:var(--border)] flex items-center justify-between">
                <h3 className="font-bold tracking-tight text-sm text-[color:var(--foreground)]">Reset Assurance History?</h3>
                <button onClick={() => setShowResetModal(false)} className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-6 space-y-4">
                <p className="text-xs text-[color:var(--muted)] leading-relaxed">
                  This will permanently remove all assurance cycles and generated reports for this project and restore it to its initial state.
                </p>
                <p className="text-xs font-semibold text-[color:var(--danger)]">This action cannot be undone.</p>
                <div className="flex gap-3 pt-2 border-t border-[color:var(--border)]">
                  <button
                    type="button"
                    onClick={() => setShowResetModal(false)}
                    className="flex-1 px-4 py-2 border border-[color:var(--border)] text-[color:var(--muted)] rounded-lg text-xs font-semibold hover:bg-[color:var(--surface-2)] transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={resetLoading}
                    onClick={handleReset}
                    className="flex-1 px-4 py-2 bg-[color:var(--danger)] hover:opacity-90 text-white rounded-lg text-xs font-bold transition-opacity flex items-center justify-center gap-2"
                  >
                    {resetLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Reset Project
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Governance Modal ─────────────────────────────────────────────── */}
        {activeGovModal && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-[color:var(--surface)] border border-[color:var(--border)] rounded-2xl w-full max-w-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              <div className="bg-[color:var(--surface-2)] px-6 py-4 border-b border-[color:var(--border)]">
                <h3 className="font-bold tracking-tight text-sm">
                  {activeGovModal === "approve" ? "Approve Assurance Cycle"
                    : activeGovModal === "reinvestigate" ? "Request Reinvestigation"
                    : "Override AI Recommendation"}
                </h3>
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!performedBy || !govReason) { alert("Please fill in all required fields."); return; }
                  handleGovernanceAction(activeGovModal, { performed_by: performedBy, reason: govReason, notes: govNotes });
                }}
                className="p-6 space-y-4"
              >
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] block">
                    Performed By <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text" required
                    placeholder="e.g. Executive Engineer / Regional Auditor"
                    value={performedBy}
                    onChange={(e) => setPerformedBy(e.target.value)}
                    className="w-full text-xs px-3 py-2 bg-[color:var(--surface-2)] border border-[color:var(--border)] rounded-lg focus:outline-none focus:border-[color:var(--primary)] text-[color:var(--foreground)]"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] block">
                    Reason <span className="text-red-500">*</span>
                  </label>
                  <select
                    required value={govReason}
                    onChange={(e) => setGovReason(e.target.value)}
                    className="w-full text-xs px-3 py-2 bg-[color:var(--surface-2)] border border-[color:var(--border)] rounded-lg focus:outline-none focus:border-[color:var(--primary)] text-[color:var(--foreground)]"
                  >
                    <option value="">-- Select a reason --</option>
                    {activeGovModal === "approve" && (
                      <>
                        <option value="Field verification completed.">Field verification completed.</option>
                        <option value="Findings accepted.">Findings accepted.</option>
                        <option value="Minor issues resolved.">Minor issues resolved.</option>
                      </>
                    )}
                    {activeGovModal === "reinvestigate" && (
                      <>
                        <option value="Additional evidence required.">Additional evidence required.</option>
                        <option value="Contradictory observations.">Contradictory observations.</option>
                        <option value="Discrepancies identified in report.">Discrepancies identified in report.</option>
                      </>
                    )}
                    {activeGovModal === "override" && (
                      <>
                        <option value="Policy exception.">Policy exception.</option>
                        <option value="Executive discretion.">Executive discretion.</option>
                        <option value="Alternative verification source approved.">Alternative verification source approved.</option>
                      </>
                    )}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] block">Optional Notes</label>
                  <textarea
                    placeholder="Add any specific context or remarks..."
                    value={govNotes}
                    onChange={(e) => setGovNotes(e.target.value)}
                    rows={3}
                    className="w-full text-xs px-3 py-2 bg-[color:var(--surface-2)] border border-[color:var(--border)] rounded-lg focus:outline-none focus:border-[color:var(--primary)] text-[color:var(--foreground)] resize-none"
                  />
                </div>
                <div className="flex justify-end gap-3 pt-2 border-t border-[color:var(--border)]">
                  <button
                    type="button"
                    onClick={() => setActiveGovModal(null)}
                    className="px-4 py-2 border border-[color:var(--border)] text-[color:var(--muted)] rounded-lg text-xs font-semibold hover:bg-[color:var(--surface-2)] transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit" disabled={govSubmitting}
                    className="px-4 py-2 bg-[color:var(--primary)] text-black rounded-lg text-xs font-bold hover:bg-[color:var(--primary-hover)] transition-colors flex items-center gap-2"
                  >
                    {govSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Submit Decision
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── View Report Modal ────────────────────────────────────────────── */}
        {viewReportOpen && dprResult?.cycle_id && selected && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
            <div className="bg-[color:var(--surface)] border border-[color:var(--border)] rounded-2xl w-full max-w-4xl shadow-xl overflow-hidden animate-in zoom-in-95 duration-150 flex flex-col h-[85vh]">
              <div className="bg-[color:var(--surface-2)] px-6 py-4 border-b border-[color:var(--border)] flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="w-5 h-5 text-[color:var(--primary)]" />
                  <h3 className="font-bold tracking-tight text-sm">Milestone Clearance Assurance Report</h3>
                </div>
                <button
                  onClick={() => {
                    const url = `${API_BASE}/projects/${selected}/cycles/${dprResult.cycle_id}/report?format=html&print=true`;
                    window.open(url, "_blank");
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-[color:var(--primary)] to-indigo-500 hover:opacity-90 text-black rounded-lg text-xs font-bold transition-opacity"
                >
                  <Printer className="w-3.5 h-3.5" />
                  Print Report
                </button>
              </div>
              <div className="grow overflow-hidden bg-white p-4">
                <iframe
                  src={`${API_BASE}/projects/${selected}/cycles/${dprResult.cycle_id}/report?format=html`}
                  className="w-full h-full border-0 rounded-xl"
                />
              </div>
              <div className="bg-[color:var(--surface-2)] px-6 py-4 border-t border-[color:var(--border)] flex justify-end shrink-0">
                <button
                  type="button"
                  onClick={() => setViewReportOpen(false)}
                  className="px-4 py-2 bg-[color:var(--surface)] border border-[color:var(--border)] text-[color:var(--muted)] rounded-lg text-xs font-semibold hover:bg-[color:var(--surface-2)] transition-colors"
                >
                  Close Report
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </GovernanceEventsProvider>
  );
}

// ── Section Components ────────────────────────────────────────────────────────

function ProjectHero({ alert }: { alert: SatelliteAlert }) {
  const tone = STATUS_TONE[alert.status] ?? { chip: "chip-muted", label: alert.status };
  return (
    <div className="px-8 py-6 bg-[color:var(--surface)] border-b border-[color:var(--border)]">
      <div className="flex items-start justify-between gap-6 flex-wrap max-w-5xl">
        <div className="min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-2xl font-bold tracking-tight">{alert.project}</h2>
            <span className={`chip ${tone.chip}`}>{tone.label}</span>
          </div>
          <p className="text-sm text-[color:var(--muted)] mt-1.5">
            {alert.contractor}
            <span className="mx-2 text-[color:var(--border-strong)]">·</span>
            {alert.id}
            <span className="mx-2 text-[color:var(--border-strong)]">·</span>
            {alert.location?.[0]?.toFixed(3)}, {alert.location?.[1]?.toFixed(3)}
          </p>
          {alert.dpr_record?.source_url && (
            <a
              href={alert.dpr_record.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-[11px] text-[color:var(--primary)] hover:underline inline-flex items-center gap-1 mt-1.5"
            >
              DPR source <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
        <div className="flex gap-3">
          <HeroStat label="Reported"    value={alert.reported_progress_pct != null ? `${alert.reported_progress_pct}%` : "—"} />
          <HeroStat label="Observed"    value={alert.satellite_actual_pct  != null ? `${alert.satellite_actual_pct}%`  : "—"} />
          <HeroStat
            label="Gap"
            value={alert.discrepancy_pct != null ? `${alert.discrepancy_pct > 0 ? "+" : ""}${alert.discrepancy_pct}%` : "—"}
            tone={alert.status === "GHOST_ALERT" ? "danger" : alert.status === "LAG_WARNING" ? "warning" : undefined}
          />
        </div>
      </div>
    </div>
  );
}

function HeroStat({ label, value, tone }: { label: string; value: string; tone?: "danger" | "warning" }) {
  const color =
    tone === "danger" ? "text-[color:var(--danger)]"
    : tone === "warning" ? "text-[color:var(--warning)]"
    : "text-[color:var(--foreground)]";
  return (
    <div className="surface-elev px-4 py-2.5 min-w-[72px] text-center">
      <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">{label}</p>
      <p className={`text-xl font-bold metric-value mt-1 ${color}`}>{value}</p>
    </div>
  );
}

function AssuranceLifecycle({ alert, result }: { alert: SatelliteAlert; result: ResultDisplay | null }) {
  return (
    <div className="px-8 py-5 border-b border-[color:var(--border)] bg-[color:var(--surface-2)]/50">
      <div className="max-w-5xl">
        <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-3">Assurance Lifecycle</p>
        <div className="flex items-center gap-1 flex-wrap">
          {LIFECYCLE_STAGES.map((stage, idx) => {
            const Icon   = stage.icon;
            const status = stage.getStatus(alert, result);
            return (
              <div key={stage.key} className="flex items-center gap-1">
                <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all ${
                  status === "done"
                    ? "bg-[color:var(--primary)]/10 text-[color:var(--primary)] border border-[color:var(--primary)]/20"
                    : status === "active"
                    ? "bg-[color:var(--warning)]/10 text-[color:var(--warning)] border border-[color:var(--warning)]/30 animate-pulse"
                    : "bg-[color:var(--surface)] text-[color:var(--muted)] border border-[color:var(--border)]"
                }`}>
                  {status === "done" ? (
                    <CheckCircle2 className="w-3 h-3" />
                  ) : (
                    <Icon className="w-3 h-3" />
                  )}
                  <span>{stage.label}</span>
                </div>
                {idx < LIFECYCLE_STAGES.length - 1 && (
                  <ChevronRight className={`w-3 h-3 ${status === "done" ? "text-[color:var(--primary)]/40" : "text-[color:var(--border)]"}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center p-16">
      <div className="w-16 h-16 rounded-2xl bg-[color:var(--surface-2)] border border-[color:var(--border)] flex items-center justify-center mb-5 shadow-sm">
        <ShieldCheck className="w-8 h-8 text-[color:var(--primary)]/40" />
      </div>
      <h2 className="text-xl font-bold tracking-tight mb-2">Select a Project</h2>
      <p className="text-sm text-[color:var(--muted)] max-w-xs leading-relaxed">
        Choose a registered project from the sidebar to begin your assurance review.
      </p>
    </div>
  );
}

// ── Summary Badge ─────────────────────────────────────────────────────────────

function Summary({ icon: Icon, tone, label, value }: {
  icon: typeof AlertTriangle;
  tone: "danger" | "muted";
  label: string;
  value: number;
}) {
  if (value === 0 && tone === "danger") return null;
  const cls =
    tone === "danger"
      ? "bg-[color:var(--danger)]/10 border-[color:var(--danger)]/20 text-[color:var(--danger)]"
      : "bg-[color:var(--surface-2)] border-[color:var(--border)] text-[color:var(--muted)]";
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold ${cls}`}>
      <Icon className="w-3.5 h-3.5" />
      <span>{value} {label}</span>
    </div>
  );
}

// ── Backend Indicator ─────────────────────────────────────────────────────────

function BackendIndicator({ ok }: { ok: boolean | null }) {
  if (ok === null) return <div className="w-2 h-2 rounded-full bg-[color:var(--muted)] animate-pulse" />;
  return (
    <div className={`flex items-center gap-1.5 text-[10px] font-semibold ${ok ? "text-green-400" : "text-[color:var(--danger)]"}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-green-400" : "bg-[color:var(--danger)]"}`} />
      {ok ? "Online" : "Offline"}
    </div>
  );
}
