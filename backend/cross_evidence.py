"""
cross_evidence.py
=================
Cross-Evidence Intelligence Engine — Phase 3.

Correlates evidence from satellite, DPR, and NCRI using declarative rules
read exclusively from policies/cross_evidence_rules.json.

Public API
----------
evaluate(satellite_result, dpr_result, ncri_result) -> dict

Returns
-------
{
    "cross_evidence_findings": [
        {
            "rule_id":            str,
            "title":              str,
            "summary":            str,
            "severity":           str,
            "confidence":         str,
            "supporting_modules": [str, ...],
            "recommendations":    [str, ...],
        },
        ...
    ]
}

Design rules
------------
- Reads ONLY from policies/cross_evidence_rules.json — no hardcoded logic.
- Never raises. Returns {"cross_evidence_findings": []} on any failure.
- Supports all condition types in the schema:
    satellite_status       list[str]   — status must be in list
    dpr_risk_level         list[str]   — verdict must be in list
    forensics_tampering_detected bool  — exact boolean match
    ppe_compliance_pct_below  int      — pct < threshold triggers
    satellite_activity_pct_below int   — pct < threshold triggers
    requires_rules         list[str]   — all listed rule_ids must have fired first
- Rules are evaluated in declaration order; composite rules (requires_rules)
  can therefore depend on earlier simple rules in the same pass.
"""

from __future__ import annotations

import logging
from typing import Any

import policy_loader

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Evidence extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_evidence(
    satellite_result: dict | None,
    dpr_result:       dict | None,
    ncri_result:      dict | None,
) -> dict:
    """
    Normalise heterogeneous module outputs into a flat evidence dict
    used for rule evaluation.

    All keys default to safe sentinel values so condition evaluators
    never receive KeyError / None.
    """
    ev: dict[str, Any] = {
        # Satellite
        "satellite_status":             "",
        "satellite_activity_pct":       100.0,   # assume full activity → no alarm
        # DPR
        "dpr_risk_level":               "",
        # NCRI / forensics
        "forensics_tampering_detected": False,
        "ppe_compliance_pct":           100.0,   # assume full compliance → no alarm
    }

    if satellite_result:
        ev["satellite_status"] = str(satellite_result.get("status") or "")
        try:
            ev["satellite_activity_pct"] = float(
                satellite_result.get("construction_activity_pct", 100)
            )
        except (TypeError, ValueError):
            pass

    if dpr_result:
        # dpr_result may be the orchestrator-shaped dict {"snapshot": …, "analysis": …}
        # or a flat analysis dict — support both.
        analysis = dpr_result.get("analysis", dpr_result)
        ev["dpr_risk_level"] = str(analysis.get("verdict") or "")

    if ncri_result:
        ev["forensics_tampering_detected"] = bool(
            ncri_result.get("tampering_detected", False)
        )
        try:
            ev["ppe_compliance_pct"] = float(
                ncri_result.get("ppe_compliance_pct", 100)
            )
        except (TypeError, ValueError):
            pass

    return ev


# ─────────────────────────────────────────────────────────────────────────────
# Single-rule evaluator
# ─────────────────────────────────────────────────────────────────────────────

