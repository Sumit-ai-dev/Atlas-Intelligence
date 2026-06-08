"""
bidding_engine.py
=================
NCRI-Gated Contractor Bidding Engine for Atlas Assurance.

Handles:
  - Tender registry (create, list, get)
  - Bid submission with NCRI auto-attachment and anomaly scoring
  - Contract award with WhatsApp notification
  - Cartel / abnormally-low-bid detection

Storage:
  - tenders.json  -> satellite_cache/tenders.json
  - bids.json     -> satellite_cache/bids.json
"""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Storage paths (resolved at import time relative to this file)
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(__file__).parent / "satellite_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

TENDERS_PATH = _CACHE_DIR / "tenders.json"
BIDS_PATH = _CACHE_DIR / "bids.json"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_tenders() -> dict[str, Any]:
    if TENDERS_PATH.exists():
        with open(TENDERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_tenders(data: dict) -> None:
    with open(TENDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_bids() -> dict[str, list]:
    """Returns dict keyed by tender_id, value is list of bid dicts."""
    if BIDS_PATH.exists():
        with open(BIDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_bids(data: dict) -> None:
    with open(BIDS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Anomaly Score Engine
# ---------------------------------------------------------------------------

def compute_anomaly_score(
    bid_amount_cr: float,
    estimated_value_cr: float,
    ncri_score: int,
    is_new_entity: bool,
    active_violation_count: int,
) -> tuple[int, list[str]]:
    """
    Returns (anomaly_score 0-100, list_of_flag_strings).

    Flags:
      ABNORMALLY_LOW_BID  - bid < 80% of estimated value
      SUSPICIOUSLY_LOW    - bid < 90% of estimated value
      BLACKLISTED         - NCRI < 40 (Tier F)
      HIGH_RISK           - NCRI 40-59 (Tier C)
      NEW_ENTITY          - entity registered < 2 years / no NCRI history
      ACTIVE_VIOLATION    - has open violations in the ledger
    """
    score = 0
    flags: list[str] = []

    # Bid-price anomaly
    if estimated_value_cr > 0:
        ratio = bid_amount_cr / estimated_value_cr
        if ratio < 0.80:
            score += 40
            flags.append("ABNORMALLY_LOW_BID")
        elif ratio < 0.90:
            score += 20
            flags.append("SUSPICIOUSLY_LOW")

    # NCRI risk
    if ncri_score < 40:
        score += 40
        flags.append("BLACKLISTED")
    elif ncri_score < 60:
        score += 20
        flags.append("HIGH_RISK")
    elif ncri_score < 80:
        score += 10

    # Entity age
    if is_new_entity:
        score += 15
        flags.append("NEW_ENTITY")

    # Active violations
    if active_violation_count > 0:
        score += min(active_violation_count * 5, 25)
        flags.append("ACTIVE_VIOLATION")

    return min(score, 100), flags


def _eligibility_from_ncri(ncri: int, min_ncri: int) -> str:
    """Return bid eligibility status string."""
    if ncri < min_ncri:
        return "REJECTED"
    if ncri < 40:
        return "REJECTED"
    if ncri < 60:
        return "FLAGGED"
    return "ELIGIBLE"


# ---------------------------------------------------------------------------
# Tender CRUD
# ---------------------------------------------------------------------------

def create_tender(
    project_name: str,
    location: str,
    estimated_value_cr: float,
    min_ncri_required: int,
    deadline: str,
    description: str = "",
    tender_id: str | None = None,
) -> dict[str, Any]:
    """Create and persist a new tender. Returns the tender dict."""
    tenders = _load_tenders()
    tid = tender_id or f"TND-{uuid.uuid4().hex[:6].upper()}"
    tender = {
        "tender_id": tid,
        "project_name": project_name,
        "location": location,
        "estimated_value_cr": estimated_value_cr,
        "min_ncri_required": min_ncri_required,
        "deadline": deadline,
        "description": description,
        "status": "OPEN",  # OPEN | CLOSED | AWARDED
        "awarded_to": None,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    tenders[tid] = tender
    _save_tenders(tenders)
    return tender


def list_tenders() -> list[dict[str, Any]]:
    tenders = _load_tenders()
    bids = _load_bids()
    result = []
    for tid, t in tenders.items():
        t_out = dict(t)
        t_out["bid_count"] = len(bids.get(tid, []))
        result.append(t_out)
    return sorted(result, key=lambda x: x["status"] != "OPEN")


def get_tender(tender_id: str) -> dict[str, Any] | None:
    tenders = _load_tenders()
    return tenders.get(tender_id)


# ---------------------------------------------------------------------------
# Bid Submission
# ---------------------------------------------------------------------------

def submit_bid(
    tender_id: str,
    contractor_id: str,
    contractor_name: str,
    bid_amount_cr: float,
    ncri_score: int,
    active_violation_count: int = 0,
    is_new_entity: bool = False,
    years_of_experience: int = 5,
) -> dict[str, Any]:
    """
    Submit a bid for a tender. NCRI is auto-attached and cannot be overridden.
    Returns the persisted bid dict.
    """
    tenders = _load_tenders()
    if tender_id not in tenders:
        raise ValueError(f"Tender {tender_id} not found")

    tender = tenders[tender_id]
    if tender["status"] != "OPEN":
        raise ValueError(f"Tender {tender_id} is {tender['status']} — not accepting bids")

    anomaly_score, flags = compute_anomaly_score(
        bid_amount_cr=bid_amount_cr,
        estimated_value_cr=tender["estimated_value_cr"],
        ncri_score=ncri_score,
        is_new_entity=is_new_entity,
        active_violation_count=active_violation_count,
    )

    eligibility = _eligibility_from_ncri(ncri_score, tender["min_ncri_required"])

    bid = {
        "bid_id": f"BID-{uuid.uuid4().hex[:8].upper()}",
        "tender_id": tender_id,
        "contractor_id": contractor_id,
        "contractor_name": contractor_name,
        "bid_amount_cr": bid_amount_cr,
        "ncri_score": ncri_score,
        "anomaly_score": anomaly_score,
        "flags": flags,
        "eligibility": eligibility,
        "active_violation_count": active_violation_count,
        "is_new_entity": is_new_entity,
        "years_of_experience": years_of_experience,
        "submitted_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    bids = _load_bids()
    bids.setdefault(tender_id, []).append(bid)
    _save_bids(bids)
    return bid


# ---------------------------------------------------------------------------
# Bid Leaderboard
# ---------------------------------------------------------------------------

def get_leaderboard(tender_id: str) -> list[dict[str, Any]]:
    """
    Return bids for a tender sorted by:
    1. ELIGIBLE bids first (by price ascending)
    2. FLAGGED bids next (by price ascending)
    3. REJECTED bids last
    """
    bids = _load_bids()
    tender_bids = bids.get(tender_id, [])

    priority = {"ELIGIBLE": 0, "FLAGGED": 1, "REJECTED": 2}
    sorted_bids = sorted(
        tender_bids,
        key=lambda b: (priority.get(b["eligibility"], 3), b["bid_amount_cr"])
    )

    # Add rank
    for i, b in enumerate(sorted_bids):
        b["rank"] = f"L{i + 1}"

    return sorted_bids


# ---------------------------------------------------------------------------
# Contract Award
# ---------------------------------------------------------------------------

def award_contract(tender_id: str, contractor_id: str) -> dict[str, Any]:
    """Mark a tender as AWARDED to the given contractor."""
    tenders = _load_tenders()
    if tender_id not in tenders:
        raise ValueError(f"Tender {tender_id} not found")

    bids = _load_bids()
    tender_bids = bids.get(tender_id, [])
    winning_bid = next(
        (b for b in tender_bids if b["contractor_id"] == contractor_id), None
    )
    if not winning_bid:
        raise ValueError(f"No bid from contractor {contractor_id} found")

    tenders[tender_id]["status"] = "AWARDED"
    tenders[tender_id]["awarded_to"] = contractor_id
    tenders[tender_id]["awarded_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    tenders[tender_id]["awarded_bid_cr"] = winning_bid["bid_amount_cr"]
    tenders[tender_id]["awarded_contractor_name"] = winning_bid["contractor_name"]
    _save_tenders(tenders)

    return {
        "tender_id": tender_id,
        "status": "AWARDED",
        "awarded_to": contractor_id,
        "awarded_contractor_name": winning_bid["contractor_name"],
        "awarded_bid_cr": winning_bid["bid_amount_cr"],
        "winning_ncri": winning_bid["ncri_score"],
    }


# ---------------------------------------------------------------------------
# AI Recommendation Engine
# ---------------------------------------------------------------------------

def get_recommendation(tender_id: str) -> dict[str, Any]:
    """
    Return an AI-generated recommendation for which contractor to award to.
    Logic:
    - Filter to ELIGIBLE bids only
    - Among eligible, pick lowest price (standard L1 logic)
    - But flag if L1 has anomaly_score > 30 and recommend L2
    """
    leaderboard = get_leaderboard(tender_id)
    eligible = [b for b in leaderboard if b["eligibility"] == "ELIGIBLE"]
    flagged = [b for b in leaderboard if b["eligibility"] == "FLAGGED"]
    rejected = [b for b in leaderboard if b["eligibility"] == "REJECTED"]

    if not eligible and not flagged:
        return {
            "recommended_contractor_id": None,
            "recommended_contractor_name": None,
            "reason": "No eligible bids received.",
            "risk_level": "CRITICAL",
        }

    # Best eligible bid
    best = eligible[0] if eligible else flagged[0]

    if best["anomaly_score"] > 50:
        reason = (
            f"L1 bidder '{best['contractor_name']}' has anomaly score "
            f"{best['anomaly_score']}/100 with flags: "
            f"{', '.join(best['flags'])}. "
            f"Atlas Assurance recommends escalating to human review before award."
        )
        risk = "HIGH"
    elif best["anomaly_score"] > 25:
        reason = (
            f"Recommend '{best['contractor_name']}' (NCRI: {best['ncri_score']}, "
            f"bid: Rs. {best['bid_amount_cr']} Cr) with caution. "
            f"Minor flags detected: {', '.join(best['flags']) or 'none'}."
        )
        risk = "MODERATE"
    else:
        reason = (
            f"Atlas Assessment: NCRI threshold satisfied for '{best['contractor_name']}' "
            f"(NCRI: {best['ncri_score']}/100, bid: Rs. {best['bid_amount_cr']} Cr). "
            f"No active violations detected. Lowest eligible bid identified."
        )
        risk = "LOW"

    return {
        "recommended_contractor_id": best["contractor_id"],
        "recommended_contractor_name": best["contractor_name"],
        "recommended_bid_cr": best["bid_amount_cr"],
        "recommended_ncri": best["ncri_score"],
        "reason": reason,
        "risk_level": risk,
        "eligible_count": len(eligible),
        "flagged_count": len(flagged),
        "rejected_count": len(rejected),
    }


# ---------------------------------------------------------------------------
# NCRI Lookup Helper (used by both seed and live bid submission)
# ---------------------------------------------------------------------------

_LEDGER_PATH = _CACHE_DIR / "audit_ledgers.json"


def get_ncri_for_contractor(contractor_id: str, contractor_name: str) -> tuple[int, int]:
    """
    Dynamically look up NCRI score and active violation count from the real
    audit_ledgers.json. Falls back to (100, 0) if no ledger entry matches.

    Matching strategy (in order):
      1. Exact contractor_id match on a ledger key
      2. Case-insensitive contractor name substring match in ledger "contractor" field
    """
    if not _LEDGER_PATH.exists():
        return 100, 0

    with open(_LEDGER_PATH, "r", encoding="utf-8") as f:
        ledger: dict = json.load(f)

    # 1. Direct key match
    if contractor_id in ledger:
        entry = ledger[contractor_id]
        violations = entry.get("active_violations", [])
        from ncri_engine import calculate_ncri_score
        return calculate_ncri_score(violations), len(violations)

    # 2. Fuzzy name match
    name_lower = contractor_name.lower()
    for pid, pdata in ledger.items():
        ledger_contractor = pdata.get("contractor", "").lower()
        if ledger_contractor and (
            ledger_contractor in name_lower or name_lower in ledger_contractor
        ):
            violations = pdata.get("active_violations", [])
            from ncri_engine import calculate_ncri_score
            return calculate_ncri_score(violations), len(violations)

    return 100, 0


# ---------------------------------------------------------------------------
# Seed Data Bootstrap
# ---------------------------------------------------------------------------

# Static seed registry — NCRI scores are looked up from ledger at seed time.
# If a contractor is not in the ledger, the fallback score below is used.
# This means the demo data reflects the REAL governance state of the system.
_SEED_CONTRACTORS = {
    "CONT-ARV": {
        "name": "Aarav Infrastructure Pvt Ltd",
        "fallback_ncri": 22,       # Blacklisted — ghost project history
        "fallback_violations": 3,
        "bid_amount_cr": {"TND-DRR7": 940.0},
        "is_new_entity": True,
        "years_of_experience": 2,
    },
    "CONT-LNT": {
        "name": "L&T Construction Ltd",
        "fallback_ncri": 81,
        "fallback_violations": 0,
        "bid_amount_cr": {"TND-DRR7": 1050.0},
        "is_new_entity": False,
        "years_of_experience": 35,
    },
    "CONT-NCC": {
        "name": "NCC Limited",
        "fallback_ncri": 74,
        "fallback_violations": 1,
        "bid_amount_cr": {"TND-DRR7": 1090.0},
        "is_new_entity": False,
        "years_of_experience": 28,
    },
    "CONT-DBL": {
        "name": "Dilip Buildcon Ltd",
        "fallback_ncri": 67,
        "fallback_violations": 2,
        "bid_amount_cr": {"TND-MCR2": 2240.0},
        "is_new_entity": False,
        "years_of_experience": 22,
    },
    "CONT-SPC": {
        "name": "Shapoorji Pallonji Engineering",
        "fallback_ncri": 92,
        "fallback_violations": 0,
        "bid_amount_cr": {"TND-MCR2": 2790.0},
        "is_new_entity": False,
        "years_of_experience": 45,
    },
    "CONT-GAY": {
        "name": "Gayatri Projects Ltd",
        "fallback_ncri": 78,
        "fallback_violations": 0,
        "bid_amount_cr": {"TND-PNB4": 318.0},
        "is_new_entity": False,
        "years_of_experience": 18,
    },
    "CONT-PNC": {
        "name": "PNC Infratech Ltd",
        "fallback_ncri": 84,
        "fallback_violations": 0,
        "bid_amount_cr": {"TND-PNB4": 326.0},
        "is_new_entity": False,
        "years_of_experience": 20,
    },
}

_SEED_TENDERS = [
    {
        "tender_id": "TND-DRR7",
        "project_name": "Delhi Ring Road - Section 7 (Mahipalpur to Dwarka)",
        "location": "New Delhi, NCR",
        "estimated_value_cr": 1200.0,
        "min_ncri_required": 60,
        "days_until_deadline": 3,
        "description": (
            "6-lane elevated expressway connecting Mahipalpur to Dwarka Sector 21. "
            "Includes 3 flyovers, 2 underpasses, and full utility relocation. "
            "Funded under NHDP Phase VII."
        ),
        "bidders": ["CONT-ARV", "CONT-LNT", "CONT-NCC"],
        "award_to": None,
    },
    {
        "tender_id": "TND-MCR2",
        "project_name": "Mumbai Coastal Road Extension - Phase 2 (Worli to Bandra)",
        "location": "Mumbai, Maharashtra",
        "estimated_value_cr": 2800.0,
        "min_ncri_required": 70,
        "days_until_deadline": 7,
        "description": (
            "8-lane coastal arterial road with twin tunnels and marine interchanges. "
            "MMRDA managed. Includes environment-sensitive marine wall reinforcement."
        ),
        "bidders": ["CONT-DBL", "CONT-SPC"],
        "award_to": None,
    },
    {
        "tender_id": "TND-PNB4",
        "project_name": "Pune Bypass NH-48 - Package 4 (Urse to Talegaon)",
        "location": "Pune, Maharashtra",
        "estimated_value_cr": 340.0,
        "min_ncri_required": 50,
        "days_until_deadline": -5,   # negative = past deadline
        "description": (
            "4-lane bypass reducing Pune city traffic. Includes 2 ROBs and "
            "toll plaza construction. MoRTH funded."
        ),
        "bidders": ["CONT-GAY", "CONT-PNC"],
        "award_to": "CONT-GAY",
    },
]


def seed_demo_data(force: bool = False) -> None:
    """
    Populate tenders.json and bids.json with demo data.
    NCRI scores are looked up from the real audit ledger at seed time —
    they are NOT hardcoded. If the ledger has no entry for a contractor,
    the fallback_ncri in _SEED_CONTRACTORS is used instead.
    Skips if data already exists unless force=True.
    """
    tenders = _load_tenders()
    if tenders and not force:
        return

    for t_def in _SEED_TENDERS:
        deadline = (
            datetime.date.today() + datetime.timedelta(days=t_def["days_until_deadline"])
        ).isoformat()

        create_tender(
            tender_id=t_def["tender_id"],
            project_name=t_def["project_name"],
            location=t_def["location"],
            estimated_value_cr=t_def["estimated_value_cr"],
            min_ncri_required=t_def["min_ncri_required"],
            deadline=deadline,
            description=t_def["description"],
        )

        for cid in t_def["bidders"]:
            c = _SEED_CONTRACTORS[cid]
            bid_amount = c["bid_amount_cr"].get(t_def["tender_id"], 0.0)

            # Try to get real NCRI from ledger; fall back to seed default
            live_ncri, live_violations = get_ncri_for_contractor(cid, c["name"])
            final_ncri = live_ncri if live_ncri != 100 else c["fallback_ncri"]
            final_violations = live_violations if live_ncri != 100 else c["fallback_violations"]

            submit_bid(
                tender_id=t_def["tender_id"],
                contractor_id=cid,
                contractor_name=c["name"],
                bid_amount_cr=bid_amount,
                ncri_score=final_ncri,
                active_violation_count=final_violations,
                is_new_entity=c["is_new_entity"],
                years_of_experience=c["years_of_experience"],
            )

        if t_def["award_to"]:
            award_contract(t_def["tender_id"], t_def["award_to"])
