"""
ncri_engine.py
==============
National Contractor Reliability Index (NCRI) — Governance Utility
Single source of truth for:
  - NCRI deduction weights
  - Severity classification thresholds
  - Severity badge metadata (colors, labels)
  - Eligibility tier calculation
  - Financial risk estimation (₹)
  - NCRI score aggregation

Imported by: main.py, agent.py
"""

from __future__ import annotations

import datetime
import json
import warnings
from pathlib import Path
from typing import Any

_BACKEND_DIR        = Path(__file__).parent
_STORAGE_LEDGER     = _BACKEND_DIR / "storage" / "audit_ledgers.json"
_LEGACY_LEDGER      = _BACKEND_DIR / "satellite_cache" / "audit_ledgers.json"

# ---------------------------------------------------------------------------
# NCRI Deduction Weights
# ---------------------------------------------------------------------------
DEDUCTIONS: dict[str, int] = {
    "IMAGE_TAMPERING": -50,   # ELA forensics fraud detection
    "GHOST_ALERT":     -40,   # DPR reported >> satellite verified (ghost billing)
    "LAG_WARNING":     -20,   # DPR progress << satellite actual (timeline delay)
    "SAFETY_VIOLATION": -10,  # Per unique PPE violation category detected by YOLO
}

# ---------------------------------------------------------------------------
# Severity Classification — Satellite Change Score
# (mean_change_score comes from change_detector_ml.detect_change_ml())
# ---------------------------------------------------------------------------
def classify_change_severity(mean_change_score: float, ela_flagged: bool = False) -> str:
    """Map ResNet-18 cosine-distance change score → severity tier."""
    if ela_flagged or mean_change_score > 0.50:
        return "FRAUD RISK"
    if mean_change_score > 0.30:
        return "CRITICAL"
    if mean_change_score > 0.10:
        return "MODERATE"
    return "LOW"


# ---------------------------------------------------------------------------
# Severity Classification — DPR Discrepancy %
# ---------------------------------------------------------------------------
def classify_dpr_severity(discrepancy_pct: float) -> str:
    """Map DPR vs satellite discrepancy percentage → severity tier."""
    if discrepancy_pct > 30:
        return "FRAUD RISK"
    if discrepancy_pct > 15:
        return "CRITICAL"
    if discrepancy_pct > 5:
        return "MODERATE"
    return "LOW"


# ---------------------------------------------------------------------------
# Severity Classification — ELA Tampering Score
# ---------------------------------------------------------------------------
def classify_ela_severity(tampering_score: float) -> str:
    """Map ELA tampering score (0–1) → severity tier."""
    if tampering_score > 0.70:
        return "FRAUD RISK"
    if tampering_score > 0.45:
        return "CRITICAL"
    if tampering_score > 0.25:
        return "MODERATE"
    return "LOW"


# ---------------------------------------------------------------------------
# Severity Badge Metadata
# (returned via API for direct consumption by frontend badge components)
# ---------------------------------------------------------------------------
SEVERITY_META: dict[str, dict[str, str]] = {
    "LOW": {
        "label":    "LOW",
        "color":    "#16a34a",   # green-600
        "bg":       "#dcfce7",   # green-100
        "dot":      "#4ade80",   # green-400
        "priority": "0",
    },
    "MODERATE": {
        "label":    "MODERATE",
        "color":    "#d97706",   # amber-600
        "bg":       "#fef3c7",   # amber-100
        "dot":      "#fbbf24",   # amber-400
        "priority": "1",
    },
    "CRITICAL": {
        "label":    "CRITICAL",
        "color":    "#dc2626",   # red-600
        "bg":       "#fee2e2",   # red-100
        "dot":      "#f87171",   # red-400
        "priority": "2",
    },
    "FRAUD RISK": {
        "label":    "FRAUD RISK",
        "color":    "#fca5a5",   # red-300 (on dark background)
        "bg":       "#7f1d1d",   # red-950
        "dot":      "#ef4444",   # red-500
        "priority": "3",
    },
}


def get_severity_meta(severity: str) -> dict[str, str]:
    """Safe accessor — falls back to LOW if unknown severity string passed."""
    return SEVERITY_META.get(severity, SEVERITY_META["LOW"])


