"use client";

import { useState } from "react";
import Image from "next/image";
import { SearchCode, Upload, Loader2, ShieldCheck, ShieldAlert } from "lucide-react";
import { API_BASE, assetUrl } from "@/lib/api";
import { useGovernanceEvents } from "@/lib/governanceEvents";

type Stats = { mean_error: number; std_error: number; max_error: number; p95_error: number };
type Notice = { available: boolean; text?: string; reason?: string };

type Result = {
  filename: string;
  attribution: { project_id: string | null; contractor: string | null; site: string | null };
  tampering_detected: boolean;
  tampering_score: number;
  ela_stats: Stats;
  ela_image: string;
  ai_analysis: Notice | null;
};

type Props = { projectId: string | null };

export function TruthLens({ projectId }: Props) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { bump } = useGovernanceEvents();

  const handle = async (file: File) => {
    setIsAnalyzing(true);
    setError(null);
    setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    if (projectId) fd.append("project_id", projectId);
    try {
      const r = await fetch(`${API_BASE}/analyze-forensics`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
      setResult(await r.json());
      bump();
    } catch (e) {
      setError(String(e));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const riskLabel = (score: number, detected: boolean) => {
    if (detected) return { label: "High", tone: "danger" as const };
    if (score > 0.30) return { label: "Medium", tone: "warning" as const };
    return { label: "Low", tone: "success" as const };
  };

  return (
    <div className="surface p-6 fade-in">
      <header className="flex items-center gap-3 mb-5">
        <div className="w-9 h-9 rounded-lg bg-[color:var(--primary-soft)] flex items-center justify-center">
          <SearchCode className="w-4 h-4 text-[color:var(--primary)]" />
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-[color:var(--muted)]">TruthLens</p>
          <h3 className="text-base font-semibold">Image forensics · Error Level Analysis</h3>
        </div>
      </header>

      {!isAnalyzing && !result && !error && (
        <label className="block">
          <input type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && handle(e.target.files[0])} />
          <div className="border-2 border-dashed border-[color:var(--border-strong)] rounded-xl py-12 flex flex-col items-center justify-center cursor-pointer hover:border-[color:var(--primary)] hover:bg-[color:var(--primary-soft)] transition-all">
            <Upload className="w-6 h-6 text-[color:var(--muted)] mb-3" />
            <p className="text-sm font-semibold">Upload an image to verify</p>
            <p className="text-xs text-[color:var(--muted)] mt-1">Detects compression artifacts from edits</p>
            <p className="text-[10px] text-[color:var(--muted-2)] mt-3">
              {projectId ? `Attributed to ${projectId}` : "No project selected — analysis unattributed"}
            </p>
          </div>
        </label>
      )}

      {isAnalyzing && (
        <div className="flex items-center gap-3 py-8 text-[color:var(--muted)]">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Computing ELA statistics…</span>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-[color:var(--danger-soft)] border border-[color:var(--danger)]/30 px-4 py-3 text-sm text-[color:var(--danger)]">
          <p className="font-semibold">Forensics failed</p>
          <p className="text-xs mt-1">{error}</p>
        </div>
      )}

      {result && (
        <div className="space-y-4 fade-in">
          {(() => {
            const risk = riskLabel(result.tampering_score, result.tampering_detected);
            const chip = risk.tone === "danger" ? "chip-danger" : risk.tone === "warning" ? "chip-warning" : "chip-success";
            const Icon = risk.tone === "danger" ? ShieldAlert : ShieldCheck;
            return (
              <div className="flex items-center justify-between gap-3">
                <span className={`chip ${chip}`}><Icon className="w-3 h-3" /> Risk · {risk.label}</span>
                <p className="text-xs text-[color:var(--muted)] metric-value">score {result.tampering_score.toFixed(3)} / threshold 0.45</p>
              </div>
            );
          })()}

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg overflow-hidden border border-[color:var(--border)] bg-black/40">
              <p className="text-[10px] px-3 py-2 border-b border-[color:var(--border)] font-semibold">ELA map</p>
              <Image
                src={assetUrl(result.ela_image)!}
                alt="ELA map"
                width={480}
                height={224}
                className="w-full h-56 object-contain"
                unoptimized
              />
            </div>
            <div className="surface-elev p-4">
              <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)] mb-3">ELA statistics</p>
              <div className="space-y-2 text-xs">
                <Row k="Mean error" v={result.ela_stats.mean_error} />
                <Row k="Std error" v={result.ela_stats.std_error} />
                <Row k="P95 error" v={result.ela_stats.p95_error} />
                <Row k="Max error" v={result.ela_stats.max_error} />
              </div>
              <div className="mt-3 pt-3 border-t border-[color:var(--border)] grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <p className="text-[color:var(--muted)]">Contractor</p>
                  <p className="font-semibold mt-0.5">{result.attribution.contractor ?? "—"}</p>
                </div>
                <div>
                  <p className="text-[color:var(--muted)]">Site</p>
                  <p className="font-semibold mt-0.5">{result.attribution.site ?? "—"}</p>
                </div>
              </div>
            </div>
          </div>

          {result.ai_analysis?.available && result.ai_analysis.text && (
            <div className="surface-elev p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-2">Mistral-7B forensic notice</p>
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap font-mono max-h-60 overflow-y-auto scroll-thin">{result.ai_analysis.text}</pre>
            </div>
          )}
          {!result.tampering_detected && (
            <p className="text-[11px] text-[color:var(--muted)]">No notice generated — image appears authentic by ELA heuristics.</p>
          )}

          <button onClick={() => { setResult(null); setError(null); }} className="btn btn-secondary w-full">Verify another image</button>
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: number }) {
  return (
    <div className="flex justify-between">
      <span className="text-[color:var(--muted)]">{k}</span>
      <span className="font-mono metric-value">{v.toFixed(2)}</span>
    </div>
  );
}
