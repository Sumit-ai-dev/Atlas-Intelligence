export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export type Project = {
  id: string;
  name: string;
  contractor: string;
  location: [number, number];
  baseline_date: string;
  started: string;
};

export type SatelliteAlert = {
  id: string;
  project: string;
  contractor: string;
  location: [number, number];
  status: string;
  reported_progress_pct: number | null;
  satellite_actual_pct?: number;
  discrepancy_pct?: number | null;
  baseline_date?: string;
  current_date?: string;
  evidence?: string;
  data_source?: string;
  method?: string;
    ml_change_detection?: {
      model: string;
      method: string;
      mean_change_score: number;
      max_change_score: number;
      high_change_cells_pct: number;
      sar_confidence?: number;
      sar_spike?: number;
      rgb_baseline_image: string;
    rgb_current_image: string;
    change_heatmap: string;
    severity?: string;
    severity_meta?: {
      label: string;
      color: string;
      bg: string;
      dot: string;
      priority: string;
    };
  } | null;
  dpr_record?: {
    source: string;
    source_url: string | null;
    reported_date: string;
  };
  images?: {
    rgb_baseline: string;
    rgb_current: string;
    ndvi_baseline: string;
    ndvi_current: string;
    landcover_baseline: string;
    landcover_current: string;
    transitions: string;
  };
  // Phase 1 quality block
  quality?: {
    phase: string;
    cloud_mask?: {
      baseline_pct_masked?: number;
      current_pct_masked?: number;
      baseline_usable?: boolean;
      current_usable?: boolean;
      note?: string;
    };
    temporal_consistency?: {
      scenes_fetched?: number;
      scenes_usable?: number;
      confidence?: number | null;
      adjusted_activity_pct?: number;
      reliability_score?: number;
      note?: string;
    };
    seasonal_normalization?: {
      season_matched?: boolean;
      season_delta_days?: number;
      warning?: string | null;
      note?: string;
    };
  };
};


// ── NCRI Types ──────────────────────────────────────────────────────────────

export type SeverityLevel = "LOW" | "MODERATE" | "CRITICAL" | "FRAUD RISK";

export type SeverityMeta = {
  label: SeverityLevel;
  color: string;
  bg: string;
  dot: string;
  priority: string;
};

export type NcriEligibility = {
  tier: "A" | "B" | "C" | "F";
  status: string;
  color: string;
  badge_bg: string;
  description: string;
};

export type NcriFinancialRisk = {
  amount_inr: number;
  amount_crore: number;
  display: string;
  severity: SeverityLevel;
  meta: SeverityMeta;
  disclaimer: string;
};

export type NcriViolation = {
  type: "IMAGE_TAMPERING" | "GHOST_ALERT" | "LAG_WARNING" | "SAFETY_VIOLATION";
  date: string;
  description: string;
  severity: SeverityLevel;
  recommended_action?: string;
};

export type NcriLedgerEntry = {
  date: string;
  type: string;
  description: string;
  deduction: number;
  severity: SeverityLevel;
  balance_after: number;
};

export type NcriTimelineEntry = {
  month: string;
  satellite_image: string;
  dpr_claimed_pct: number;
  satellite_verified_pct: number;
  discrepancy: number;
  severity: SeverityLevel;
};

export type NcriData = {
  project_id: string;
  project_name: string;
  contractor: string;
  ncri_score: number;
  eligibility: NcriEligibility;
  financial_risk: NcriFinancialRisk;
  active_violations: NcriViolation[];
  audit_ledger: NcriLedgerEntry[];
  timeline: NcriTimelineEntry[];
};

// ── Bidding / Tender Types ───────────────────────────────────────────────────

export type Tender = {
  tender_id: string;
  project_name: string;
  location: string;
  estimated_value_cr: number;
  min_ncri_required: number;
  deadline: string;
  description: string;
  status: "OPEN" | "CLOSED" | "AWARDED";
  awarded_to: string | null;
  awarded_contractor_name?: string;
  awarded_bid_cr?: number;
  created_at: string;
  bid_count?: number;
};

export type Bid = {
  bid_id: string;
  tender_id: string;
  contractor_id: string;
  contractor_name: string;
  bid_amount_cr: number;
  ncri_score: number;
  anomaly_score: number;
  flags: string[];
  eligibility: "ELIGIBLE" | "FLAGGED" | "REJECTED";
  active_violation_count: number;
  is_new_entity: boolean;
  years_of_experience: number;
  submitted_at: string;
  rank?: string;
};

export type TenderRecommendation = {
  recommended_contractor_id: string | null;
  recommended_contractor_name: string | null;
  recommended_bid_cr?: number;
  recommended_ncri?: number;
  reason: string;
  risk_level: "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
  eligible_count: number;
  flagged_count: number;
  rejected_count: number;
};

