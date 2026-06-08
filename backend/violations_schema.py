# violations_schema.py
# 58 Authentic Indian Government Infrastructure Violations (CAG / CVC / MoRTH / MoEFCC)

VIOLATIONS_DICT = {
    # ---------------- 1. PLANNING & DPR (Detailed Project Report) ----------------
    "violations.planning.faulty_topographical_survey": "Is the topographical survey faulty, inadequate, or missing?",
    "violations.planning.unplanned_utility_shifting": "Are there issues with unbudgeted utility shifting, like water or electrical lines?",
    "violations.planning.inadequate_soil_testing": "Has the geotechnical or soil testing been reported as inadequate or missing?",
    "violations.planning.poor_traffic_forecasting": "Are the traffic volume projections or forecasting models reported as overly optimistic or flawed?",
    "violations.planning.failure_to_identify_encroachments": "Did the DPR fail to identify illegal encroachments on the project site?",
    "violations.planning.faulty_hydrological_survey": "Is there a failure or inadequacy in the hydrological survey regarding flood plains or drainage?",
    "violations.planning.improper_alignment_selection": "Was the highway or railway alignment selection contested or found to be improper?",
    "violations.planning.omission_of_railway_over_bridges": "Were Railway Over Bridges (ROBs) or Under Bridges (RUBs) omitted from the initial DPR?",
    "violations.planning.underestimated_rehabilitation_plan": "Is the Resettlement & Rehabilitation (R&R) plan underestimated or inadequately budgeted?",
    "violations.planning.failure_to_consult_local_bodies": "Was there a failure to consult local municipal or panchayat bodies during planning?",
    
    # ---------------- 2. CLEARANCES & LAND ACQUISITION (LARR Act & MoEFCC) ----------------
    "violations.clearances.land_acquisition_incomplete": "Is land acquisition incomplete, or are there protests or stays regarding land?",
    "violations.clearances.missing_forest_clearance": "Is the formal forest clearance (Stage I or Stage II) missing or delayed?",
    "violations.clearances.missing_environmental_clearance": "Is the environmental clearance or EIA approval missing or contested?",
    "violations.clearances.delayed_wildlife_clearance": "Is the wildlife clearance from the National Board for Wildlife delayed or denied?",
    "violations.clearances.coastal_regulation_zone_violation": "Is there a violation or delay regarding Coastal Regulation Zone (CRZ) clearances?",
    "violations.clearances.right_of_way_not_secured": "Was the Right of Way (RoW) not handed over to the contractor on time?",
    "violations.clearances.tree_felling_permission_delayed": "Is the permission for tree felling or afforestation delayed by the forest department?",
    "violations.clearances.mining_clearance_for_borrow_earth_missing": "Are the mining clearances for borrow earth or aggregates missing?",
    "violations.clearances.archaeological_survey_objection": "Are there objections or stop-work orders from the Archaeological Survey of India (ASI)?",
    "violations.clearances.defense_land_transfer_delayed": "Is the transfer of Defense or Cantonment land delayed?",
    
    # ---------------- 3. FINANCIAL & TENDERING (CVC Guidelines) ----------------
    "violations.financial.ineligible_bidder_awarded": "Was an ineligible bidder awarded the contract?",
    "violations.financial.ccea_scrutiny_bypassed": "Was Cabinet Committee on Economic Affairs (CCEA) scrutiny bypassed?",
    "violations.financial.inflation_underestimation": "Did the financial model underestimate inflation or use 10-year-old material cost indices?",
    "violations.financial.single_bid_acceptance_violation": "Was a single bid accepted without proper justification or retendering?",
    "violations.financial.abnormal_low_bid_accepted": "Was an abnormally low bid accepted leading to project stalling?",
    "violations.financial.defective_bank_guarantee": "Did the contractor submit a defective or forged Performance Bank Guarantee?",
    "violations.financial.delayed_mobilization_advance_recovery": "Has the recovery of the Mobilization Advance from the contractor been delayed?",
    "violations.financial.cost_overrun_due_to_scope_change": "Are there massive cost overruns due to unauthorized changes in project scope?",
    "violations.financial.escrow_account_mismanagement": "Is there mismanagement or diversion of funds from the project Escrow Account?",
    "violations.financial.failure_to_achieve_financial_closure": "Did the concessionaire fail to achieve Financial Closure within the stipulated time?",
    "violations.financial.irregular_grant_of_extension_of_time": "Was an Extension of Time (EoT) granted irregularly without imposing liquidated damages?",
    
    # ---------------- 4. EXECUTION & QUALITY CONTROL (IRC Codes & QCI) ----------------
    "violations.execution.use_of_substandard_cement": "Is there evidence of the use of substandard cement or failure of concrete cube tests?",
    "violations.execution.poor_bitumen_quality": "Has the bitumen quality or pavement thickness been found to be substandard?",
    "violations.execution.absence_of_quality_assurance_plan": "Is the Quality Assurance Plan (QAP) missing or not strictly implemented?",
    "violations.execution.unauthorized_subcontracting": "Has the main contractor engaged in unauthorized or illegal subcontracting?",
    "violations.execution.failure_to_deploy_key_personnel": "Did the contractor fail to deploy the required Key Personnel (like Project Manager or Quality Engineer)?",
    "violations.execution.delayed_milestone_achievement": "Has the contractor repeatedly failed to achieve the physical milestones on time?",
    "violations.execution.independent_engineer_negligence": "Is the Independent Engineer (IE) or Authority Engineer (AE) reported as negligent or colluding?",
    "violations.execution.failure_to_maintain_during_dlp": "Did the contractor fail to rectify defects during the Defect Liability Period (DLP)?",
    "violations.execution.improper_curing_of_concrete": "Are there reports of improper curing of concrete leading to cracks or structural weakness?",
    "violations.execution.non_compliance_with_safety_norms": "Are there severe non-compliances with construction safety norms leading to accidents?",
    "violations.execution.use_of_rejected_materials": "Were materials rejected by the engineer later illegally used in construction?",
    "violations.execution.failure_to_relocate_utilities_safely": "Did utility relocation cause damage to existing pipelines or optical fiber cables?",
    "violations.execution.inadequate_machinery_deployment": "Did the contractor fail to deploy the required construction machinery and plants?",
    
    # ---------------- 5. OPERATIONS, TOLL & SAFETY (NHAI / MoRTH) ----------------
    "violations.operations.toll_management_system_noncompliant": "Is the toll management system non-compliant or prone to revenue leakage?",
    "violations.operations.premature_tolling": "Was toll collection started prematurely before the issuance of the Commercial Operation Date (COD)?",
    "violations.operations.failure_to_construct_toll_plaza": "Is the construction of the toll plaza delayed or incomplete?",
    "violations.operations.non_maintenance_of_ambulances": "Are the mandated ambulances, cranes, or patrol vehicles missing or unmaintained?",
    "violations.operations.weigh_in_motion_defective": "Are the Weigh-in-Motion (WIM) bridges at the toll plaza defective or bypassed?",
    "violations.operations.missing_highway_lighting": "Is highway lighting or high-mast lighting missing at critical junctions or toll plazas?",
    "violations.operations.poor_road_marking_and_signage": "Are road markings, crash barriers, or signages reported as substandard or missing?",
    "violations.operations.failure_to_maintain_service_roads": "Are the adjacent service roads left unmaintained or incomplete?",
    "violations.operations.illegal_median_openings": "Are there illegal or unsafe median openings causing accidents?",
    "violations.operations.waterlogging_in_underpasses": "Is there severe waterlogging reported in underpasses or vehicular underpasses (VUP)?",
    
    # ---------------- 6. CONTRACTUAL & LEGAL DISPUTES ----------------
    "violations.legal.arbitration_losses_due_to_delays": "Has the government lost arbitration cases due to its own delays in handing over land?",
    "violations.legal.failure_to_terminate_defaulting_contractor": "Did the authority fail to terminate a heavily defaulting contractor in time?",
    "violations.legal.pending_court_cases_halting_work": "Are there pending High Court or Supreme Court cases completely halting the work?",
    "violations.legal.force_majeure_misuse": "Has the contractor misused the Force Majeure clause to escape liabilities?"
}

# Ensure there are exactly 58 violations
if len(VIOLATIONS_DICT) != 58:
    print(f"Error: Expected 58 violations, found {len(VIOLATIONS_DICT)}")
