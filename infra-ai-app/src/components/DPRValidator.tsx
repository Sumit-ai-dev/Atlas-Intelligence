"use client";

import { useEffect, useState } from "react";
import { FileText, Upload, Loader2, AlertTriangle, CheckCircle2, ExternalLink, FileCheck2 } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { useGovernanceEvents } from "@/lib/governanceEvents";

type Extraction = {
  extracted: boolean;
  reported_progress_pct?: number;
  matched_line?: string;
  confidence_score?: number;
  all_candidates?: { value: number; score: number; line: string }[];
  text_excerpt?: string;
  reason?: string;
};

type DprRecord = {
  project_id: string;
  reported_progress_pct: number;
  source: string;
  source_url: string | null;
  reported_date: string;
  ingested_at: string;
  raw_excerpt: string | null;
};

type Analysis = {
  status: string;
  reported_progress_pct: number | null;
  satellite_actual_pct: number;
  discrepancy_pct: number | null;
};

type AnalyzeDoc = {
  filename: string;
  attribution: { project_id: string | null; contractor: string | null; site: string | null };
  extraction: Extraction;
  dpr_record: DprRecord | null;
  satellite_analysis: Analysis | null;
  audit_notice: { available: boolean; text?: string; reason?: string } | null;
};

type Props = { projectId: string | null };