# ---------------------------------------------------------------------------
# Eligibility Tier — based on NCRI score
# ---------------------------------------------------------------------------
_ELIGIBILITY_TIERS: list[dict[str, Any]] = [
    {
        "min_score":   90,
        "tier":        "A",
        "status":      "FULLY ELIGIBLE",
        "color":       "#16a34a",
        "badge_bg":    "#dcfce7",
        "description": (
            "Contractor is fully compliant and eligible for all public infrastructure "
            "tenders under CPWD guidelines."
        ),
    },
    {
        "min_score":   80,
        "tier":        "B",
        "status":      "UNDER ACTIVE WATCH",
        "color":       "#d97706",
        "badge_bg":    "#fef3c7",
        "description": (
            "Minor compliance gaps detected. Contractor is under government surveillance. "
            "Corrective action required within 30 days."
        ),
    },
    {
        "min_score":   60,
        "tier":        "C",
        "status":      "PROBATION / DISBURSEMENT FROZEN",
        "color":       "#dc2626",
        "badge_bg":    "#fee2e2",
        "description": (
            "Active violations recorded. All milestone disbursements are frozen pending "
            "physical site audit. Fines apply per Clause 14A."
        ),
    },
    {
        "min_score":   0,
        "tier":        "F",
        "status":      "BLACKLISTED & BANNED",
        "color":       "#fca5a5",
        "badge_bg":    "#7f1d1d",
        "description": (
            "Contractor is debarred from all public infrastructure bidding for 3 years. "
            "Legal action initiated under IPC Section 471 (evidence tampering)."
        ),
    },
]


def get_eligibility_status(score: int) -> dict[str, Any]:
    """Return eligibility tier dict for a given NCRI score."""
    for tier in _ELIGIBILITY_TIERS:
        if score >= tier["min_score"]:
            return {k: v for k, v in tier.items() if k != "min_score"}
    return {k: v for k, v in _ELIGIBILITY_TIERS[-1].items() if k != "min_score"}


# ---------------------------------------------------------------------------
# Financial Risk Calculator (₹)
# ---------------------------------------------------------------------------
def calculate_financial_risk(
    contract_value_inr: float,
    discrepancy_pct: float,
    disbursed_ratio: float,
) -> dict[str, Any]:
    """
    Estimate potential fund misuse in INR.

    Formula (transparent & auditor-defensible):
        Risk = Contract_Value × (Discrepancy% / 100) × Disbursed_Ratio

    Args:
        contract_value_inr:  Full sanctioned contract amount in ₹
        discrepancy_pct:     DPR-claimed minus satellite-verified progress (%)
        disbursed_ratio:     Fraction of total milestones already released (0–1)

    Returns:
        dict with amount_inr, amount_crore, display string, and severity
    """
    # Clamp inputs to sane ranges
    discrepancy_pct = max(0.0, min(discrepancy_pct, 100.0))
    disbursed_ratio = max(0.0, min(disbursed_ratio, 1.0))

    risk_inr = contract_value_inr * (discrepancy_pct / 100.0) * disbursed_ratio
    risk_crore = round(risk_inr / 1_00_00_000, 2)  # 1 Crore = 10,000,000

    if risk_crore <= 0:
        severity = "LOW"
        display = "₹0 (No discrepancy)"
    elif risk_crore < 1:
        severity = "LOW"
        display = f"₹{round(risk_crore * 100, 1)} L"   # show in Lakhs if < 1 Cr
    elif risk_crore < 10:
        severity = "MODERATE"
        display = f"₹{risk_crore} Cr"
    elif risk_crore < 50:
        severity = "CRITICAL"
        display = f"₹{risk_crore} Cr"
    else:
        severity = "FRAUD RISK"
        display = f"₹{risk_crore} Cr"

    return {
        "amount_inr":   round(risk_inr, 2),
        "amount_crore": risk_crore,
        "display":      display,
        "severity":     severity,
        "meta":         get_severity_meta(severity),
        "disclaimer":   (
            "Estimated based on DPR vs satellite telemetry variance. "
            "Subject to physical audit verification as per CPWD norms."
        ),
    }


