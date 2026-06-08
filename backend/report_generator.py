"""
report_generator.py
===================
Assurance Report Generation Engine — Phase 6.

Generates a structured report object from hydrated cycle data
entirely in-memory (Option B/Immutability compliance) and renders
a browser-printable, high-contrast HTML report.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import policy_loader
import digital_twin

def generate_assurance_report(project_id: str, cycle_id: str) -> dict[str, Any]:
    """
    Generate a structured, in-memory assurance report object for a given
    project and cycle ID. Operating entirely from the Digital Twin source of truth.
    """
    # 1. Fetch hydrated cycle from the Digital Twin
    # We raise ValueError if not found, to be handled by the API layer
    projects = policy_loader.get_projects_registry()
    if project_id not in projects:
        raise ValueError(f"Unknown project_id: {project_id}")
    
    project_record = projects[project_id]
    cycles = digital_twin.load_project_cycles(project_id)
    target_cycle = None
    for c in cycles:
        if c.get("cycle_id") == cycle_id:
            target_cycle = c
            break
            
    if not target_cycle:
        raise ValueError(f"Cycle {cycle_id} not found for project {project_id}")

    # Generate timestamps and ID
    now_dt = datetime.datetime.utcnow()
    generated_at_str = now_dt.isoformat() + "Z"
    date_prefix = now_dt.strftime("%Y%m%d")
    
    # Extract cycle number suffix
    try:
        cycle_num = int(cycle_id.split("-")[1])
    except (IndexError, ValueError):
        cycle_num = 1
    report_id = f"RPT-{date_prefix}-{cycle_num:04d}"

    # Extract components safely
    satellite = target_cycle.get("satellite") or {}
    dpr = target_cycle.get("dpr") or {}
    dpr_snapshot = dpr.get("snapshot") or {}
    dpr_analysis = dpr.get("analysis") or {}
    ncri = target_cycle.get("ncri") or {}
    context = target_cycle.get("context") or {}
    cross_evidence = target_cycle.get("cross_evidence") or []
    unified_risk = target_cycle.get("unified_risk") or {}
    governance = target_cycle.get("governance") or {}
    
    # Executive Summary narrative logic
    gov_status = governance.get("status", "PENDING_REVIEW")
    risk_tier = unified_risk.get("tier", "PENDING REVIEW")
    
    gov_status_text_map = {
        "PENDING_REVIEW": "remain pending human review",
        "APPROVED": "have been formally approved by authorized human officers",
        "REINVESTIGATION_REQUESTED": "have resulted in a reinvestigation request",
        "OVERRIDDEN": "have overridden the recommendation under executive discretion"
    }
    gov_status_desc = gov_status_text_map.get(gov_status, "remain pending review")
    
    executive_narrative = (
        f"Atlas identified corroborated concerns requiring human review. "
        f"Unified risk was classified as {risk_tier}. Governance actions {gov_status_desc}."
    )

    # Context Adjustments data
    original_budget_cr = context.get("original_budget_cr", dpr_analysis.get("budget_cr", 0.0))
    adjusted_budget_cr = context.get("adjusted_budget_cr", original_budget_cr)
    budget_variance = context.get("budget_adjustment_pct", 0.0)
    original_duration_months = context.get("original_duration_months", dpr_analysis.get("time_gap_months", 0.0))
    adjusted_duration_months = context.get("adjusted_duration_months", original_duration_months)
    assumptions_used = context.get("assumptions_used", [])

    # Cross Evidence explainability text formatting
    ce_list = []
    for rule in cross_evidence:
        rule_id = rule.get("rule_id", "UNKNOWN")
        title = rule.get("title", "Unknown Rule")
        summary = rule.get("summary", "")
        severity = rule.get("severity", "MEDIUM")
        confidence = rule.get("confidence", "MEDIUM")
        triggered_by = rule.get("triggered_by", [])
        
        # Build explainability bullet details
        bullets = []
        for trigger in triggered_by:
            mod = trigger.get("module", "").upper()
            sig = trigger.get("signal", "").upper()
            bullets.append(f"{mod} \u2192 {sig}")
        explainability_str = f"Rule {rule_id} triggered because: " + ", ".join(bullets)
        
        ce_list.append({
            "rule_id": rule_id,
            "title": title,
            "summary": summary,
            "severity": severity,
            "confidence": confidence,
            "triggered_by": triggered_by,
            "explainability": explainability_str
        })

    # Recommendations Sourcing & Deduplication
    raw_recs = []
    # 1. From Investigations
    for inv in dpr_analysis.get("investigations", []):
        raw_recs.extend(inv.get("recommendations", []))
    # 2. From Cross Evidence
    for rule in cross_evidence:
        raw_recs.extend(rule.get("recommendations", []))
    # 3. From Governance
    if gov_status == "PENDING_REVIEW":
        raw_recs.append("Complete human review to verify risk anomalies and authorize disbursement.")
    elif gov_status == "REINVESTIGATION_REQUESTED":
        raw_recs.append("Initiate site reinvestigation to address contradictory evidence and update digital twin.")
    elif gov_status == "OVERRIDDEN":
        raw_recs.append("Ensure policy exception rationale is fully documented and audit records updated.")

    # Deduplicate keeping order
    seen = set()
    deduped_recs = []
    for r in raw_recs:
        if r not in seen:
            seen.add(r)
            deduped_recs.append(r)

    # Categorize recommendations
    immediate_actions = []
    escalation_actions = []
    monitoring_actions = []
    
    immediate_keywords = [
        "immediately", "halt", "suspend", "freeze", "stop-work", "deduct", "ipc", "cvc", "cbi", "police", "confiscate", "reduce", "stop work"
    ]
    escalation_keywords = [
        "escalate", "ministry", "director", "ccea", "nhai", "morth", "statutory", "authority", "chief", "technical", "cte"
    ]
    
    for r in deduped_recs:
        r_lower = r.lower()
        if any(kw in r_lower for kw in immediate_keywords):
            immediate_actions.append(r)
        elif any(kw in r_lower for kw in escalation_keywords):
            escalation_actions.append(r)
        else:
            monitoring_actions.append(r)

    # Assemble report schema object
    report = {
        "report_metadata": {
            "report_id": report_id,
            "generated_at": generated_at_str,
            "generated_from_cycle": cycle_id
        },
        "section_1_executive_summary": {
            "project_name": project_record.get("name"),
            "cycle_id": cycle_id,
            "generated_at": generated_at_str,
            "governance_status": gov_status,
            "unified_assurance_score": unified_risk.get("score", 0),
            "attention_tier": risk_tier,
            "summary_text": executive_narrative
        },
        "section_2_project_overview": {
            "project_id": project_id,
            "project_name": project_record.get("name"),
            "location": f"{project_record.get('location', [0.0, 0.0])[0]}, {project_record.get('location', [0.0, 0.0])[1]}",
            "cycle_timestamp": target_cycle.get("timestamp", target_cycle.get("created_at")),
            "assurance_status": target_cycle.get("assurance_status", "COMPLETED")
        },
        "section_3_dpr_intelligence": {
            "risk_verdict": dpr_analysis.get("verdict", "LOW_RISK"),
            "budget": f"{dpr_analysis.get('budget_cr', 0.0):.2f} Cr" if "budget_cr" in dpr_analysis else "N/A",
            "time_gap": f"{dpr_analysis.get('time_gap_months', 0.0):.1f} months" if "time_gap_months" in dpr_analysis else "N/A",
            "investigations": dpr_analysis.get("investigations", []),
            "key_findings": dpr_analysis.get("findings", [])
        },
        "section_4_satellite_intelligence": {
            "satellite_status": satellite.get("status", "NORMAL"),
            "ghost_alerts": "Ghost Activity detected contradicting reported progress" if satellite.get("status") == "GHOST_ALERT" else "None",
            "progress_indicators": {
                "reported_progress_pct": satellite.get("reported_progress_pct"),
                "satellite_actual_pct": satellite.get("satellite_actual_pct"),
                "discrepancy_pct": satellite.get("discrepancy_pct")
            },
            "construction_signals": {
                "construction_activity_pct": satellite.get("construction_activity_pct", 100.0),
                "ml_change_detection": satellite.get("ml_change_detection")
            }
        },
        "section_5_cross_evidence_intelligence": ce_list,
        "section_6_context_adjustments": {
            "original_budget": f"{original_budget_cr:.2f} Cr",
            "adjusted_budget": f"{adjusted_budget_cr:.2f} Cr",
            "variance": f"{budget_variance:+.1f}%" if isinstance(budget_variance, (int, float)) else str(budget_variance),
            "original_duration": f"{original_duration_months:.1f} months",
            "adjusted_duration": f"{adjusted_duration_months:.1f} months",
            "policy_assumptions_used": assumptions_used
        },
        "section_7_unified_assurance_score": {
            "score": unified_risk.get("score", 0),
            "attention_tier": risk_tier,
            "breakdown": unified_risk.get("breakdown", {}),
            "rationale": unified_risk.get("rationale", [])
        },
        "section_8_governance_actions": {
            "governance_status": gov_status,
            "timeline": sorted(governance.get("actions", []), key=lambda x: x.get("performed_at", ""), reverse=True)
        },
        "section_9_atlas_recommendations": {
            "immediate_actions": immediate_actions,
            "monitoring_actions": monitoring_actions,
            "escalation_actions": escalation_actions
        },
        "section_10_evidence_provenance": {
            "dpr_file_name": dpr_snapshot.get("file_name", "N/A"),
            "sha256": dpr_snapshot.get("sha256", "N/A"),
            "evidence_sources": [
                "DPR Document Regulatory Feature Extraction",
                "SAR / RGB Multi-spectral Satellite Imagery",
                "GSTIN Government Contractor Registry Lookups",
                "NCRI Active Infractions & Violations Ledger",
                "ChromaDB Semantic Compliance Case Search"
            ],
            "cycle_timestamp": target_cycle.get("timestamp", target_cycle.get("created_at")),
            "report_generation_timestamp": generated_at_str,
            "statement": "Atlas recommendations are advisory. Final decisions remain under human governance."
        }
    }

    return report


def render_html_report(report: dict[str, Any]) -> str:
    """
    Renders the structured report object as browser-printable HTML.
    Designed with serif styling, clean page breaks, and black-on-white layout.
    """
    meta = report["report_metadata"]
    s1 = report["section_1_executive_summary"]
    s2 = report["section_2_project_overview"]
    s3 = report["section_3_dpr_intelligence"]
    s4 = report["section_4_satellite_intelligence"]
    s5 = report["section_5_cross_evidence_intelligence"]
    s6 = report["section_6_context_adjustments"]
    s7 = report["section_7_unified_assurance_score"]
    s8 = report["section_8_governance_actions"]
    s9 = report["section_9_atlas_recommendations"]
    s10 = report["section_10_evidence_provenance"]

    # Format Status badges
    def get_badge_class(status: str) -> str:
        s = status.upper()
        if "APPROVE" in s:
            return "badge-green"
        if "REINVESTIGATE" in s or "LAG" in s or "MODERATE" in s or "WARN" in s:
            return "badge-amber"
        if "OVERRIDE" in s or "HIGH" in s or "CRITICAL" in s or "FRAUD" in s:
            return "badge-orange"
        return "badge-blue"

    # Governance Actions timeline rows HTML
    gov_rows = ""
    if s8["timeline"]:
        for act in s8["timeline"]:
            act_type = act.get("action_type", "").replace("_", " ").title()
            perf_at = act.get("performed_at", "")
            try:
                perf_date = datetime.datetime.fromisoformat(perf_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                perf_date = perf_at
            
            notes_html = f"<div class='timeline-notes'><strong>Notes:</strong> {act.get('notes')}</div>" if act.get("notes") else ""
            gov_rows += f"""
            <div class="timeline-item">
                <div class="timeline-header">
                    <span class="timeline-badge {get_badge_class(act.get("action_type", ""))}">
                        {act_type}
                    </span>
                    <span class="timeline-time">[{perf_date}]</span>
                </div>
                <div class="timeline-body">
                    <p><strong>By:</strong> {act.get("performed_by")}</p>
                    <p><strong>Reason:</strong> {act.get("reason")}</p>
                    {notes_html}
                </div>
            </div>
            """
    else:
        gov_rows = "<p class='no-data'>No governance actions recorded for this cycle.</p>"

    # Investigations HTML
    inv_cards = ""
    if s3["investigations"]:
        for inv in s3["investigations"]:
            findings_li = "".join([f"<li>{f}</li>" for f in inv.get("supporting_findings", [])])
            recs_li = "".join([f"<li>{r}</li>" for r in inv.get("recommendations", [])])
            evidence_p = "".join([f"<p class='evidence-excerpt'>&ldquo;{ev}&rdquo;</p>" for ev in inv.get("evidence", [])])
            
            inv_cards += f"""
            <div class="sub-card">
                <div class="flex-between">
                    <h4>{inv.get("title")}</h4>
                    <div>
                        <span class="badge {get_badge_class(inv.get("severity"))}">Severity: {inv.get("severity")}</span>
                        <span class="badge {get_badge_class(inv.get("confidence"))}">Confidence: {inv.get("confidence")}</span>
                    </div>
                </div>
                <p class="summary-para">{inv.get("summary")}</p>
                
                <div class="findings-evidence-grid">
                    <div>
                        <strong>Supporting Violations:</strong>
                        <ul class="mini-list">
                            {findings_li}
                        </ul>
                    </div>
                    <div>
                        <strong>Recommendations:</strong>
                        <ul class="mini-list">
                            {recs_li}
                        </ul>
                    </div>
                </div>
                
                <div style="margin-top: 8px;">
                    <strong>ChromaDB Semantically Matched Evidence:</strong>
                    {evidence_p}
                </div>
            </div>
            """
    else:
        inv_cards = "<p class='no-data'>No environmental, financial, or execution violations detected by DPR scanner.</p>"

    # Key Findings HTML
    findings_list_html = ""
    if s3["key_findings"]:
        findings_list_html = "<ul class='standard-list'>" + "".join([f"<li>{f}</li>" for f in s3["key_findings"]]) + "</ul>"
    else:
        findings_list_html = "<p class='no-data'>No individual findings triggered.</p>"

    # Cross evidence HTML
    ce_cards = ""
    if s5:
        for ce in s5:
            ce_recs = "".join([f"<li>{r}</li>" for r in ce.get("recommendations", [])]) if "recommendations" in ce else ""
            ce_cards += f"""
            <div class="sub-card">
                <div class="flex-between">
                    <h4>{ce['rule_id']}: {ce['title']}</h4>
                    <div>
                        <span class="badge {get_badge_class(ce['severity'])}">Severity: {ce['severity']}</span>
                        <span class="badge {get_badge_class(ce['confidence'])}">Confidence: {ce['confidence']}</span>
                    </div>
                </div>
                <p class="summary-para">{ce['summary']}</p>
                <div class="explainability-box">
                    <strong>Explainability Trace:</strong>
                    <code>{ce['explainability']}</code>
                </div>
            </div>
            """
    else:
        ce_cards = "<p class='no-data'>No cross-evidence anomalies matched during this cycle.</p>"

    # Assumptions HTML
    assumptions_li = "".join([f"<li>{a}</li>" for a in s6["policy_assumptions_used"]]) if s6["policy_assumptions_used"] else "<li>None</li>"

    # Rationale HTML
    rationale_li = "".join([f"<li>{r}</li>" for r in s7["rationale"]])

    # Recommendations HTML lists
    immediate_li = "".join([f"<li>{r}</li>" for r in s9["immediate_actions"]]) if s9["immediate_actions"] else "<li>No immediate actions flagged.</li>"
    escalation_li = "".join([f"<li>{r}</li>" for r in s9["escalation_actions"]]) if s9["escalation_actions"] else "<li>No escalation actions flagged.</li>"
    monitoring_li = "".join([f"<li>{r}</li>" for r in s9["monitoring_actions"]]) if s9["monitoring_actions"] else "<li>No monitoring actions flagged.</li>"

    # Evidence sources HTML
    sources_li = "".join([f"<li>{s}</li>" for s in s10["evidence_sources"]])

    # Time values format
    try:
        report_timestamp_formatted = datetime.datetime.fromisoformat(meta["generated_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
        cycle_timestamp_formatted = datetime.datetime.fromisoformat(s10["cycle_timestamp"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        report_timestamp_formatted = meta["generated_at"]
        cycle_timestamp_formatted = s10["cycle_timestamp"]

    # HTML document template
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Atlas Assurance Report - {meta['report_id']}</title>
    <style>
        /* Base typography - Georgia for official headings, system-ui for high readability */
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 13px;
            line-height: 1.5;
            color: #1a1a1a;
            background-color: #ffffff;
            margin: 0;
            padding: 30px;
        }}

        h1, h2, h3, h4 {{
            font-family: "Georgia", "Times New Roman", Times, serif;
            color: #0f172a;
            margin-top: 0;
        }}

        h1 {{
            font-size: 24px;
            border-bottom: 2px solid #0f172a;
            padding-bottom: 8px;
            margin-bottom: 20px;
        }}

        h2 {{
            font-size: 16px;
            color: #1e293b;
            border-bottom: 1px solid #cbd5e1;
            padding-bottom: 6px;
            margin-top: 24px;
            margin-bottom: 12px;
            page-break-after: avoid;
        }}

        h3 {{
            font-size: 14px;
            margin-top: 16px;
            margin-bottom: 8px;
            color: #334155;
        }}

        h4 {{
            font-size: 13px;
            margin: 0;
            color: #475569;
        }}

        p {{
            margin: 0 0 10px 0;
        }}

        /* Document header metadata table */
        .doc-header-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
            font-size: 11px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 12px 16px;
            border-radius: 6px;
        }}

        .doc-header-grid div p {{
            margin-bottom: 4px;
        }}

        /* Badge design - pure CSS */
        .badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .badge-blue {{ background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }}
        .badge-green {{ background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }}
        .badge-amber {{ background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }}
        .badge-orange {{ background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa; }}

        /* Main sections cards */
        .section-card {{
            margin-bottom: 20px;
            page-break-inside: avoid;
        }}

        .executive-box {{
            background: #f8fafc;
            border-left: 4px solid #1e293b;
            padding: 16px;
            margin-bottom: 20px;
            font-size: 13px;
            border-radius: 0 6px 6px 0;
        }}
        
        .executive-box.APPROVED {{ border-left-color: #16803d; }}
        .executive-box.REINVESTIGATION_REQUESTED {{ border-left-color: #b45309; }}
        .executive-box.OVERRIDDEN {{ border-left-color: #c2410c; }}

        .sub-card {{
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 12px 16px;
            margin-bottom: 12px;
            background: #ffffff;
            page-break-inside: avoid;
        }}

        .flex-between {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}

        .summary-para {{
            font-size: 12px;
            color: #4b5563;
            margin-bottom: 10px;
        }}

        .findings-evidence-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-top: 8px;
            font-size: 11px;
        }}

        .evidence-excerpt {{
            font-family: Consolas, Monaco, monospace;
            font-size: 10px;
            background: #f1f5f9;
            padding: 6px;
            border-left: 2px solid #94a3b8;
            margin: 6px 0;
            color: #334155;
        }}

        .explainability-box {{
            background: #fafafa;
            border: 1px solid #eaeaea;
            padding: 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 10px;
            margin-top: 6px;
        }}

        /* Data list and tables styling */
        ul.standard-list, ul.mini-list {{
            margin: 0;
            padding-left: 20px;
        }}

        ul.standard-list li {{
            margin-bottom: 6px;
        }}

        ul.mini-list li {{
            margin-bottom: 4px;
            font-size: 11px;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            margin-bottom: 16px;
        }}

        .data-table th, .data-table td {{
            border: 1px solid #e2e8f0;
            padding: 8px 12px;
            text-align: left;
        }}

        .data-table th {{
            background-color: #f8fafc;
            color: #334155;
            font-weight: bold;
        }}

        .data-grid-3 {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 16px;
            margin-bottom: 16px;
        }}

        .data-grid-3 div {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
        }}

        .data-grid-3 div span {{
            display: block;
            font-size: 10px;
            color: #64748b;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}

        .data-grid-3 div strong {{
            font-size: 14px;
            color: #0f172a;
        }}

        /* Governance timeline styling */
        .timeline-item {{
            border-left: 2px solid #e2e8f0;
            margin-left: 10px;
            padding-left: 16px;
            position: relative;
            margin-bottom: 16px;
            page-break-inside: avoid;
        }}

        .timeline-item::before {{
            content: "";
            position: absolute;
            left: -6px;
            top: 2px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #ffffff;
            border: 2px solid #94a3b8;
        }}

        .timeline-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }}

        .timeline-time {{
            font-size: 10px;
            color: #64748b;
            font-family: monospace;
        }}

        .timeline-body {{
            font-size: 11px;
            color: #334155;
        }}

        .timeline-body p {{
            margin: 0 0 2px 0;
        }}

        .timeline-notes {{
            margin-top: 4px;
            font-style: italic;
            background: #f8fafc;
            padding: 6px;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
        }}

        .no-data {{
            font-style: italic;
            color: #64748b;
            font-size: 12px;
            margin: 0;
        }}

        /* Recommendations styling */
        .recs-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
        }}

        .recs-column {{
            border: 1px solid #cbd5e1;
            border-top: 3px solid #0f172a;
            border-radius: 4px;
            padding: 12px;
            background: #ffffff;
            page-break-inside: avoid;
        }}

        .recs-column.immediate {{ border-top-color: #ef4444; }}
        .recs-column.escalation {{ border-top-color: #f97316; }}
        .recs-column.monitoring {{ border-top-color: #3b82f6; }}

        .recs-column h3 {{
            margin-top: 0;
            margin-bottom: 10px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 6px;
        }}

        .recs-column ul {{
            margin: 0;
            padding-left: 16px;
            font-size: 11px;
        }}

        .recs-column ul li {{
            margin-bottom: 6px;
        }}

        /* Provenance and Disclaimer footer */
        .provenance-card {{
            border-top: 1px solid #cbd5e1;
            padding-top: 16px;
            margin-top: 30px;
            font-size: 10px;
            color: #64748b;
            page-break-inside: avoid;
        }}

        .provenance-card ul {{
            margin: 4px 0 10px 0;
            padding-left: 16px;
        }}

        .disclaimer-statement {{
            font-style: italic;
            font-weight: bold;
            color: #475569;
            margin-bottom: 8px;
        }}

        .footer-line {{
            margin-top: 20px;
            text-align: center;
            font-size: 9px;
            color: #94a3b8;
            border-top: 1px dashed #cbd5e1;
            padding-top: 10px;
        }}

        /* PRINT CONFIGURATION */
        @media print {{
            body {{
                padding: 0;
                font-size: 12px;
            }}
            
            h1 {{
                font-size: 20px;
            }}

            .section-card {{
                margin-bottom: 15px;
            }}

            .doc-header-grid {{
                background: none;
                border: 1px solid #94a3b8;
            }}

            .executive-box {{
                background: none;
                border: 1px solid #94a3b8;
                border-left: 4px solid #1e293b;
            }}

            .sub-card {{
                border: 1px solid #94a3b8;
                background: none;
            }}

            .recs-column {{
                border: 1px solid #94a3b8;
                border-top: 3px solid #1e293b;
                background: none;
            }}

            .recs-column.immediate {{ border-top-color: #ef4444; }}
            .recs-column.escalation {{ border-top-color: #f97316; }}
            .recs-column.monitoring {{ border-top-color: #3b82f6; }}

            .data-grid-3 div {{
                background: none;
                border: 1px solid #94a3b8;
            }}

            .timeline-notes {{
                background: none;
                border: 1px dashed #94a3b8;
            }}

            .page-break {{
                page-break-before: always;
            }}
        }}
    </style>
</head>
<body>

    <!-- Document Header Seal & Title -->
    <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 10px;">
        <div style="font-family: Georgia, serif; font-size: 10px; font-weight: bold; letter-spacing: 1px; color: #475569; text-transform: uppercase;">
            Atlas Assurance Intelligence Platform
        </div>
        <div style="font-family: monospace; font-size: 10px; color: #64748b;">
            CONFIDENTIAL // GOVERNANCE REVIEW
        </div>
    </div>

    <h1>Milestone Clearance Assurance Report</h1>

    <!-- SECTION 1: Executive Summary -->
    <div class="section-card">
        <div class="doc-header-grid">
            <div>
                <p><strong>Report Reference ID:</strong> {meta['report_id']}</p>
                <p><strong>Generated At:</strong> {report_timestamp_formatted}</p>
                <p><strong>Governance Status:</strong> <span class="badge {get_badge_class(s1['governance_status'])}">{s1['governance_status'].replace('_', ' ')}</span></p>
            </div>
            <div>
                <p><strong>Source Assurance Cycle:</strong> {meta['generated_from_cycle']}</p>
                <p><strong>Unified Assurance Score:</strong> {s1['unified_assurance_score']} / 100</p>
                <p><strong>Attention Tier:</strong> <span class="badge {get_badge_class(s1['attention_tier'])}">{s1['attention_tier']}</span></p>
            </div>
        </div>

        <h2>Section 1: Executive Summary</h2>
        <div class="executive-box {s1['governance_status']}">
            <p style="margin: 0; font-weight: 500; line-height: 1.6;">
                {s1['summary_text']}
            </p>
        </div>
    </div>

    <!-- SECTION 2: Project Overview -->
    <div class="section-card">
        <h2>Section 2: Project Overview</h2>
        <table class="data-table">
            <tr>
                <th style="width: 25%;">Project ID</th>
                <td style="width: 25%; font-family: monospace;">{s2['project_id']}</td>
                <th style="width: 25%;">Project Name</th>
                <td style="width: 25%;">{s2['project_name']}</td>
            </tr>
            <tr>
                <th>Location Coordinates</th>
                <td>{s2['location']}</td>
                <th>Cycle Timestamp</th>
                <td>{cycle_timestamp_formatted}</td>
            </tr>
            <tr>
                <th>Assurance Status</th>
                <td><span class="badge badge-green">{s2['assurance_status']}</span></td>
                <th>Authority / Registry</th>
                <td>National Infrastructure Projects Registry</td>
            </tr>
        </table>
    </div>

    <!-- SECTION 3: DPR Intelligence -->
    <div class="section-card">
        <h2>Section 3: DPR Intelligence</h2>
        <div class="data-grid-3">
            <div>
                <span>DPR Risk Verdict</span>
                <strong class="badge {get_badge_class(s3['risk_verdict'])}" style="font-size: 11px; margin-top: 4px;">
                    {s3['risk_verdict'].replace('_', ' ')}
                </strong>
            </div>
            <div>
                <span>Reported Budget</span>
                <strong>{s3['budget']}</strong>
            </div>
            <div>
                <span>Physical Execution Gap</span>
                <strong>{s3['time_gap']}</strong>
            </div>
        </div>

        <h3 style="margin-bottom: 8px;">CAG-Aligned Violation Investigations</h3>
        {inv_cards}

        <h3 style="margin-top: 14px; margin-bottom: 6px;">Key Textual Findings Extract</h3>
        {findings_list_html}
    </div>

    <!-- Page Break for print clarity -->
    <div class="page-break"></div>

    <!-- SECTION 4: Satellite Intelligence -->
    <div class="section-card">
        <h2>Section 4: Satellite Intelligence</h2>
        <table class="data-table">
            <tr>
                <th style="width: 30%;">Satellite Scanning Status</th>
                <td>
                    <span class="badge {get_badge_class(s4['satellite_status'])}">
                        {s4['satellite_status'].replace('_', ' ')}
                    </span>
                </td>
            </tr>
            <tr>
                <th>Ghost Activity Warning</th>
                <td>{s4['ghost_alerts']}</td>
            </tr>
        </table>

        <h3>Progress Indicators &amp; Physical Evidence</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Reported Value</th>
                    <th>Satellite Actual</th>
                    <th>Discrepancy Variance</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Milestone Execution Progress</td>
                    <td>{s4['progress_indicators']['reported_progress_pct'] if s4['progress_indicators']['reported_progress_pct'] is not None else "N/A"}%</td>
                    <td>{s4['progress_indicators']['satellite_actual_pct'] if s4['progress_indicators']['satellite_actual_pct'] is not None else "N/A"}%</td>
                    <td style="font-weight: bold; color: { '#15803d' if (s4['progress_indicators']['discrepancy_pct'] or 0) <= 10 else '#c2410c' };">
                        {s4['progress_indicators']['discrepancy_pct'] if s4['progress_indicators']['discrepancy_pct'] is not None else "N/A"}%
                    </td>
                </tr>
            </tbody>
        </table>

        <h3>Physical Construction Signals</h3>
        <table class="data-table">
            <tr>
                <th style="width: 40%;">SAR / RGB Activity Percentage</th>
                <td>{s4['construction_signals']['construction_activity_pct']}%</td>
            </tr>
            {"".join([f"<tr><th>ML Change detection parameter - {k.replace('_', ' ').title()}</th><td>{v}</td></tr>" for k, v in s4['construction_signals']['ml_change_detection'].items() if k not in ['rgb_baseline_image', 'rgb_current_image', 'change_heatmap', 'severity_meta', 'severity']]) if s4['construction_signals']['ml_change_detection'] else ""}
        </table>
    </div>

    <!-- SECTION 5: Cross-Evidence Intelligence -->
    <div class="section-card">
        <h2>Section 5: Cross-Evidence Intelligence</h2>
        <p class="summary-para" style="margin-bottom: 12px;">
            Atlas cross-references satellite data, document features, and forensic tampering signals to identify systematic compliance clusters.
        </p>
        {ce_cards}
    </div>

    <!-- SECTION 6: Context Adjustments -->
    <div class="section-card">
        <h2>Section 6: Context Adjustments</h2>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Parameter</th>
                    <th>Original / DPR Claimed</th>
                    <th>Policy-Adjusted (Expected)</th>
                    <th>Adjustment Variance</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Project Budget</strong></td>
                    <td>{s6['original_budget']}</td>
                    <td>{s6['adjusted_budget']}</td>
                    <td style="font-weight: bold;">{s6['variance']}</td>
                </tr>
                <tr>
                    <td><strong>Execution Duration</strong></td>
                    <td>{s6['original_duration']}</td>
                    <td>{s6['adjusted_duration']}</td>
                    <td>0.0 months (No Delta)</td>
                </tr>
            </tbody>
        </table>

        <h3 style="margin-top: 10px; margin-bottom: 6px;">Applied Context Policy Assumptions</h3>
        <ul class="standard-list">
            {assumptions_li}
        </ul>
    </div>

    <!-- SECTION 7: Unified Assurance Score -->
    <div class="section-card" style="page-break-inside: avoid;">
        <h2>Section 7: Unified Assurance Score</h2>
        <div style="display: flex; gap: 20px; align-items: flex-start; margin-bottom: 12px;">
            <div style="border: 2px solid #0f172a; padding: 16px; border-radius: 8px; text-align: center; min-width: 120px;">
                <span style="font-size: 10px; color: #64748b; text-transform: uppercase; display: block; margin-bottom: 4px;">Assurance Score</span>
                <strong style="font-size: 32px; color: #0f172a; font-family: Georgia, serif;">{s7['score']}</strong>
                <span style="font-size: 9px; color: #64748b; display: block; margin-top: 4px;">Risk Deducted: {100 - s7['score']} pts</span>
            </div>
            <div style="flex-grow: 1;">
                <p><strong>Risk Attention Tier:</strong> <span class="badge {get_badge_class(s7['attention_tier'])}">{s7['attention_tier']}</span></p>
                <p><strong>Rationale Synthesized:</strong></p>
                <ul class="standard-list" style="margin-top: 4px;">
                    {rationale_li}
                </ul>
            </div>
        </div>

        <h3>Assurance Deductions Breakdown</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Satellite Scans</th>
                    <th>DPR Violations</th>
                    <th>NCRI Ledger Score</th>
                    <th>Cross-Evidence Rules</th>
                    <th>Context Adjustment</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>-{s7['breakdown'].get('satellite', 0)} pts</td>
                    <td>-{s7['breakdown'].get('dpr', 0)} pts</td>
                    <td>-{s7['breakdown'].get('ncri', 0)} pts</td>
                    <td>-{s7['breakdown'].get('cross_evidence', 0)} pts</td>
                    <td>-{s7['breakdown'].get('context', 0)} pts</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Page Break for print clarity -->
    <div class="page-break"></div>

    <!-- SECTION 8: Governance Actions -->
    <div class="section-card">
        <h2>Section 8: Governance Actions &amp; Audit Trail</h2>
        <p class="summary-para">
            Chronological audit history of human decisions. Newest actions are shown first.
        </p>
        <div style="margin-top: 12px;">
            {gov_rows}
        </div>
    </div>

    <!-- SECTION 9: Atlas Recommendations -->
    <div class="section-card">
        <h2>Section 9: Atlas Policy-Driven Recommendations</h2>
        <p class="summary-para" style="margin-bottom: 12px;">
            Sourced and consolidated from investigation findings, cross-evidence rules, and current governance state.
        </p>
        <div class="recs-grid">
            <div class="recs-column immediate">
                <h3>Immediate Actions</h3>
                <ul>
                    {immediate_li}
                </ul>
            </div>
            <div class="recs-column escalation">
                <h3>Escalation Actions</h3>
                <ul>
                    {escalation_li}
                </ul>
            </div>
            <div class="recs-column monitoring">
                <h3>Monitoring Actions</h3>
                <ul>
                    {monitoring_li}
                </ul>
            </div>
        </div>
    </div>

    <!-- SECTION 10: Evidence Provenance & Statement -->
    <div class="provenance-card">
        <div class="disclaimer-statement">
            {s10['statement']}
        </div>
        <p><strong>Evidence Provenance Verification:</strong></p>
        <ul>
            <li><strong>DPR File Name:</strong> {s10['dpr_file_name']}</li>
            <li><strong>Document Cryptographic Hash (SHA-256):</strong> <code style="font-size: 10px;">{s10['sha256']}</code></li>
            <li><strong>Source Materials Evaluated:</strong></li>
            <ul>
                {sources_li}
            </ul>
        </ul>
        <p style="margin-top: 8px;">
            <strong>Cycle Capture Time:</strong> {cycle_timestamp_formatted} | 
            <strong>Report Generation Time:</strong> {report_timestamp_formatted}
        </p>
    </div>

    <!-- Footer Statement -->
    <div class="footer-line">
        <p>Atlas provides analytical recommendations derived from available evidence and policy assumptions. Final decisions remain under authorized human governance.</p>
        <p style="margin-top: 4px; font-weight: bold;">Generated by Atlas Assurance Intelligence Platform | Generated at: {report_timestamp_formatted}</p>
    </div>

</body>
</html>
"""
    return html
