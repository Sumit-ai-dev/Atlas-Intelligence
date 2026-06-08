"""
test_phase5.py
==============
Automated regression test suite for Phase 5 Human Governance deliverables.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient

# Setup paths
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

import policy_loader
import digital_twin
import orchestrator
from main import app

def run_phase5_tests():
    print("====================================================")
    print("🚀 RUNNING PHASE 5 REGRESSION TESTS 🚀")
    print("====================================================\n")

    policy_loader.load_all()
    client = TestClient(app)

    # ────────────────────────────────────────────────────────
    # Setup temporary project and cycle for testing
    # ────────────────────────────────────────────────────────
    temp_project = "PRJ-TEMP-GOV"
    project_dir = BACKEND_DIR / "storage" / "digital_twins" / temp_project
    project_dir.mkdir(parents=True, exist_ok=True)
    temp_cycle_file = project_dir / "cycle-001.json"

    # Add temp project to registry dynamically so main.py doesn't 404
    registry_file = BACKEND_DIR / "storage" / "projects_registry.json"
    with open(registry_file, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    # Backup registry
    backup_file = BACKEND_DIR / "storage" / "projects_registry.json.bak5"
    shutil.copyfile(registry_file, backup_file)

    try:
        registry_data["projects"][temp_project] = {
            "id": temp_project,
            "name": "Governance Test Project",
            "contractor": "Gov Builder Ltd",
            "location": [19.0, 73.0],
            "bbox": [72.9, 18.9, 73.1, 19.1],
            "baseline_date": "2024-01-01",
            "started": "2024-01-01"
        }
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, indent=2)

        policy_loader.reload()

        # ────────────────────────────────────────────────────────
        # Scenario 1: Old cycles hydrate successfully & Immutability validation
        # ────────────────────────────────────────────────────────
        print("[*] Test 1: Historical Cycle Hydration & Immutability Audit...")
        legacy_cycle = {
            "cycle_id": "cycle-001",
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

        # Write directly to disk
        with open(temp_cycle_file, "w", encoding="utf-8") as f:
            json.dump(legacy_cycle, f, indent=2)

        # Load cycle to trigger hydration
        loaded_cycles = digital_twin.load_project_cycles(temp_project)
        assert len(loaded_cycles) == 1, "Should load 1 cycle"
        hydrated = loaded_cycles[0]

        # Verify default governance in memory
        assert "governance" in hydrated, "governance block must be hydrated in memory"
        assert hydrated["governance"]["status"] == "PENDING_REVIEW", "governance status must default to PENDING_REVIEW"
        assert hydrated["governance"]["actions"] == [], "governance actions must default to empty list"

        # Verify unified risk was hydrated in memory
        assert "unified_risk" in hydrated, "unified_risk must be hydrated in memory"

        # Verify file on disk was NOT mutated
        with open(temp_cycle_file, "r", encoding="utf-8") as f:
            disk_cycle = json.load(f)
        assert "governance" not in disk_cycle, "Disk JSON must NOT be mutated during hydration (Immutability check failed)"
        assert "unified_risk" not in disk_cycle, "Disk JSON must NOT have unified_risk after simple load (Immutability check failed)"
        print("    - Scenario 1/Pre-Check: SUCCESS (Hydration works in-memory, disk remains immutable Option B)")

        # ────────────────────────────────────────────────────────
        # Scenario 2: Governance defaults to PENDING_REVIEW on new cycle creation
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 2: New Cycle Creation Governance Default...")
        new_cycle_envelope = orchestrator.build_assurance_cycle(
            project=registry_data["projects"][temp_project],
            satellite_result={"status": "OK"},
            dpr_result={"analysis": {"verdict": "LOW_RISK", "risk_score": 0.10}},
            ncri_result={"tampering_detected": False, "ppe_compliance_pct": 100.0},
            context_result={"tolerance_band": "MEDIUM"},
            cross_evidence_result={"cross_evidence_findings": []}
        )
        assert "governance" in new_cycle_envelope, "New cycle must contain governance block"
        assert new_cycle_envelope["governance"]["status"] == "PENDING_REVIEW", "New cycle governance status must be PENDING_REVIEW"
        assert new_cycle_envelope["governance"]["actions"] == [], "New cycle governance actions must be empty"
        print("    - Scenario 2: SUCCESS (Governance defaults to PENDING_REVIEW)")

        # ────────────────────────────────────────────────────────
        # Scenario 3: Approvals persist
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 3: POST /approve Endpoint & Persistence...")
        approve_payload = {
            "performed_by": "Executive Engineer",
            "reason": "Field verification completed.",
            "notes": "Verified all concrete laying via geotagged photos."
        }
        response = client.post(
            f"/projects/{temp_project}/cycles/cycle-001/approve",
            json=approve_payload
        )
        assert response.status_code == 200, f"Approve request failed: {response.text}"
        gov_block = response.json()
        assert gov_block["status"] == "APPROVED"
        assert len(gov_block["actions"]) == 1
        assert gov_block["actions"][0]["action_type"] == "APPROVE"
        assert gov_block["actions"][0]["performed_by"] == "Executive Engineer"
        assert gov_block["actions"][0]["reason"] == "Field verification completed."
        assert gov_block["actions"][0]["notes"] == "Verified all concrete laying via geotagged photos."
        assert "performed_at" in gov_block["actions"][0]

        # Verify it persisted to disk
        with open(temp_cycle_file, "r", encoding="utf-8") as f:
            disk_cycle_after_approve = json.load(f)
        assert "governance" in disk_cycle_after_approve, "Governance must be persisted to disk after manual action"
        assert disk_cycle_after_approve["governance"]["status"] == "APPROVED"
        assert len(disk_cycle_after_approve["governance"]["actions"]) == 1

        print("    - Scenario 3: SUCCESS (Approvals persist)")

        # ────────────────────────────────────────────────────────
        # Scenario 4: Reinvestigations persist
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 4: POST /reinvestigate Endpoint & Persistence...")
        reinvestigate_payload = {
            "performed_by": "Regional Auditor",
            "reason": "Contradictory observations.",
            "notes": "Drone images show a lag in block B."
        }
        response = client.post(
            f"/projects/{temp_project}/cycles/cycle-001/reinvestigate",
            json=reinvestigate_payload
        )
        assert response.status_code == 200, f"Reinvestigate request failed: {response.text}"
        gov_block = response.json()
        assert gov_block["status"] == "REINVESTIGATION_REQUESTED"
        assert len(gov_block["actions"]) == 2
        assert gov_block["actions"][1]["action_type"] == "REQUEST_REINVESTIGATION"
        assert gov_block["actions"][1]["performed_by"] == "Regional Auditor"

        # Verify it persisted to disk and actions are additive
        with open(temp_cycle_file, "r", encoding="utf-8") as f:
            disk_cycle_after_reinv = json.load(f)
        assert disk_cycle_after_reinv["governance"]["status"] == "REINVESTIGATION_REQUESTED"
        assert len(disk_cycle_after_reinv["governance"]["actions"]) == 2
        print("    - Scenario 4: SUCCESS (Reinvestigations persist and are additive)")

        # ────────────────────────────────────────────────────────
        # Scenario 5: Overrides persist
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 5: POST /override Endpoint & Persistence...")
        override_payload = {
            "performed_by": "Project Director",
            "reason": "Executive discretion.",
            "notes": "Approved due to urgent national security requirement."
        }
        response = client.post(
            f"/projects/{temp_project}/cycles/cycle-001/override",
            json=override_payload
        )
        assert response.status_code == 200, f"Override request failed: {response.text}"
        gov_block = response.json()
        assert gov_block["status"] == "OVERRIDDEN"
        assert len(gov_block["actions"]) == 3
        assert gov_block["actions"][2]["action_type"] == "OVERRIDE"

        # Verify it persisted to disk
        with open(temp_cycle_file, "r", encoding="utf-8") as f:
            disk_cycle_after_override = json.load(f)
        assert disk_cycle_after_override["governance"]["status"] == "OVERRIDDEN"
        assert len(disk_cycle_after_override["governance"]["actions"]) == 3
        print("    - Scenario 5: SUCCESS (Overrides persist)")

        # ────────────────────────────────────────────────────────
        # Scenario 6: AI findings remain unchanged after governance actions
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 6: AI Findings Immutability Under Governance Actions...")
        # Compare base attributes from initial load to post-override load
        loaded_cycles_final = digital_twin.load_project_cycles(temp_project)
        final_cycle = loaded_cycles_final[0]
        
        # Verify non-governance keys are preserved exactly
        for k in ["satellite", "dpr", "ncri", "context", "cross_evidence", "unified_risk"]:
            assert k in final_cycle, f"Key {k} must be preserved in the cycle"
            if k != "cross_evidence":
                assert final_cycle[k] == hydrated[k], f"Key {k} was mutated! {final_cycle[k]} vs {hydrated[k]}"
            else:
                # Compare rule IDs and general structures without checking triggered_by which was hydrated
                for f1, f2 in zip(final_cycle["cross_evidence"], hydrated["cross_evidence"]):
                    assert f1["rule_id"] == f2["rule_id"]
                    assert f1["title"] == f2["title"]
        print("    - Scenario 6: SUCCESS (AI findings remain completely untouched)")

        # ────────────────────────────────────────────────────────
        # Scenario 7: PRJ-TEST works with zero code changes
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 7: PRJ-TEST Verification...")
        # Verify PRJ-TEST exists in projects registry
        projects = policy_loader.get_projects_registry()
        assert "PRJ-TEST" in projects, "PRJ-TEST must be registered"
        
        # Verify cycles for PRJ-TEST can be fetched
        cycles_prj_test = digital_twin.load_project_cycles("PRJ-TEST")
        print(f"    - PRJ-TEST cycle count: {len(cycles_prj_test)}")
        for i, c in enumerate(cycles_prj_test):
            assert "governance" in c, f"PRJ-TEST cycle {i} must hydrate governance correctly"
            assert "unified_risk" in c, f"PRJ-TEST cycle {i} must hydrate unified_risk correctly"
        print("    - Scenario 7: SUCCESS (PRJ-TEST behaves properly out of the box)")

        # ────────────────────────────────────────────────────────
        # Scenario 8: TypeScript compiles cleanly
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 8: TypeScript Compile Check...")
        app_dir = BACKEND_DIR.parent / "infra-ai-app"
        res = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(app_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            print("    - TypeScript compilation: SUCCESS (0 errors, 0 warnings)")
        else:
            print("    - TypeScript compilation: FAILED")
            print(res.stdout)
            print(res.stderr)
            raise AssertionError("TypeScript compilation failed")

        # ────────────────────────────────────────────────────────
        # Scenario 9: Previous regressions pass
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 9: Previous regressions...")
        import test_phase4
        test_phase4.run_tests()
        print("    - Scenario 9: SUCCESS (All Phase 0-4 regressions continue passing)")

    finally:
        # Restore backup
        shutil.copyfile(backup_file, registry_file)
        if backup_file.exists():
            backup_file.unlink()
        policy_loader.reload()

        # Cleanup temp project cycles
        if temp_cycle_file.exists():
            temp_cycle_file.unlink()
        if project_dir.exists():
            shutil.rmtree(project_dir)

    print("\n=========================================")
    print("🎉 ALL PHASE 5 REGRESSION TESTS PASSED! 🎉")
    print("=========================================\n")

if __name__ == "__main__":
    run_phase5_tests()
