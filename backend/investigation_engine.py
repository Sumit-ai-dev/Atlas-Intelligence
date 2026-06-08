"""
investigation_engine.py
=======================
Deterministic Investigation Grouping Engine for Atlas Assurance DPR Analysis.

Groups the 58 CAG violation findings into themed investigation summaries
without any ML models or LLMs. Pure keyword-to-category mapping.

Output schema per investigation:
    {
        "title": str,
        "severity": "LOW" | "MEDIUM" | "HIGH",
        "confidence": "LOW" | "MEDIUM" | "HIGH",
        "summary": str,
        "supporting_findings": list[str],
        "evidence": list[str],
        "recommendations": list[str],
    }

Imported by: main.py
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Investigation Group Definitions
# Maps investigation title → list of violation key fragments that belong to it.
# A finding belongs to a group if its feature_key contains any fragment.
# ---------------------------------------------------------------------------

_INVESTIGATION_GROUPS: list[dict[str, Any]] = [
    {
        "title": "Environmental & Regulatory Clearance Failure",
        "fragments": [
            "missing_forest_clearance",
            "missing_environmental_clearance",
            "delayed_wildlife_clearance",
            "coastal_regulation_zone_violation",
            "tree_felling_permission_delayed",
            "archaeological_survey_objection",
        ],
        "severity_weights": {"missing_forest_clearance": 2, "missing_environmental_clearance": 2},
        "summaries": {
            1: "One or more mandatory environmental approvals appear to have been delayed or incorrectly certified, creating regulatory exposure and potential schedule overruns.",
            2: "Multiple environmental and regulatory clearances appear to be delayed or missing. This pattern is consistent with documentation failures that can stall project execution and invite CVC scrutiny.",
            3: "A systemic cluster of environmental clearance failures has been detected. Findings across forest, environmental, and wildlife approvals suggest a breakdown in regulatory compliance that constitutes high legal and financial risk.",
        },
        "recommendations": [
            "Request certified copies of all pending regulatory approvals from the contractor.",
            "Verify Stage I and Stage II forest clearances with MoEFCC directly.",
            "Conduct a regulatory compliance review before releasing next milestone payment.",
            "Escalate unresolved clearance gaps to the relevant statutory authority.",
        ],
    },
    {
        "title": "Land Acquisition & Right of Way Failure",
        "fragments": [
            "land_acquisition_incomplete",
            "right_of_way_not_secured",
            "defense_land_transfer_delayed",
            "failure_to_identify_encroachments",
            "underestimated_rehabilitation_plan",
        ],
        "severity_weights": {"land_acquisition_incomplete": 2, "right_of_way_not_secured": 2},
        "summaries": {
            1: "Land acquisition or Right of Way handover appears incomplete, which may be directly obstructing physical construction progress.",
            2: "Multiple land-related issues detected, including acquisition gaps and possible encroachment failures. These issues can freeze construction and trigger arbitration.",
            3: "A systemic land access failure pattern has been identified across land acquisition, Right of Way, and encroachment findings, indicating high risk of contractual dispute and schedule collapse.",
        },
        "recommendations": [
            "Obtain an up-to-date land acquisition status report from the District Collector.",
            "Verify Right of Way handover documentation against contract Clause 9.",
            "Initiate encroachment survey before next construction milestone.",
            "Escalate to NHAI / MoRTH if land handover has exceeded contractual deadlines.",
        ],
    },
    {
        "title": "Planning & Survey Deficiency",
        "fragments": [
            "faulty_topographical_survey",
            "inadequate_soil_testing",
            "poor_traffic_forecasting",
            "faulty_hydrological_survey",
            "improper_alignment_selection",
            "omission_of_railway_over_bridges",
            "failure_to_consult_local_bodies",
        ],
        "severity_weights": {"faulty_topographical_survey": 2, "inadequate_soil_testing": 2},
        "summaries": {
            1: "A planning deficiency has been detected in the DPR, suggesting inadequate field surveys or technical assessments during the pre-construction phase.",
            2: "Multiple planning and survey deficiencies have been identified. These findings suggest the DPR was prepared without adequate field validation, increasing the risk of scope creep and cost overruns.",
            3: "A systemic planning failure has been detected across topographic, soil, hydrological, and traffic survey parameters. This level of deficiency is a strong indicator of DPR inflation and document fabrication.",
        },
        "recommendations": [
            "Commission an independent technical audit of the DPR surveys.",
            "Request original field survey data and third-party validation reports.",
            "Review IRC standards compliance for the alignment and bridge design.",
            "Refer findings to the Chief Technical Examiner (CTE) if multiple survey deficiencies are confirmed.",
        ],
    },
    {
        "title": "Financial Integrity & Procurement Irregularity",
        "fragments": [
            "ineligible_bidder_awarded",
            "ccea_scrutiny_bypassed",
            "inflation_underestimation",
            "single_bid_acceptance_violation",
            "abnormal_low_bid_accepted",
            "defective_bank_guarantee",
            "delayed_mobilization_advance_recovery",
            "cost_overrun_due_to_scope_change",
            "escrow_account_mismanagement",
            "failure_to_achieve_financial_closure",
            "irregular_grant_of_extension_of_time",
        ],
        "severity_weights": {
            "ineligible_bidder_awarded": 3,
            "escrow_account_mismanagement": 3,
            "defective_bank_guarantee": 3,
            "ccea_scrutiny_bypassed": 2,
        },
        "summaries": {
            1: "A financial or procurement irregularity has been detected, which may indicate deviation from CVC tendering guidelines or contract financial norms.",
            2: "Multiple financial integrity issues have been flagged across the DPR, including possible tendering violations and budget management concerns that warrant deeper audit.",
            3: "A high-risk financial irregularity cluster has been identified. Findings across bidding, advance recovery, and escrow management are consistent with patterns observed in past CAG-flagged ghost project cases.",
        },
        "recommendations": [
            "Request the original tender evaluation matrix and comparative bid statement.",
            "Audit mobilization advance disbursement and recovery schedule against contract terms.",
            "Verify Escrow Account statements with the designated bank.",
            "Refer to CVC if CCEA scrutiny bypass or ineligible award is confirmed.",
        ],
    },
    {
        "title": "Execution Quality & Material Compliance Failure",
        "fragments": [
            "use_of_substandard_cement",
            "poor_bitumen_quality",
            "absence_of_quality_assurance_plan",
            "unauthorized_subcontracting",
            "failure_to_deploy_key_personnel",
            "improper_curing_of_concrete",
            "use_of_rejected_materials",
            "failure_to_relocate_utilities_safely",
            "inadequate_machinery_deployment",
        ],
        "severity_weights": {
            "use_of_substandard_cement": 2,
            "use_of_rejected_materials": 3,
            "absence_of_quality_assurance_plan": 2,
        },
        "summaries": {
            1: "An execution quality issue has been flagged, suggesting possible deviation from IRC construction standards or QAP non-compliance.",
            2: "Multiple construction quality findings have been detected, including possible substandard materials and QAP gaps. These collectively increase structural risk to the project.",
            3: "A systemic execution quality failure has been identified across material, personnel, and machinery parameters. This pattern is consistent with concealed subcontracting and quality certificate forgery.",
        },
        "recommendations": [
            "Commission third-party quality audit of cement cube test records and bitumen core samples.",
            "Verify Key Personnel deployment records against contractual Schedule K.",
            "Request the Quality Assurance Plan (QAP) and monthly inspection reports.",
            "Inspect construction zone for use of rejected or unverified materials.",
        ],
    },
    {
        "title": "Project Milestone & Schedule Violation",
        "fragments": [
            "delayed_milestone_achievement",
            "failure_to_maintain_during_dlp",
            "independent_engineer_negligence",
            "non_compliance_with_safety_norms",
            "unplanned_utility_shifting",
        ],
        "severity_weights": {"independent_engineer_negligence": 3, "delayed_milestone_achievement": 2},
        "summaries": {
            1: "A schedule or milestone compliance issue has been flagged, suggesting the contractor may be failing to meet contractual progress obligations.",
            2: "Multiple milestone and compliance violations have been detected, including possible Independent Engineer negligence. These indicate governance oversight breakdown.",
            3: "A high-severity schedule and compliance failure cluster has been identified. Evidence of IE negligence combined with repeated milestone defaults is a strong indicator of collusion or governance capture.",
        },
        "recommendations": [
            "Pull Independent Engineer's monthly progress reports and compare against actual site photographs.",
            "Apply liquidated damages as per contract clause if milestones are confirmed delayed.",
            "Consider replacing the Independent Engineer if collusion is indicated.",
            "Escalate to CPWD Project Director for emergency site audit.",
        ],
    },
    {
        "title": "Operations & Safety Compliance Gap",
        "fragments": [
            "toll_management_system_noncompliant",
            "premature_tolling",
            "failure_to_construct_toll_plaza",
            "non_maintenance_of_ambulances",
            "weigh_in_motion_defective",
            "missing_highway_lighting",
            "poor_road_marking_and_signage",
            "failure_to_maintain_service_roads",
            "illegal_median_openings",
            "waterlogging_in_underpasses",
        ],
        "severity_weights": {
            "premature_tolling": 2,
            "missing_highway_lighting": 2,
            "illegal_median_openings": 3,
        },
        "summaries": {
            1: "An operational or safety compliance gap has been identified, potentially exposing the project to road safety and revenue leakage risk.",
            2: "Multiple operations and safety issues have been detected, including possible toll mismanagement and road safety deficiencies that create public liability.",
            3: "A systemic operations compliance failure has been identified across tolling, safety, and maintenance parameters. This pattern may indicate deliberate underperformance to avoid operational obligations.",
        },
        "recommendations": [
            "Conduct a joint NHAI/MoRTH site inspection for operational infrastructure status.",
            "Audit toll collection records against traffic census data for premature tolling evidence.",
            "Verify highway lighting and crash barrier installation against design drawings.",
            "Issue penalty notice under NHAI Safety Audit norms if deficiencies are confirmed.",
        ],
    },
    {
        "title": "Legal Dispute & Contractual Default Risk",
        "fragments": [
            "arbitration_losses_due_to_delays",
            "failure_to_terminate_defaulting_contractor",
            "pending_court_cases_halting_work",
            "force_majeure_misuse",
        ],
        "severity_weights": {
            "pending_court_cases_halting_work": 3,
            "failure_to_terminate_defaulting_contractor": 3,
        },
        "summaries": {
            1: "A legal or contractual risk has been flagged, indicating the project may be exposed to arbitration or court proceedings.",
            2: "Multiple legal and contractual default indicators have been detected. These findings suggest the authority may have failed to take timely action against the contractor.",
            3: "A high-severity legal default cluster has been identified. Evidence of pending court cases combined with failure to terminate a defaulting contractor represents a serious governance failure with potential financial recovery risk to the government.",
        },
        "recommendations": [
            "Request status of all pending arbitration and court cases from legal cell.",
            "Review contractor termination readiness under contract clauses 60–65.",
            "Conduct Force Majeure declaration audit against independent weather/event records.",
            "Escalate to Ministry of Law if active court injunction is confirmed.",
        ],
    },
]


# ---------------------------------------------------------------------------
# Severity / Confidence Calculation
# ---------------------------------------------------------------------------

def _compute_severity(count: int, weighted_score: int) -> str:
    """Map finding count and weighted score → severity tier."""
    if weighted_score >= 5 or count >= 3:
        return "HIGH"
    if weighted_score >= 3 or count >= 2:
        return "MEDIUM"
    return "LOW"


def _compute_confidence(count: int, evidence_items: list[str]) -> str:
    """
    Confidence reflects how well the evidence actually matches the group.
    More triggering findings = higher confidence the group is real.
    """
    if count >= 3:
        return "HIGH"
    if count >= 2:
        return "MEDIUM"
    return "LOW"


def _pick_summary(count: int, summaries: dict) -> str:
    if count >= 3:
        return summaries[3]
    if count >= 2:
        return summaries[2]
    return summaries[1]


# ---------------------------------------------------------------------------
# Finding label formatter
# Mirrors the format used in _run_dpr_analysis's evidence_log entries:
#   "Risk Found: {label} - '{excerpt}'"
# ---------------------------------------------------------------------------

def _finding_label_from_key(feature_key: str) -> str:
    """Convert 'violations.clearances.missing_forest_clearance' → 'Missing Forest Clearance'."""
    leaf = feature_key.split(".")[-1]
    return leaf.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def build_investigations(
    extracted_features: dict[str, Any],
    evidence_log: list[str],
) -> list[dict[str, Any]]:
    """
    Build a list of Investigation summary objects from:
      - extracted_features: the full 58-violation feature dict (value 0 or 1)
      - evidence_log: the raw evidence strings from ChromaDB RAG

    Returns only groups that have at least one triggered finding.
    Groups with zero triggered findings are silently omitted.
    """

    # Build a lookup: feature_key_fragment → evidence excerpt
    # evidence_log entries look like:
    #   "Risk Found: Missing Forest Clearance - 'some excerpt from doc'"
    #   The feature key fragment can be reverse-mapped from the label.

    # First, build a map: fragment → bool (triggered) + raw evidence string
    triggered: dict[str, str] = {}  # fragment → raw evidence line
    for feature_key, value in extracted_features.items():
        if not feature_key.startswith("violations."):
            continue
        if value == 1:
            fragment = feature_key.split(".")[-1]
            # Find the corresponding evidence line if it exists
            label = _finding_label_from_key(feature_key)
            matching_evidence = ""
            for ev_line in evidence_log:
                if label.lower() in ev_line.lower():
                    matching_evidence = ev_line
                    break
            triggered[fragment] = matching_evidence

    investigations: list[dict[str, Any]] = []

    for group in _INVESTIGATION_GROUPS:
        matched_fragments: list[str] = []
        matched_evidence: list[str] = []
        weighted_score = 0

        for fragment in group["fragments"]:
            if fragment in triggered:
                matched_fragments.append(fragment)
                ev = triggered[fragment]
                if ev:
                    matched_evidence.append(ev)
                # Apply weight multiplier if defined
                weight = group["severity_weights"].get(fragment, 1)
                weighted_score += weight

        if not matched_fragments:
            continue  # Nothing in this group triggered — skip it

        count = len(matched_fragments)
        severity = _compute_severity(count, weighted_score)
        confidence = _compute_confidence(count, matched_evidence)
        summary = _pick_summary(count, group["summaries"])

        # Build human-readable supporting findings list
        supporting_findings = [
            _finding_label_from_key(f) for f in matched_fragments
        ]

        investigations.append({
            "title": group["title"],
            "severity": severity,
            "confidence": confidence,
            "summary": summary,
            "supporting_findings": supporting_findings,
            "evidence": matched_evidence,
            "recommendations": group["recommendations"],
        })

    # Sort: HIGH severity first, then MEDIUM, then LOW
    _order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    investigations.sort(key=lambda x: _order.get(x["severity"], 3))

    return investigations