export function DPRValidator({ projectId }: Props) {
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<AnalyzeDoc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [existingDpr, setExistingDpr] = useState<DprRecord | null>(null);
  const [googleMapsUrl, setGoogleMapsUrl] = useState("");
  const { bump } = useGovernanceEvents();

  useEffect(() => {
    // Reset display state for the new project (deferred to avoid cascading renders)
    const id = setTimeout(() => {
      setResult(null);
      setError(null);
      setExistingDpr(null);
    }, 0);
    if (!projectId) return () => clearTimeout(id);
    fetch(`${API_BASE}/dpr/${projectId}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.project_id && d.reported_progress_pct != null) setExistingDpr(d);
      })
      .catch(() => {});
    return () => clearTimeout(id);
  }, [projectId]);

  const handle = async (file: File) => {
    setIsUploading(true);
    setError(null);
    setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    if (projectId) fd.append("project_id", projectId);
    if (googleMapsUrl.trim()) fd.append("google_maps_url", googleMapsUrl.trim());
    try {
      const r = await fetch(`${API_BASE}/analyze-doc`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
      setResult(await r.json());
      bump();
    } catch (e) {
      setError(String(e));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="surface p-6 fade-in">
      <header className="flex items-center gap-3 mb-5">
        <div className="w-9 h-9 rounded-lg bg-[color:var(--primary-soft)] flex items-center justify-center">
          <FileText className="w-4 h-4 text-[color:var(--primary)]" />
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-[color:var(--muted)]">DPR Validator</p>
          <h3 className="text-base font-semibold">OCR-driven progress extraction</h3>
        </div>
      </header>

      {existingDpr && !result && (
        <div className="surface-elev p-4 mb-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)] mb-1">Currently ingested DPR</p>
              <p className="text-sm font-semibold">{existingDpr.source}</p>
              <p className="text-xs text-[color:var(--muted)] mt-1">
                Reported <span className="text-[color:var(--foreground)] font-semibold metric-value">{existingDpr.reported_progress_pct}%</span> ·
                date {existingDpr.reported_date}
              </p>
              {existingDpr.source_url && (
                <a href={existingDpr.source_url} target="_blank" rel="noreferrer" className="text-[11px] text-[color:var(--primary)] hover:underline inline-flex items-center gap-1 mt-1">
                  Open source PDF <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            <FileCheck2 className="w-5 h-5 text-[color:var(--success)] shrink-0" />
          </div>
          {existingDpr.raw_excerpt && (
            <p className="text-[10px] font-mono text-[color:var(--muted-2)] mt-2 line-clamp-2">{existingDpr.raw_excerpt}</p>
          )}
        </div>
      )}

      {!isUploading && !result && !error && (
        <div className="space-y-4">
          <div className="surface-elev p-4">
            <p className="text-xs font-semibold mb-2">Optional: Manual Location Override</p>
            <input 
              type="text" 
              placeholder="Paste Google Maps URL here (e.g. https://maps.google.com/?q=28.25,77.06)"
              className="w-full bg-[color:var(--surface)] border border-[color:var(--border)] rounded px-3 py-2 text-xs focus:outline-none focus:border-[color:var(--primary)]"
              value={googleMapsUrl}
              onChange={(e) => setGoogleMapsUrl(e.target.value)}
            />
            <p className="text-[10px] text-[color:var(--muted)] mt-1">If empty, AI will autonomously locate the project from the DPR.</p>
          </div>

          <label className="block">
            <input type="file" accept="application/pdf" className="hidden" onChange={(e) => e.target.files?.[0] && handle(e.target.files[0])} />
            <div className="border-2 border-dashed border-[color:var(--border-strong)] rounded-xl py-12 flex flex-col items-center justify-center cursor-pointer hover:border-[color:var(--primary)] hover:bg-[color:var(--primary-soft)] transition-all">
              <Upload className="w-6 h-6 text-[color:var(--muted)] mb-3" />
              <p className="text-sm font-semibold">{existingDpr ? "Upload an updated DPR" : "Upload Detailed Project Report (DPR)"}</p>
              <p className="text-xs text-[color:var(--muted)] mt-1">PDF · Tesseract OCR + percentage extraction</p>
              <p className="text-[10px] text-[color:var(--muted-2)] mt-3">
                {projectId ? `Will be saved as DPR for ${projectId}` : "Will automatically register new project if no existing project is selected"}
              </p>
            </div>
          </label>
        </div>
      )}

      {isUploading && (
        <div className="flex items-center gap-3 py-8 text-[color:var(--muted)]">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Running OCR · scoring candidates · saving DPR…</span>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-[color:var(--danger-soft)] border border-[color:var(--danger)]/30 px-4 py-3 text-sm text-[color:var(--danger)]">
          <p className="font-semibold">Upload failed</p>
          <p className="text-xs mt-1">{error}</p>
        </div>
      )}

      {result && (
        <div className="space-y-4 fade-in">
          <div className="flex items-center gap-2 flex-wrap">
            {result.extraction.extracted ? (
              <span className="chip chip-success"><CheckCircle2 className="w-3 h-3" /> Extracted</span>
            ) : (
              <span className="chip chip-warning"><AlertTriangle className="w-3 h-3" /> No % found</span>
            )}
            {result.dpr_record && <span className="chip chip-info">Saved as DPR</span>}
            {result.satellite_analysis && (
              <span className={`chip ${result.satellite_analysis.status === "GHOST_ALERT" ? "chip-danger" : result.satellite_analysis.status === "LAG_WARNING" ? "chip-warning" : result.satellite_analysis.status === "NORMAL" ? "chip-success" : "chip-muted"}`}>
                {result.satellite_analysis.status.replace(/_/g, " ").toLowerCase()}
              </span>
            )}
          </div>

          {result.extraction.extracted && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Reported progress" value={`${result.extraction.reported_progress_pct}%`} big />
              <Field label="Match confidence" value={String(result.extraction.confidence_score ?? "—")} big />
            </div>
          )}

          {result.extraction.matched_line && (
            <div className="surface-elev p-3">
              <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)] mb-1">Matched line (OCR)</p>
              <p className="text-[11px] font-mono">{result.extraction.matched_line}</p>
            </div>
          )}

          {result.satellite_analysis && result.satellite_analysis.discrepancy_pct != null && (
            <div className="surface-elev p-4">
              <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)] mb-2">Reported vs Satellite</p>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div>
                  <p className="text-[10px] text-[color:var(--muted)]">Reported</p>
                  <p className="text-lg font-semibold metric-value">{result.satellite_analysis.reported_progress_pct}%</p>
                </div>
                <div>
                  <p className="text-[10px] text-[color:var(--muted)]">Satellite</p>
                  <p className="text-lg font-semibold metric-value">{result.satellite_analysis.satellite_actual_pct}%</p>
                </div>
                <div>
                  <p className="text-[10px] text-[color:var(--muted)]">Discrepancy</p>
                  <p className={`text-lg font-semibold metric-value ${result.satellite_analysis.discrepancy_pct > 15 ? "text-[color:var(--danger)]" : "text-[color:var(--foreground)]"}`}>
                    {result.satellite_analysis.discrepancy_pct > 0 ? "+" : ""}{result.satellite_analysis.discrepancy_pct}%
                  </p>
                </div>
              </div>
            </div>
          )}

          {result.audit_notice?.available && result.audit_notice.text && (
            <div className="surface-elev p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-2">Mistral-7B audit notice</p>
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap font-mono max-h-60 overflow-y-auto scroll-thin">{result.audit_notice.text}</pre>
            </div>
          )}

          {!result.extraction.extracted && (
            <details className="surface-elev p-3">
              <summary className="text-[11px] font-semibold cursor-pointer text-[color:var(--muted)]">Why was nothing extracted?</summary>
              <p className="text-xs mt-2 text-[color:var(--muted)]">{result.extraction.reason}</p>
              {result.extraction.text_excerpt && (
                <pre className="text-[10px] font-mono mt-2 whitespace-pre-wrap text-[color:var(--muted-2)] max-h-40 overflow-y-auto scroll-thin">{result.extraction.text_excerpt}</pre>
              )}
            </details>
          )}

          <button onClick={() => { setResult(null); setError(null); }} className="btn btn-secondary w-full">Upload another DPR</button>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, big }: { label: string; value: string; big?: boolean }) {
  return (
    <div className="surface-elev p-3">
      <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">{label}</p>
      <p className={`${big ? "text-2xl" : "text-sm"} font-semibold metric-value mt-1`}>{value}</p>
    </div>
  );
}