def _rule_fires(
    rule:           dict,
    evidence:       dict,
    fired_rule_ids: set[str],
) -> bool:
    """
    Return True if every condition in the rule is satisfied by evidence.
    fired_rule_ids is the set of rule_ids that have already fired in this
    evaluation pass (used for requires_rules composite conditions).
    """
    conds = rule.get("conditions", {})

    for key, value in conds.items():

        if key == "satellite_status":
            # value is a list of acceptable status strings
            if evidence.get("satellite_status") not in value:
                return False

        elif key == "dpr_risk_level":
            if evidence.get("dpr_risk_level") not in value:
                return False

        elif key == "forensics_tampering_detected":
            if evidence.get("forensics_tampering_detected") != value:
                return False

        elif key == "ppe_compliance_pct_below":
            # fires when observed pct is STRICTLY below the threshold
            if evidence.get("ppe_compliance_pct", 100.0) >= float(value):
                return False

        elif key == "satellite_activity_pct_below":
            if evidence.get("satellite_activity_pct", 100.0) >= float(value):
                return False

        elif key == "requires_rules":
            # All listed rule_ids must have fired earlier in this pass
            for req_id in value:
                if req_id not in fired_rule_ids:
                    return False

        # Unknown condition keys are silently ignored (forward-compatible).

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Explainability helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_triggered_by(rule: dict, evidence: dict, findings: list[dict]) -> list[dict[str, str]]:
    """
    Return a list of trigger sources (module and signal) that caused the rule to fire.
    Recursively pulls triggers for compound rules (requires_rules).
    """
    triggered_by = []
    conds = rule.get("conditions", {})

    if "satellite_status" in conds:
        val = evidence.get("satellite_status") or (conds["satellite_status"][0] if conds["satellite_status"] else "")
        triggered_by.append({"module": "satellite", "signal": val})

    if "dpr_risk_level" in conds:
        val = evidence.get("dpr_risk_level") or (conds["dpr_risk_level"][0] if conds["dpr_risk_level"] else "")
        triggered_by.append({"module": "dpr", "signal": val})

    if "forensics_tampering_detected" in conds:
        triggered_by.append({"module": "forensics", "signal": "TAMPERING_DETECTED"})

    if "ppe_compliance_pct_below" in conds:
        triggered_by.append({"module": "ppe", "signal": "NON_COMPLIANT"})

    if "satellite_activity_pct_below" in conds:
        triggered_by.append({"module": "satellite", "signal": "LOW_ACTIVITY"})

    if "requires_rules" in conds:
        for req_id in conds["requires_rules"]:
            for prev_f in findings:
                if prev_f.get("rule_id") == req_id:
                    for trigger in prev_f.get("triggered_by", []):
                        if trigger not in triggered_by:
                            triggered_by.append(trigger)

    return triggered_by


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

_NULL_RESULT: dict = {"cross_evidence_findings": []}


def evaluate(
    satellite_result: dict | None = None,
    dpr_result:       dict | None = None,
    ncri_result:      dict | None = None,
) -> dict:
    """
    Evaluate all enabled cross-evidence rules against the supplied module outputs.

    Parameters
    ----------
    satellite_result : dict | None
        Output of analyze_project() from satellite.py, or None.
    dpr_result : dict | None
        Orchestrator DPR slot ({"snapshot": …, "analysis": …}) or raw
        analysis dict, or None.
    ncri_result : dict | None
        NCRI / forensics output, or None.

    Returns
    -------
    {"cross_evidence_findings": [list of fired-rule dicts]}
    """
    try:
        rules = policy_loader.get_cross_evidence_rules()
        if not rules:
            return _NULL_RESULT

        evidence = _extract_evidence(satellite_result, dpr_result, ncri_result)
        findings: list[dict] = []
        fired_ids: set[str] = set()

        for rule in rules:
            rule_id = rule.get("rule_id", "")
            if not rule_id:
                continue

            if _rule_fires(rule, evidence, fired_ids):
                fired_ids.add(rule_id)
                triggered_by = _get_triggered_by(rule, evidence, findings)
                findings.append({
                    "rule_id":            rule_id,
                    "title":              rule.get("title", ""),
                    "summary":            rule.get("narrative", ""),
                    "severity":           rule.get("severity", "LOW"),
                    "confidence":         rule.get("confidence", "LOW"),
                    "supporting_modules": rule.get("evidence_sources", []),
                    "recommendations":    rule.get("recommendations", []),
                    "triggered_by":       triggered_by,
                })

        return {"cross_evidence_findings": findings}

    except Exception as exc:
        logger.warning("[cross_evidence] Evaluation failed: %s — returning empty", exc)
        return _NULL_RESULT

