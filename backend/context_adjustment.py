"""
context_adjustment.py
=====================
Context Adjustment Layer — Phase 2.

Reads `policies/context_assumptions.json` and computes inflation-adjusted
budget and duration values for a DPR result.

Public API
----------
adjust_project_context(dpr_result, project) -> dict

Returns
-------
{
    "original_budget_cr":      float,
    "adjusted_budget_cr":      float,
    "budget_adjustment_pct":   float,

    "original_duration_months": int | float,
    "adjusted_duration_months": int | float,

    "assumptions_used": [str, ...]
}

Design rules
------------
- Uses ONLY policies/context_assumptions.json — no hardcoded rates.
- Never raises. On any failure returns original values unchanged.
- project.get("started") drives months_elapsed; falls back to 0.
- No project-ID-specific logic.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_POLICY_PATH = Path(__file__).parent / "policies" / "context_assumptions.json"

# ---------------------------------------------------------------------------
# Policy loader (lazy, cached per process)
# ---------------------------------------------------------------------------

_CACHED_POLICY: dict | None = None


def _load_policy() -> dict:
    """Load and cache context_assumptions.json. Returns {} on failure."""
    global _CACHED_POLICY
    if _CACHED_POLICY is not None:
        return _CACHED_POLICY
    try:
        with open(_POLICY_PATH, "r", encoding="utf-8") as f:
            _CACHED_POLICY = json.load(f)
    except Exception as exc:
        logger.warning("[context_adjustment] Could not load policy: %s", exc)
        _CACHED_POLICY = {}
    return _CACHED_POLICY


def _months_since(started_str: str | None) -> float:
    """Return months elapsed since project start date (ISO date string), or 0."""
    if not started_str:
        return 0.0
    try:
        started = datetime.date.fromisoformat(str(started_str)[:10])
        today   = datetime.date.today()
        delta   = (today - started).days
        return max(0.0, delta / 30.44)          # average days per month
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def adjust_project_context(
    dpr_result: dict[str, Any],
    project: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute context-adjusted budget and duration for a DPR result.

    Parameters
    ----------
    dpr_result : dict
        The dpr_analysis sub-dict (keys: budget_cr, time_gap_months, …).
    project : dict
        The project record from projects_registry.json.

    Returns
    -------
    Context adjustment dict. Never raises.
    """
    original_budget   = float(dpr_result.get("budget_cr") or 0.0)
    original_duration = float(dpr_result.get("time_gap_months") or 0.0)

    # Safe no-op defaults
    _null = {
        "original_budget_cr":       original_budget,
        "adjusted_budget_cr":       original_budget,
        "budget_adjustment_pct":    0.0,
        "original_duration_months": original_duration,
        "adjusted_duration_months": original_duration,
        "assumptions_used":         [],
    }

    try:
        policy = _load_policy()
        if not policy:
            return _null

        cpi_rate       = float(policy.get("cpi_annual_rate",      0.0))
        material_rate  = float(policy.get("material_escalation_rate", 0.0))
        labour_rate    = float(policy.get("labour_escalation_rate",  0.0))
        sources        = policy.get("_meta", {}).get("source", [])

        months_elapsed = _months_since(project.get("started"))
        years_elapsed  = months_elapsed / 12.0

        if years_elapsed <= 0:
            return _null

        # ── Budget adjustment: weighted escalation ───────────────────────
        # Weights: 40% material, 35% labour, 25% CPI (governance standard mix)
        composite_annual_rate = (
            0.40 * material_rate
            + 0.35 * labour_rate
            + 0.25 * cpi_rate
        )
        escalation_factor     = (1.0 + composite_annual_rate) ** years_elapsed
        adjusted_budget       = original_budget * escalation_factor
        budget_adjustment_pct = round((escalation_factor - 1.0) * 100, 2)

        # ── Duration: no escalation formula here — reported as-is ───────
        # The time_gap_months is already an observed delay; we do not
        # "adjust" it but preserve it unchanged for downstream cross-evidence.
        adjusted_duration = original_duration

        # ── Assumptions provenance ───────────────────────────────────────
        assumptions: list[str] = []
        if sources:
            assumptions = [str(s) for s in sources]
        else:
            assumptions = [
                f"CPI-Construction: {cpi_rate*100:.1f}% p.a.",
                f"Material escalation: {material_rate*100:.1f}% p.a.",
                f"Labour escalation: {labour_rate*100:.1f}% p.a.",
            ]

        note_template = policy.get("context_note_template", "")
        if note_template:
            note = note_template.format(
                months_elapsed=round(months_elapsed),
                escalation_pct=budget_adjustment_pct,
                tolerance="±5",
            )
            assumptions.append(f"Context note: {note}")

        return {
            "original_budget_cr":       round(original_budget, 2),
            "adjusted_budget_cr":       round(adjusted_budget, 2),
            "budget_adjustment_pct":    budget_adjustment_pct,
            "original_duration_months": int(original_duration),
            "adjusted_duration_months": int(adjusted_duration),
            "assumptions_used":         assumptions,
        }

    except Exception as exc:
        logger.warning("[context_adjustment] Adjustment failed: %s — returning originals", exc)
        return _null
