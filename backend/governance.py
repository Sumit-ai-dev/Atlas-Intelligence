"""
governance.py
=============
Human Governance Workflow Engine — Phase 5.

Implements human-in-the-loop decisions (approval, reinvestigation requests, and overrides)
whilst preserving original AI recommendation outputs. All actions are additive.
"""

from __future__ import annotations

import datetime
from typing import Any

# Supported statuses
STATUS_PENDING = "PENDING_REVIEW"
STATUS_APPROVED = "APPROVED"
STATUS_REINVESTIGATION = "REINVESTIGATION_REQUESTED"
STATUS_OVERRIDDEN = "OVERRIDDEN"

# Supported action types
ACTION_APPROVE = "APPROVE"
ACTION_REINVESTIGATE = "REQUEST_REINVESTIGATION"
ACTION_OVERRIDE = "OVERRIDE"

def init_governance(cycle_data: dict[str, Any]) -> dict[str, Any]:
    """Ensure governance block exists with default state."""
    if "governance" not in cycle_data or not isinstance(cycle_data["governance"], dict):
        cycle_data["governance"] = {
            "status": STATUS_PENDING,
            "actions": []
        }
    return cycle_data

def add_governance_action(
    cycle_data: dict[str, Any],
    action_type: str,
    performed_by: str,
    reason: str,
    notes: str | None = None
) -> dict[str, Any]:
    """
    Appends a new governance action record to the cycle in-place,
    and updates the overall governance status.
    """
    cycle_data = init_governance(cycle_data)
    
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    
    action_record = {
        "action_type": action_type,
        "performed_by": performed_by,
        "performed_at": timestamp,
        "reason": reason,
        "notes": notes or ""
    }
    
    # Map action type to status
    status_map = {
        ACTION_APPROVE: STATUS_APPROVED,
        ACTION_REINVESTIGATE: STATUS_REINVESTIGATION,
        ACTION_OVERRIDE: STATUS_OVERRIDDEN
    }
    
    cycle_data["governance"]["actions"].append(action_record)
    cycle_data["governance"]["status"] = status_map.get(action_type, STATUS_PENDING)
    
    return cycle_data

def approve_cycle(
    cycle_data: dict[str, Any],
    performed_by: str,
    reason: str,
    notes: str | None = None
) -> dict[str, Any]:
    """Approve the assurance cycle."""
    return add_governance_action(cycle_data, ACTION_APPROVE, performed_by, reason, notes)

def request_reinvestigation(
    cycle_data: dict[str, Any],
    performed_by: str,
    reason: str,
    notes: str | None = None
) -> dict[str, Any]:
    """Request a reinvestigation for the cycle."""
    return add_governance_action(cycle_data, ACTION_REINVESTIGATE, performed_by, reason, notes)

def override_recommendation(
    cycle_data: dict[str, Any],
    performed_by: str,
    reason: str,
    notes: str | None = None
) -> dict[str, Any]:
    """Override the AI recommendation."""
    return add_governance_action(cycle_data, ACTION_OVERRIDE, performed_by, reason, notes)
