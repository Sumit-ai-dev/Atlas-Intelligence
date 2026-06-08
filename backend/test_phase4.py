"""
test_phase4.py
==============
Automated regression test suite for Phase 4 deliverables.
"""

import os
import sys
import json
import shutil
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

import policy_loader
import satellite
import cross_evidence
import unified_risk
import digital_twin

def run_tests():
    print("====================================================")
    print("🚀 RUNNING PHASE 4 REGRESSION TESTS 🚀")
    print("====================================================\n")

    # Prime policy loader
    policy_loader.load_all()

    # ────────────────────────────────────────────────────────
    # Test 1: PROJECTS Dynamic Proxy (Part A)
    # ────────────────────────────────────────────────────────
    print("[*] Test 1: PROJECTS Dynamic Proxy...")
    # Get current registry size
    initial_count = len(satellite.PROJECTS)
    print(f"    - Initial PROJECTS count: {initial_count}")

    # Read registry directly
    registry_file = BACKEND_DIR / "storage" / "projects_registry.json"
    with open(registry_file, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    # Backup registry
    backup_file = BACKEND_DIR / "storage" / "projects_registry.json.bak"
    shutil.copyfile(registry_file, backup_file)

    try:
        # Add new project to registry file
        registry_data["projects"]["PRJ-NEW-TEST"] = {
            "id": "PRJ-NEW-TEST",
            "name": "New Test Project",
            "contractor": "Adani Holdings",
            "location": [18.994, 73.070],
            "bbox": [73.045, 18.975, 73.095, 19.015],
            "baseline_date": "2024-01-01",
            "started": "2024-01-01"
        }
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, indent=2)

        # Trigger reload
        policy_loader.reload()

        # Check if PROJECTS automatically has it
        assert "PRJ-NEW-TEST" in satellite.PROJECTS, "PRJ-NEW-TEST should be present in PROJECTS after reload"
        assert len(satellite.PROJECTS) == initial_count + 1, "PROJECTS size should have increased by 1"
        print("    - Live reload check: SUCCESS (satellite.PROJECTS updated instantly)")

    finally:
        # Restore backup
        shutil.copyfile(backup_file, registry_file)
        if backup_file.exists():
            backup_file.unlink()
        policy_loader.reload()

    # Verify restored
    assert "PRJ-NEW-TEST" not in satellite.PROJECTS, "PRJ-NEW-TEST should be removed after restore"
    assert len(satellite.PROJECTS) == initial_count, "PROJECTS size should be back to initial"
    print("    - Live registry cleanup check: SUCCESS")


    # ────────────────────────────────────────────────────────
    # Test 2: Cross-Evidence Explainability (Part B)
    # ────────────────────────────────────────────────────────
    print("\n[*] Test 2: Cross-Evidence Explainability...")
    sat_res = {"status": "GHOST_ALERT", "construction_activity_pct": 5.0}
    dpr_res = {"verdict": "HIGH_RISK", "risk_score": 0.90}
    ncri_res = {"tampering_detected": True, "ppe_compliance_pct": 50.0}

    ce_result = cross_evidence.evaluate(
        satellite_result=sat_res,
        dpr_result=dpr_res,
        ncri_result=ncri_res
    )
    findings = ce_result.get("cross_evidence_findings", [])
    assert len(findings) > 0, "Should have fired rules"

    for f in findings:
        assert "rule_id" in f, "Finding must have rule_id"
        assert "triggered_by" in f, "Finding must have triggered_by"
        assert isinstance(f["triggered_by"], list), "triggered_by must be a list"
        print(f"    - Finding {f['rule_id']} triggered_by: {f['triggered_by']}")
    print("    - Cross-Evidence Explainability check: SUCCESS")


    # ────────────────────────────────────────────────────────
    # Test 3: Unified Risk Engine (Part C)
    # ────────────────────────────────────────────────────────
    print("\n[*] Test 3: Unified Risk Engine...")
    risk_result = unified_risk.compute_unified_risk(
        satellite_result=sat_res,
        dpr_result=dpr_res,
        ncri_result=ncri_res,
        context_result={"tolerance_band": "MEDIUM"},
        cross_evidence_result=ce_result
    )

    print(f"    - Computed Score: {risk_result['score']}")
    print(f"    - Attention Tier: {risk_result['tier']}")
    print(f"    - Breakdown: {risk_result['breakdown']}")
    print(f"    - Rationale: {risk_result['rationale']}")

    assert 0 <= risk_result["score"] <= 100, "Score must be 0-100"
    assert "tier" in risk_result, "Tier must be present"
    assert sum(risk_result["breakdown"].values()) == 100, "Breakdown sum must be 100"
    assert len(risk_result["rationale"]) > 0, "Rationale bullets must be generated"
    print("    - Unified Risk Engine check: SUCCESS")


    # ────────────────────────────────────────────────────────
    # Test 4: Cycle Hydration (Part D & Scenario 1)
    # ────────────────────────────────────────────────────────
    print("\n[*] Test 4: Cycle Hydration...")
    # Create temporary legacy cycle directory and file
    temp_project = "PRJ-TEMP-TEST"
    project_dir = BACKEND_DIR / "storage" / "digital_twins" / temp_project
    project_dir.mkdir(parents=True, exist_ok=True)
    temp_cycle_file = project_dir / "cycle-001.json"

    legacy_cycle = {
        "project_id": temp_project,
        "created_at": "2026-06-13T12:00:00Z",
        "satellite": {"status": "GHOST_ALERT"},
        "dpr": {"analysis": {"verdict": "HIGH_RISK", "risk_score": 0.85}},
        "ncri": {"tampering_detected": False, "ppe_compliance_pct": 90.0},
        "context": {"tolerance_band": "LOW"},
        "cross_evidence": [
            {
                "rule_id": "R1",
                "title": "Ghost Billing Cluster",
                "summary": "Old test summary"
            }
        ]
    }

    with open(temp_cycle_file, "w", encoding="utf-8") as f:
        json.dump(legacy_cycle, f)

    try:
        # Load project cycles
        loaded_cycles = digital_twin.load_project_cycles(temp_project)
        assert len(loaded_cycles) == 1, "Should load 1 cycle"
        hydrated = loaded_cycles[0]

        # Verify explainability and risk hydration
        assert "unified_risk" in hydrated, "unified_risk must be hydrated"
        assert "score" in hydrated["unified_risk"], "unified_risk must contain score"
        assert "triggered_by" in hydrated["cross_evidence"][0], "triggered_by must be hydrated in findings"
        print(f"    - Hydrated Score: {hydrated['unified_risk']['score']}")
        print(f"    - Hydrated Triggered By: {hydrated['cross_evidence'][0]['triggered_by']}")
        print("    - Cycle Hydration check: SUCCESS")
    finally:
        # Cleanup
        if temp_cycle_file.exists():
            temp_cycle_file.unlink()
        if project_dir.exists():
            shutil.rmtree(project_dir)

    print("\n=========================================")
    print("🎉 ALL PHASE 4 REGRESSION TESTS PASSED! 🎉")
    print("=========================================\n")

if __name__ == "__main__":
    run_tests()
