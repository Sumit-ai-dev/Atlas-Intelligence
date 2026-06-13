"use client";

import { useState } from "react";
import { Shield, Upload, Loader2, AlertTriangle, CheckCircle2, ImageIcon } from "lucide-react";
import { API_BASE, assetUrl } from "@/lib/api";
import { useGovernanceEvents } from "@/lib/governanceEvents";

type Step = { step: string; message: string };
type Notice = { available: boolean; text?: string; reason?: string };

type AnalyzeResult = {
  filename: string;
  attribution: { project_id: string | null; contractor: string | null; site: string | null };
  violation_detected: boolean;
  violations: string[];
  severity: string;
  objects: { label: string; confidence: number }[];
  object_count: number;
  ppe_confidence_threshold: number;
  reasoning_log: Step[];
  legal_notice: Notice | null;
  output_image: string | null;
};

type Props = { projectId: string | null };

export function SiteGuard({ projectId }: Props) {
  const [isUploading, setIsUploading] = useState(false);
  const [log, setLog] = useState<Step[]>([]);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { bump } = useGovernanceEvents();

  const handleAnalysis = async (file: File) => {
    setIsUploading(true);
    setLog([]);
    setResult(null);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);
    if (projectId) formData.append("project_id", projectId);

    try {
      const response = await fetch(`${API_BASE}/analyze-site`, { method: "POST", body: formData });
      if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
      const data: AnalyzeResult = await response.json();

      for (let i = 0; i < data.reasoning_log.length; i++) {
        await new Promise((r) => setTimeout(r, 400));
        setLog((prev) => [...prev, data.reasoning_log[i]]);
      }
      setResult(data);
      bump();
    } catch (e) {
      setError(String(e));
    } finally {
      setIsUploading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setLog([]);
    setError(null);
  };

  return (
    <div className="surface p-6 fade-in">
      <header className="flex items-center gap-3 mb-5">
        <div className="w-9 h-9 rounded-lg bg-[color:var(--primary-soft)] flex items-center justify-center">
          <Shield className="w-4 h-4 text-[color:var(--primary)]" />
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-[color:var(--muted)]">SiteGuard</p>
          <h3 className="text-base font-semibold">PPE detection · YOLOv8 + Mistral-7B</h3>
        </div>
      </header>

      {!result && !isUploading && !error && (
        <label className="block group">
          <input type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && handleAnalysis(e.target.files[0])} />
          <div className="relative border border-dashed border-[color:var(--border-strong)] rounded-xl py-14 flex flex-col items-center justify-center cursor-pointer overflow-hidden transition-all duration-300 hover:border-[color:var(--primary)] hover:bg-[color:var(--primary-soft)] hover:shadow-[0_0_30px_rgba(0,229,255,0.15)]">
            <div className="absolute inset-0 bg-gradient-to-b from-[color:var(--primary-soft)] to-transparent opacity-0 group-hover:opacity-20 transition-opacity duration-500"></div>
            <Upload className="w-7 h-7 text-[color:var(--muted)] mb-4 group-hover:text-[color:var(--primary)] transition-colors duration-300 group-hover:scale-110" />
            <p className="text-sm font-bold tracking-wide group-hover:text-[color:var(--primary)] transition-colors">UPLOAD SECURE FEED</p>
            <p className="text-xs text-[color:var(--muted)] mt-1.5 font-mono opacity-70">JPG / PNG · AI PPE SCANNER LIVE</p>
            <p className="text-[10px] text-[color:var(--muted-2)] mt-4 font-mono uppercase tracking-widest">
              {projectId ? `TARGET: ${projectId}` : "NO TARGET SPECIFIED"}
            </p>
          </div>
        </label>
      )}

      {isUploading && (
        <div className="py-8 space-y-2">
          {log.map((entry, i) => (
            <div key={i} className="flex gap-3 fade-in">
              <CheckCircle2 className="w-4 h-4 text-[color:var(--primary)] mt-0.5 shrink-0" />
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--primary)]">{entry.step}</p>
                <p className="text-sm">{entry.message}</p>
              </div>
            </div>
          ))}
          <div className="flex items-center gap-2 text-[color:var(--muted)]">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span className="text-xs">Running model…</span>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-[color:var(--danger-soft)] border border-[color:var(--danger)]/30 px-4 py-3 text-sm text-[color:var(--danger)]">
          <p className="font-semibold">Analysis failed</p>
          <p className="text-xs mt-1 text-[color:var(--danger)]/80">{error}</p>
          <button onClick={reset} className="btn btn-secondary mt-3">Try again</button>
        </div>
      )}

      {result && (
        <div className="space-y-4 fade-in">
          <div className="flex items-center gap-3">
            {result.violation_detected ? (
              <span className="chip chip-danger"><AlertTriangle className="w-3 h-3" /> {result.severity}</span>
            ) : (
              <span className="chip chip-success"><CheckCircle2 className="w-3 h-3" /> Compliant</span>
            )}
            <p className="text-xs text-[color:var(--muted)]">
              {result.object_count} detections · threshold {result.ppe_confidence_threshold}
            </p>
          </div>

          {result.output_image && (
            <div className="rounded-lg overflow-hidden border border-[color:var(--border)] bg-black/40">
              <img src={assetUrl(result.output_image)!} alt="YOLO output" className="w-full max-h-72 object-contain" />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 text-xs">
            <Field label="Contractor" value={result.attribution.contractor ?? "(unattributed)"} />
            <Field label="Site" value={result.attribution.site ?? "(unattributed)"} />
            <Field label="Violations" value={result.violations.length > 0 ? result.violations.join(", ") : "None"} />
            <Field label="File" value={result.filename} />
          </div>

          {result.objects.length > 0 && (
            <details className="surface-elev p-3">
              <summary className="text-[11px] font-semibold cursor-pointer text-[color:var(--muted)] uppercase tracking-widest">
                All detected objects ({result.objects.length})
              </summary>
              <div className="mt-3 space-y-1 max-h-40 overflow-y-auto scroll-thin">
                {result.objects.map((o, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="flex items-center gap-2">
                      <ImageIcon className="w-3 h-3 text-[color:var(--muted)]" />
                      {o.label}
                    </span>
                    <span className="font-mono text-[color:var(--muted)]">{o.confidence.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </details>
          )}

          {result.legal_notice?.available && result.legal_notice.text && (
            <div className="surface-elev p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)] mb-2">
                Mistral-7B compliance notice
              </p>
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap font-mono max-h-60 overflow-y-auto scroll-thin">{result.legal_notice.text}</pre>
            </div>
          )}
          {result.legal_notice && !result.legal_notice.available && (
            <p className="text-[11px] text-[color:var(--muted-2)] italic">Notice generation unavailable: {result.legal_notice.reason}</p>
          )}
          {!result.legal_notice && !result.violation_detected && (
            <p className="text-[11px] text-[color:var(--muted)]">No notice generated — site appears compliant.</p>
          )}

          <button onClick={reset} className="btn btn-secondary w-full">Analyze another photo</button>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-[color:var(--muted)]">{label}</p>
      <p className="text-xs font-semibold mt-1 break-words">{value}</p>
    </div>
  );
}