export type TenderDetail = {
  tender: Tender;
  leaderboard: Bid[];
  recommendation: TenderRecommendation;
};

// ── Fetch helpers ────────────────────────────────────────────────────────────

export async function fetchProjects(): Promise<Record<string, Project>> {
  const r = await fetch(`${API_BASE}/projects`);
  if (!r.ok) throw new Error(`fetchProjects: ${r.status}`);
  return r.json();
}

export async function fetchAlerts(): Promise<{ projects: string[]; alerts: SatelliteAlert[] }> {
  const r = await fetch(`${API_BASE}/satellite-alerts`);
  if (!r.ok) throw new Error(`fetchAlerts: ${r.status}`);
  return r.json();
}

export async function fetchNcri(projectId: string): Promise<NcriData> {
  const r = await fetch(`${API_BASE}/projects/${projectId}/ncri`);
  if (!r.ok) throw new Error(`fetchNcri: ${r.status}`);
  return r.json();
}

// Cache-bust key — changes every session so fresh satellite scans always load
// (Updated to trigger an HMR refresh for the new images!)
const _CACHE_KEY = Date.now() + 2000;

export function assetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  // Use Math.random() to guarantee cache bust every single render
  return `${API_BASE}${path}?v=${Math.random()}`;
}

export async function fetchTenders(): Promise<{ tenders: Tender[] }> {
  const r = await fetch(`${API_BASE}/tenders`);
  if (!r.ok) throw new Error(`fetchTenders: ${r.status}`);
  return r.json();
}

export async function fetchTenderDetail(tenderId: string): Promise<TenderDetail> {
  const r = await fetch(`${API_BASE}/tenders/${tenderId}`);
  if (!r.ok) throw new Error(`fetchTenderDetail: ${r.status}`);
  return r.json();
}

export async function awardTenderContract(tenderId: string, contractorId: string): Promise<unknown> {
  const r = await fetch(`${API_BASE}/tenders/${tenderId}/award/${contractorId}`, { method: "POST" });
  if (!r.ok) throw new Error(`awardContract: ${r.status}`);
  return r.json();
}

export async function submitBid(
  tenderId: string,
  fields: {
    contractor_id: string;
    contractor_name: string;
    bid_amount_cr: number;
    is_new_entity: boolean;
    years_of_experience: number;
  }
): Promise<Bid> {
  const form = new FormData();
  form.append("contractor_id", fields.contractor_id);
  form.append("contractor_name", fields.contractor_name);
  form.append("bid_amount_cr", String(fields.bid_amount_cr));
  form.append("is_new_entity", String(fields.is_new_entity));
  form.append("years_of_experience", String(fields.years_of_experience));
  const r = await fetch(`${API_BASE}/tenders/${tenderId}/bid`, { method: "POST", body: form });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || `submitBid: ${r.status}`);
  }
  return r.json();
}

// ── GSTIN Verification ──────────────────────────────────────────────────────

export interface GstinVerification {
  gstin: string;
  format_valid: boolean;
  checksum_valid: boolean;
  live_verified: boolean;
  company_name: string | null;
  trade_name: string | null;
  gst_status: string | null;
  state: string | null;
  entity_type: string | null;
  pan: string | null;
  registration_date: string | null;
  ncri: {
    found: boolean;
    ncri_score: number | null;
    violation_count: number;
    project_id?: string;
    project_name?: string;
  };
  risk_flags: string[];
  trust_level: "HIGH" | "MEDIUM" | "LOW" | "REJECTED";
  trust_reason: string;
  source?: string;
}

// ── DPR Scan Types ──────────────────────────────────────────────────────────

export type InvestigationSeverity = "LOW" | "MEDIUM" | "HIGH";
export type InvestigationConfidence = "LOW" | "MEDIUM" | "HIGH";

export type Investigation = {
  /** Short title describing the governance failure cluster */
  title: string;
  /** Overall severity of the investigation cluster */
  severity: InvestigationSeverity;
  /** Confidence that the cluster is real (driven by number of triggered findings) */
  confidence: InvestigationConfidence;
  /** One-paragraph narrative summary */
  summary: string;
  /** Human-readable labels of individual triggered findings */
  supporting_findings: string[];
  /** Raw evidence excerpts from ChromaDB search that fed the findings */
  evidence: string[];
  /** Deterministic governance action recommendations */
  recommendations: string[];
};

// ── Context Adjustment Type ─────────────────────────────────────────────────

export type ContextAdjustment = {
  original_budget_cr:       number;
  adjusted_budget_cr:       number;
  budget_adjustment_pct:    number;
  original_duration_months: number;
  adjusted_duration_months: number;
  assumptions_used:         string[];
};

// ── Cross-Evidence Type (Phase 3) ─────────────────────────────────────────────

