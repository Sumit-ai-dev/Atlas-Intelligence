"""
digital_twin.py
===============
Storage layer for assurance cycle persistence.

Each project gets its own sub-directory under storage/digital_twins/{project_id}/.
Each cycle is a self-contained JSON file: cycle-001.json, cycle-002.json, etc.

Public API:
  get_next_cycle_number(project_id)        → int
  save_assurance_cycle(project_id, cycle)  → str  (cycle_id like "cycle-001")
  load_project_cycles(project_id)          → list[dict]
  get_latest_cycle(project_id)             → dict | None

No database. JSON only. All I/O is synchronous.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_BACKEND_DIR     = Path(__file__).parent
_DIGITAL_TWINS   = _BACKEND_DIR / "storage" / "digital_twins"

# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def _project_dir(project_id: str) -> Path:
    """Return (and create if absent) the per-project twin directory."""
    d = _DIGITAL_TWINS / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_next_cycle_number(project_id: str) -> int:
    """
    Return the next sequential cycle number for a project.
    Scans existing cycle-NNN.json files and returns max+1 (or 1 if none exist).
    """
    d = _project_dir(project_id)
    existing = sorted(d.glob("cycle-*.json"))
    if not existing:
        return 1
    # Parse the highest number from filenames like "cycle-007.json"
    numbers = []
    for p in existing:
        try:
            numbers.append(int(p.stem.split("-")[1]))
        except (IndexError, ValueError):
            pass
    return (max(numbers) + 1) if numbers else 1


def save_assurance_cycle(project_id: str, cycle: dict[str, Any]) -> str:
    """
    Write a cycle dict to storage/digital_twins/{project_id}/cycle-NNN.json.

    The cycle dict must already contain all fields (caller's responsibility).
    Returns the cycle_id string (e.g. "cycle-001").
    """
    n        = get_next_cycle_number(project_id)
    cycle_id = f"cycle-{n:03d}"
    cycle["cycle_id"] = cycle_id            # stamp the id into the record

    dest = _project_dir(project_id) / f"{cycle_id}.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(cycle, f, indent=2, ensure_ascii=False)

    return cycle_id


def hydrate_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    """
    Hydrate older cycles for backward compatibility.
    1. Ensure all cross_evidence findings have the "triggered_by" key.
    2. Ensure the cycle has the "unified_risk" dict.
    """
    # 1. Hydrate cross_evidence findings with triggered_by
    if "cross_evidence" in cycle and isinstance(cycle["cross_evidence"], list):
        try:
            import policy_loader
            rules = policy_loader.get_cross_evidence_rules()
            rules_map = {r["rule_id"]: r for r in rules if "rule_id" in r}
        except Exception:
            rules_map = {}

        satellite_result = cycle.get("satellite")
        dpr_result = cycle.get("dpr")
        dpr_analysis = dpr_result.get("analysis", dpr_result) if dpr_result else {}
        ncri_result = cycle.get("ncri")
        
        ev = {
            "satellite_status": satellite_result.get("status", "") if satellite_result else "",
            "dpr_risk_level": dpr_analysis.get("verdict", "") if dpr_analysis else "",
            "forensics_tampering_detected": bool(ncri_result.get("tampering_detected", False)) if ncri_result else False,
            "ppe_compliance_pct": ncri_result.get("ppe_compliance_pct", 100.0) if ncri_result else 100.0,
            "satellite_activity_pct": satellite_result.get("construction_activity_pct", 100.0) if satellite_result else 100.0
        }

        from cross_evidence import _get_triggered_by
        findings_so_far = []
        for finding in cycle["cross_evidence"]:
            if not isinstance(finding, dict):
                continue
            if "triggered_by" not in finding:
                rule_id = finding.get("rule_id")
                rule = rules_map.get(rule_id)
                if rule:
                    try:
                        finding["triggered_by"] = _get_triggered_by(rule, ev, findings_so_far)
                    except Exception:
                        finding["triggered_by"] = []
                else:
                    finding["triggered_by"] = []
            findings_so_far.append(finding)
            
    # 2. Hydrate unified_risk if absent
    if "unified_risk" not in cycle or not cycle["unified_risk"]:
        try:
            from unified_risk import compute_unified_risk
            cycle["unified_risk"] = compute_unified_risk(
                satellite_result=cycle.get("satellite"),
                dpr_result=cycle.get("dpr"),
                ncri_result=cycle.get("ncri"),
                context_result=cycle.get("context"),
                cross_evidence_result=cycle.get("cross_evidence", [])
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to compute unified risk for backward compatibility: %s", exc)

    # 3. Hydrate governance if absent
    if "governance" not in cycle or not cycle["governance"]:
        cycle["governance"] = {
            "status": "PENDING_REVIEW",
            "actions": []
        }

    return cycle


def load_project_cycles(project_id: str) -> list[dict[str, Any]]:
    """
    Return all cycles for a project in ascending order (oldest first).
    Returns [] if the project has no cycles yet.
    """
    d = _project_dir(project_id)
    cycles = []
    for p in sorted(d.glob("cycle-*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                cycle = json.load(f)
                cycles.append(hydrate_cycle(cycle))
        except (json.JSONDecodeError, OSError):
            pass          # skip corrupt files silently
    return cycles


def get_latest_cycle(project_id: str) -> dict[str, Any] | None:
    """
    Return the most recent cycle dict for a project, or None if no cycles exist.
    """
    cycles = load_project_cycles(project_id)
    return cycles[-1] if cycles else None
