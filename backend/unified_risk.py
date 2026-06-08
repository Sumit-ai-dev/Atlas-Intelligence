"""
unified_risk.py
===============
Unified Risk Engine — Phase 4.

Aggregates individual component risk signals into a single Atlas Assurance Score (0-100),
assigns an attention tier, computes the weight breakdown, and produces plain-language rationales.
Reads weights dynamically from policies/risk_weights.json.
"""

from __future__ import annotations

import logging
from typing import Any
import policy_loader

logger = logging.getLogger(__name__)

def compute_unified_risk(
    satellite_result: dict | None,
    dpr_result:       dict | None,
    ncri_result:      dict | None,
    context_result:   dict | None,
    cross_evidence_result: dict | None,
) -> dict[str, Any]:
    """
    Compute the unified risk score and attention tier for an Assurance Cycle.

    Parameters
    ----------
    satellite_result : dict | None
    dpr_result : dict | None
    ncri_result : dict | None
    context_result : dict | None
    cross_evidence_result : dict | None

    Returns
    -------
    {
        "score": 0-100,
        "tier": "LOW ATTENTION | MODERATE ATTENTION | HIGH ATTENTION | CRITICAL ATTENTION",
        "breakdown": {
            "satellite": int,
            "dpr": int,
            "ncri": int,
            "cross_evidence": int,
            "context": int
        },
        "rationale": [str, ...]
    }
    """
    try:
        # ── 1. Load weights policy ───────────────────────────────────────────
        weights_policy = policy_loader.get_risk_weights()
        comp_weights = weights_policy.get("component_weights", {})
        severity_scores = weights_policy.get("severity_scores", {})
        score_bands = weights_policy.get("score_bands", {})

        # Define weight components dynamically from policy
        dpr_w = float(comp_weights.get("dpr_rejection_probability", comp_weights.get("dpr", 0.0)))
        sat_w = float(comp_weights.get("satellite_discrepancy", comp_weights.get("satellite", 0.0)))
        ce_w  = float(comp_weights.get("cross_evidence_severity", comp_weights.get("cross_evidence", 0.0)))
        forensics_w = float(comp_weights.get("forensics_tampering", comp_weights.get("forensics", 0.0)))
        ppe_w = float(comp_weights.get("ppe_noncompliance", comp_weights.get("ppe", 0.0)))
        context_w = float(comp_weights.get("context_variance", comp_weights.get("context", 0.0)))

        # Sum up NCRI weight (forensics + ppe) for breakdown
        ncri_w = forensics_w + ppe_w

        # Normalize breakdown to sum to exactly 100%
        w_sum = dpr_w + sat_w + ce_w + ncri_w + context_w
        if w_sum <= 0:
            w_sum = 1.0

        dpr_pct = int(round((dpr_w / w_sum) * 100))
        sat_pct = int(round((sat_w / w_sum) * 100))
        ce_pct  = int(round((ce_w / w_sum) * 100))
        ncri_pct = int(round((ncri_w / w_sum) * 100))
        context_pct = 100 - (dpr_pct + sat_pct + ce_pct + ncri_pct)

        breakdown = {
            "satellite": sat_pct,
            "dpr": dpr_pct,
            "cross_evidence": ce_pct,
            "ncri": ncri_pct,
            "context": context_pct
        }

        # ── 2. Compute component scores (0 to 100 scale) ─────────────────────
        # A) DPR Risk Score
        # dpr_result can be orchestrator wrapper {"snapshot": ..., "analysis": ...} or raw analysis dict
        dpr_analysis = dpr_result.get("analysis", dpr_result) if dpr_result else {}
        rejection_prob = dpr_analysis.get("risk_score")
        if rejection_prob is None:
            rejection_prob = dpr_analysis.get("rejection_probability", 0.0)
        dpr_score = float(rejection_prob) * 100.0 if float(rejection_prob) <= 1.0 else float(rejection_prob)

        # B) Satellite Discrepancy Score
        sat_status = satellite_result.get("status", "NORMAL") if satellite_result else "NORMAL"
        sat_score = float(severity_scores.get("satellite_status", {}).get(sat_status, 0.0))

        # C) Cross-Evidence Severity Score
        # cross_evidence_result can be list of findings directly or wrapped in {"cross_evidence_findings": ...}
        ce_findings = []
        if cross_evidence_result:
            if isinstance(cross_evidence_result, dict):
                ce_findings = cross_evidence_result.get("cross_evidence_findings", [])
            elif isinstance(cross_evidence_result, list):
                ce_findings = cross_evidence_result

        ce_score = 0.0
        if ce_findings:
            ce_severity_map = severity_scores.get("cross_evidence_severity", {})
            finding_scores = []
            for f in ce_findings:
                sev = f.get("severity", "LOW")
                finding_scores.append(float(ce_severity_map.get(sev, 0.0)))
            ce_score = max(finding_scores) if finding_scores else 0.0

        # D) Forensics Tampering Score
        forensics_score = 0.0
        if ncri_result:
            tampering_score = ncri_result.get("tampering_score")
            if tampering_score is not None:
                forensics_score = float(tampering_score) * 100.0 if float(tampering_score) <= 1.0 else float(tampering_score)
            elif ncri_result.get("tampering_detected") is True:
                forensics_score = 100.0

        # E) PPE Noncompliance Score
        ppe_score = 0.0
        if ncri_result:
            # Non-compliance = 100 - compliance_pct
            ppe_compliance = ncri_result.get("ppe_compliance_pct")
            if ppe_compliance is not None:
                ppe_score = max(0.0, 100.0 - float(ppe_compliance))

        # F) Context Score
        context_band = context_result.get("tolerance_band", "LOW") if context_result else "LOW"
        context_score = {"HIGH": 100.0, "MEDIUM": 50.0, "LOW": 0.0}.get(context_band.upper(), 0.0)

        # ── 3. Weighted score sum ────────────────────────────────────────────
        weighted_sum = (
            dpr_score * dpr_w +
            sat_score * sat_w +
            ce_score * ce_w +
            forensics_score * forensics_w +
            ppe_score * ppe_w +
            context_score * context_w
        )
        total_w = dpr_w + sat_w + ce_w + forensics_w + ppe_w + context_w
        if total_w <= 0:
            total_w = 1.0

        final_score = int(round(weighted_sum / total_w))
        final_score = max(0, min(final_score, 100))

        # ── 4. Determine Attention Tier from policy score bands ──────────────
        tier = "LOW ATTENTION"
        for band_name, range_dict in score_bands.items():
            if range_dict.get("min", 0) <= final_score <= range_dict.get("max", 100):
                mapped_tiers = {
                    "LOW": "LOW ATTENTION",
                    "MEDIUM": "MODERATE ATTENTION",
                    "HIGH": "HIGH ATTENTION",
                    "CRITICAL": "CRITICAL ATTENTION"
                }
                band_upper = band_name.upper()
                if "ATTENTION" in band_upper:
                    tier = band_upper
                else:
                    tier = mapped_tiers.get(band_upper, band_upper + " ATTENTION")
                break

        # ── 5. Generate Rationale Bullets ────────────────────────────────────
        rationale = []

        # DPR Rationale
        dpr_verdict = dpr_analysis.get("verdict")
        if dpr_verdict == "HIGH_RISK":
            rationale.append("DPR classified HIGH RISK.")
        elif dpr_score > 50:
            rationale.append("DPR analysis indicated elevated risk.")

        # Satellite Rationale
        if sat_status == "GHOST_ALERT":
            rationale.append("Satellite ghost activity increased risk.")
        elif sat_status == "LAG_WARNING":
            rationale.append("Satellite telemetry indicated project execution lag.")
        elif satellite_result and satellite_result.get("discrepancy_pct", 0) > 10:
            rationale.append("Satellite telemetry showed discrepancy with reported progress.")

        # Cross-Evidence Rationale
        if ce_findings:
            rationale.append("Cross-evidence corroborated multiple modules.")

        # Forensics Rationale
        if ncri_result and ncri_result.get("tampering_detected") is True:
            rationale.append("Forensics detected image manipulation risk.")

        # PPE Rationale
        if ppe_score > 30:
            rationale.append("Safety compliance non-conformities detected on site.")

        # Context Rationale
        if context_result:
            rationale.append("Context adjustment reduced expected variance.")

        # Ensure at least one rationale fallback
        if not rationale:
            rationale.append("All measured governance signals fall within normal parameters.")

        return {
            "score": final_score,
            "tier": tier,
            "breakdown": breakdown,
            "rationale": rationale
        }

    except Exception as exc:
        logger.error("[unified_risk] Score computation failed: %s", exc)
        # Safe fallback
        return {
            "score": 0,
            "tier": "LOW ATTENTION",
            "breakdown": {
                "satellite": 30,
                "dpr": 35,
                "cross_evidence": 20,
                "ncri": 15,
                "context": 0
            },
            "rationale": [f"Risk calculation failed: {exc}"]
        }