# ---------------------------------------------------------------------------
# NCRI Score Aggregator
# ---------------------------------------------------------------------------
def calculate_ncri_score(violations: list[dict[str, Any]]) -> int:
    """
    Compute NCRI score from a list of active violation dicts.

    Each violation dict must have a "type" key matching DEDUCTIONS keys.
    Score is floored at 0 (cannot go negative).

    Example violation entry:
        {"type": "GHOST_ALERT", "date": "2025-03-12", "severity": "CRITICAL"}
    """
    score = 100
    for v in violations:
        deduction = DEDUCTIONS.get(v.get("type", ""), 0)
        score += deduction
    return max(0, score)


# ---------------------------------------------------------------------------
# Ledger Path Resolution (Phase 0 — NCRI Compatibility)
# ---------------------------------------------------------------------------

def _load_audit_ledgers() -> dict[str, Any]:
    """
    Load audit_ledgers.json with a dual-path fallback:

    Priority 1 — storage/audit_ledgers.json  (new canonical location)
    Priority 2 — satellite_cache/audit_ledgers.json  (legacy location)

    If the legacy path is used, a deprecation warning is emitted.
    Returns an empty dict if neither file exists.
    """
    if _STORAGE_LEDGER.exists():
        with open(_STORAGE_LEDGER, "r", encoding="utf-8") as f:
            return json.load(f)

    if _LEGACY_LEDGER.exists():
        warnings.warn(
            "[DEPRECATION] Using legacy satellite_cache/audit_ledgers.json. "
            "Migrate to storage/audit_ledgers.json.",
            DeprecationWarning,
            stacklevel=2,
        )
        with open(_LEGACY_LEDGER, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def _save_audit_ledgers(ledger: dict[str, Any]) -> None:
    """
    Save audit_ledgers.json to the canonical storage/ location.
    Creates the directory if it does not exist.
    """
    _STORAGE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_STORAGE_LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Ledger Mutation Helpers
# (called by main.py after each upload analysis to keep audit_ledgers.json
#  in sync with the latest governance events in real-time)
# ---------------------------------------------------------------------------

_RECOMMENDED_ACTIONS: dict[str, str] = {
    "IMAGE_TAMPERING":  "INITIATE_BLACKLIST_REVIEW",
    "GHOST_ALERT":      "FREEZE_DISBURSEMENT",
    "LAG_WARNING":      "ISSUE_SHOW_CAUSE_NOTICE",
    "SAFETY_VIOLATION": "ESCALATE_PHYSICAL_AUDIT",
}


def add_violation_to_ledger(
    ledger: dict[str, Any],
    project_id: str,
    violation_type: str,
    severity: str,
    description: str,
) -> None:
    """
    Append a new violation to active_violations and audit_ledger for the given
    project in-place.  The caller is responsible for writing the ledger to disk.
    """
    if project_id not in ledger:
        return  # project not registered — skip silently

    today = datetime.date.today().isoformat()
    project_data = ledger[project_id]

    # --- active_violations ---
    project_data.setdefault("active_violations", []).append({
        "type":               violation_type,
        "severity":           severity,
        "date":               today,
        "description":        description,
        "recommended_action": _RECOMMENDED_ACTIONS.get(violation_type, ""),
    })

    # --- audit_ledger (balanced running score) ---
    current_violations = project_data["active_violations"]
    new_score = calculate_ncri_score(current_violations)
    deduction = DEDUCTIONS.get(violation_type, 0)

    project_data.setdefault("audit_ledger", []).append({
        "date":          today,
        "type":          violation_type,
        "description":   description,
        "deduction":     deduction,
        "severity":      severity,
        "balance_after": new_score,
    })


def add_progress_to_timeline(
    ledger: dict[str, Any],
    project_id: str,
    month: str,
    reported_pct: float,
    actual_pct: float,
    discrepancy: float,
    severity: str,
) -> None:
    """
    Append a new satellite timeline node for the given project in-place.
    Field names match NcriTimelineEntry TypeScript type.
    The caller is responsible for writing the ledger to disk.
    """
    if project_id not in ledger:
        return

    today = datetime.date.today().isoformat()
    node = {
        "month":                    month or today,
        "dpr_claimed_pct":          round(reported_pct, 1),
        "satellite_verified_pct":   round(actual_pct, 1),
        "discrepancy":              round(discrepancy, 1),
        "severity":                 severity,
        "satellite_image":          None,  # populated by satellite.py when available
    }
    ledger[project_id].setdefault("timeline", []).append(node)