export type CrossEvidenceFinding = {
  rule_id:            string;
  title:              string;
  summary:            string;
  severity:           "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  confidence:         "LOW" | "MEDIUM" | "HIGH";
  supporting_modules: string[];
  recommendations:    string[];
  triggered_by?:      { module: string; signal: string }[];
};

// ── Unified Risk Type (Phase 4) ─────────────────────────────────────────────

export type UnifiedRisk = {
  score: number;
  tier: string;
  confidence?: number;
  breakdown: {
    satellite: number;
    dpr: number;
    ncri: number;
    cross_evidence: number;
    context: number;
  };
  rationale: string[];
};


export type DprScanResult = {
  department: string;
  risk_level: "HIGH_RISK" | "LOW_RISK";
  approval_probability: number;
  rejection_probability: number;
  /** Backward-compatible flat evidence list (unchanged) */
  critical_evidence_found: string[];
  /** Alias of critical_evidence_found for frontend clarity */
  findings: string[];
  /** New: correlated investigation summaries */
  investigations: Investigation[];
  extracted_ml_features: {
    budget_cr: number;
    time_gap_months: number;
    [key: string]: number | string;
  };
  /** Phase 2: context adjustment (null for old cycles) */
  context?: ContextAdjustment | null;
  /** Phase 3: cross-evidence findings (empty for old cycles or when none fire) */
  cross_evidence?: CrossEvidenceFinding[] | null;
  /** Phase 4: unified risk */
  unified_risk?: UnifiedRisk | null;
  /** Phase 5: human governance */
  governance?: {
    status: string;
    actions: {
      action_type: string;
      performed_by: string;
      performed_at: string;
      reason: string;
      notes: string;
    }[];
  } | null;
};

export async function analyzeDpr(
  file: File,
  projectId: string,
  signal?: AbortSignal,
): Promise<DprScanResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("project_id", projectId);
  const r = await fetch(`${API_BASE}/scan-dpr`, { method: "POST", body: form, signal });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    const detail = typeof err.detail === "object" ? err.detail.error : (err.detail ?? r.statusText);
    throw new Error(detail);
  }
  return r.json();
}

export async function verifyGstin(gstin: string): Promise<GstinVerification> {
  const form = new FormData();
  form.append("gstin", gstin.trim().toUpperCase());
  const r = await fetch(`${API_BASE}/verify-gstin`, { method: "POST", body: form });
  if (!r.ok) throw new Error(`verifyGstin: ${r.status}`);
  return r.json();
}

// ── Digital Twin Cycle Types + Helpers ─────────────────────────────────────

export type AssuranceCycleSummary = {
  cycle_id:   string;
  created_at: string;
  verdict:    string | null;
  risk_score: number | null;
};

export type AssuranceCycle = {
  cycle_id:   string;
  project_id: string;
  created_at: string;
  // Backward-compatible top-level aliases (Phase 1 files use these)
  dpr_snapshot: {
    file_name:                string;
    sha256:                   string;
    uploaded_at:              string;
    source_files:             string[];
    truncated:                boolean;
    original_character_count: number;
  };
  dpr_analysis: {
    risk_score:       number;
    verdict:          string;
    budget_cr:        number;
    time_gap_months:  number;
    investigations:   Investigation[];
    findings:         string[];
  };
  // Phase 2 additions (absent in old cycles → optional)
  context?:          ContextAdjustment | null;
  assurance_status?: string;
  // Phase 3 addition (absent in old cycles → optional)
  cross_evidence?:   CrossEvidenceFinding[] | null;
  // Phase 4 addition
  unified_risk?:     UnifiedRisk | null;
  // Phase 5 addition
  governance?: {
    status: string;
    actions: {
      action_type: string;
      performed_by: string;
      performed_at: string;
      reason: string;
      notes: string;
    }[];
  } | null;
};

export async function fetchCycles(projectId: string): Promise<AssuranceCycleSummary[]> {
  const r = await fetch(`${API_BASE}/projects/${projectId}/cycles`);
  if (!r.ok) throw new Error(`fetchCycles: ${r.status}`);
  return r.json();
}


export async function fetchLatestCycle(projectId: string): Promise<AssuranceCycle> {
  const r = await fetch(`${API_BASE}/projects/${projectId}/cycles/latest`);
  if (!r.ok) throw new Error(`fetchLatestCycle: ${r.status}`);
  return r.json();
}

/** Phase 6.4: Delete all assurance cycles for a project (demo reset). */
export async function deleteAssuranceHistory(projectId: string): Promise<{ deleted: number; project_id: string }> {
  const r = await fetch(`${API_BASE}/projects/${projectId}/assurance-history`, { method: "DELETE" });
  if (!r.ok) throw new Error(`deleteAssuranceHistory: ${r.status}`);
  return r.json();
}

