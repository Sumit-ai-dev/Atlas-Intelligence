"""
orchestrator.py
===============
Atlas Orchestrator — Phase 2.

Combines all module outputs into a canonical Assurance Cycle envelope.
This is a pure data-assembly step — no risk computation, no cross-evidence,
no approvals. Those belong to later phases.

Public API
----------
build_assurance_cycle(
    project,
    satellite_result,
    dpr_result,
    ncri_result,
    context_result,
) -> dict

The returned dict is the canonical "assurance cycle" shape. Callers are
responsible for stamping cycle_id and project_id before persisting.
"""

from __future__ import annotations

import datetime
from typing import Any


def build_assurance_cycle(
    project:               dict[str, Any],
    satellite_result:      dict[str, Any] | None = None,
    dpr_result:            dict[str, Any] | None = None,
    ncri_result:           dict[str, Any] | None = None,
    context_result:        dict[str, Any] | None = None,
    cross_evidence_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Assemble a canonical Assurance Cycle envelope.

    Each module slot is optional (None if that module has not run yet).
    cross_evidence_result is the output of cross_evidence.evaluate().

    Returns
    -------
    {
        "cycle_id":         None,          # stamped by save_assurance_cycle
        "project_id":       str,
        "timestamp":        ISO-8601 str,

        "satellite":        dict | None,
        "dpr":              dict | None,
        "ncri":             dict | None,
        "context":          dict | None,
        "cross_evidence":   list | None,   # Phase 3 — findings list

        "assurance_status": "COMPLETED"
    }
    """
    project_id = project.get("id") or project.get("project_id") or "UNKNOWN"
    timestamp  = datetime.datetime.utcnow().isoformat() + "Z"

    # Unwrap cross_evidence_result: orchestrator stores the findings list,
    # not the outer {"cross_evidence_findings": [...]} wrapper.
    ce_findings: list | None = None
    if cross_evidence_result is not None:
        ce_findings = cross_evidence_result.get("cross_evidence_findings")

    from unified_risk import compute_unified_risk
    unified_risk_val = compute_unified_risk(
        satellite_result=satellite_result,
        dpr_result=dpr_result,
        ncri_result=ncri_result,
        context_result=context_result,
        cross_evidence_result=cross_evidence_result
    )

    return {
        "cycle_id":         None,
        "project_id":       project_id,
        "timestamp":        timestamp,

        "satellite":        satellite_result,
        "dpr":              dpr_result,
        "ncri":             ncri_result,
        "context":          context_result,
        "cross_evidence":   ce_findings,
        "unified_risk":     unified_risk_val,
        "governance": {
            "status":       "PENDING_REVIEW",
            "actions":      []
        },

        "assurance_status": "COMPLETED",
    }

