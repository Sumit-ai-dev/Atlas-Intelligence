"""
test_phase6.py
==============
Automated regression test suite for Phase 6 Final Assurance Report deliverables.
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
from report_generator import generate_assurance_report, render_html_report
from main import app

def run_phase6_tests():
    print("====================================================")
    print("🚀 RUNNING PHASE 6 REGRESSION TESTS 🚀")
    print("====================================================\n")

    policy_loader.load_all()
    client = TestClient(app)

    # ────────────────────────────────────────────────────────
    # Setup temporary project and cycle for testing
    # ────────────────────────────────────────────────────────
    temp_project = "PRJ-TEMP-REP"
    project_dir = BACKEND_DIR / "storage" / "digital_twins" / temp_project
    project_dir.mkdir(parents=True, exist_ok=True)
    temp_cycle_file = project_dir / "cycle-001.json"

    # Add temp project to registry dynamically
    registry_file = BACKEND_DIR / "storage" / "projects_registry.json"
    with open(registry_file, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    # Backup registry
    backup_file = BACKEND_DIR / "storage" / "projects_registry.json.bak6"
    shutil.copyfile(registry_file, backup_file)

    try:
        registry_data["projects"][temp_project] = {
            "id": temp_project,
            "name": "Report Test Project",
            "contractor": "Report Builders Ltd",
            "location": [20.0, 73.0],
            "bbox": [72.9, 19.9, 73.1, 20.1],
            "baseline_date": "2024-01-01",
            "started": "2024-01-01"
        }
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, indent=2)

        policy_loader.reload()

        # ────────────────────────────────────────────────────────
        # Scenario 1 & 3: Old cycles generate reports & no disk mutation
        # ────────────────────────────────────────────────────────
        print("[*] Test 1: Historical Cycle Report Generation & Immutability...")
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

        # Record file modify time to prove zero mutation
        mtime_before = temp_cycle_file.stat().st_mtime

        # Generate report
        report_data = generate_assurance_report(temp_project, "cycle-001")
        
        # Verify Report ID format and metadata
        meta = report_data["report_metadata"]
        assert meta["report_id"].startswith("RPT-"), "Report ID must start with RPT-"
        assert meta["generated_from_cycle"] == "cycle-001"
        assert "generated_at" in meta

        # Verify sections
        assert report_data["section_1_executive_summary"]["project_name"] == "Report Test Project"
        assert "section_9_atlas_recommendations" in report_data
        
        # Verify no file mutation on disk
        mtime_after = temp_cycle_file.stat().st_mtime
        assert mtime_before == mtime_after, "Report generation mutated the cycle JSON file on disk!"
        
        # Verify no new report files were created in storage directory
        twin_files = list(project_dir.glob("*"))
        assert len(twin_files) == 1, f"Report generation created extra files on disk! {twin_files}"
        
        print("    - Scenario 1/3: SUCCESS (Reports generated, zero disk mutations Option B)")

        # ────────────────────────────────────────────────────────
        # Scenario 2: New cycles generate reports successfully
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 2: New Cycle Report Generation...")
        # Create a new cycle through normal envelope
        new_cycle_envelope = orchestrator.build_assurance_cycle(
            project=registry_data["projects"][temp_project],
            satellite_result={"status": "NORMAL", "reported_progress_pct": 50.0, "satellite_actual_pct": 48.0, "discrepancy_pct": 2.0},
            dpr_result={"analysis": {"verdict": "LOW_RISK", "risk_score": 0.15, "budget_cr": 45.0, "time_gap_months": 2.0}},
            ncri_result={"tampering_detected": False, "ppe_compliance_pct": 95.0},
            context_result={"tolerance_band": "MEDIUM"},
            cross_evidence_result={"cross_evidence_findings": []}
        )
        new_cycle_envelope["cycle_id"] = "cycle-002"
        temp_cycle_file_2 = project_dir / "cycle-002.json"
        with open(temp_cycle_file_2, "w", encoding="utf-8") as f:
            json.dump(new_cycle_envelope, f, indent=2)

        # Generate report for new cycle
        report_data_2 = generate_assurance_report(temp_project, "cycle-002")
        assert report_data_2["section_1_executive_summary"]["unified_assurance_score"] > 0
        assert report_data_2["section_3_dpr_intelligence"]["risk_verdict"] == "LOW_RISK"
        print("    - Scenario 2: SUCCESS (New cycle reports generated)")

        # Cleanup cycle-002
        if temp_cycle_file_2.exists():
            temp_cycle_file_2.unlink()

        # ────────────────────────────────────────────────────────
        # Scenario 4: Governance actions render correctly
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 4: Governance Rendering (Newest First)...")
        # Add mock governance decisions
        legacy_cycle["governance"] = {
            "status": "APPROVED",
            "actions": [
                {
                    "action_type": "REQUEST_REINVESTIGATION",
                    "performed_by": "Auditor Alpha",
                    "performed_at": "2026-06-13T12:00:00Z",
                    "reason": "Contradictory observations.",
                    "notes": "Drone images lag."
                },
                {
                    "action_type": "APPROVE",
                    "performed_by": "Director Beta",
                    "performed_at": "2026-06-13T12:05:00Z",
                    "reason": "Field verification completed.",
                    "notes": "Verified."
                }
            ]
        }
        with open(temp_cycle_file, "w", encoding="utf-8") as f:
            json.dump(legacy_cycle, f, indent=2)

        report_gov = generate_assurance_report(temp_project, "cycle-001")
        timeline = report_gov["section_8_governance_actions"]["timeline"]
        assert len(timeline) == 2
        # Check reverse chronological order (newest first based on ISO strings: 12:05 is first)
        assert timeline[0]["action_type"] == "APPROVE"
        assert timeline[1]["action_type"] == "REQUEST_REINVESTIGATION"

        # Verify in HTML output
        html_content = render_html_report(report_gov)
        assert "Director Beta" in html_content
        assert "Auditor Alpha" in html_content
        print("    - Scenario 4: SUCCESS (Governance renders with newest first)")

        # ────────────────────────────────────────────────────────
        # Scenario 5: Cross-evidence explainability renders correctly
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 5: Cross-Evidence Explainability Rendering...")
        ce_intel = report_gov["section_5_cross_evidence_intelligence"]
        assert len(ce_intel) == 1
        assert "explainability" in ce_intel[0]
        assert "triggered because: SATELLITE \u2192 GHOST_ALERT, DPR \u2192 HIGH_RISK" in ce_intel[0]["explainability"]
        
        # Verify in HTML
        assert "triggered because: SATELLITE" in html_content
        print("    - Scenario 5: SUCCESS (Explainability traces render correctly)")

        # ────────────────────────────────────────────────────────
        # Scenario 6: PRJ-TEST works with zero code changes
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 6: PRJ-TEST Verification...")
        cycles_prj_test = digital_twin.load_project_cycles("PRJ-TEST")
        print(f"    - PRJ-TEST cycle count: {len(cycles_prj_test)}")
        if cycles_prj_test:
            # Try generating a report for its first cycle
            c_id = cycles_prj_test[0]["cycle_id"]
            rep_test = generate_assurance_report("PRJ-TEST", c_id)
            assert rep_test["section_1_executive_summary"]["cycle_id"] == c_id
        print("    - Scenario 6: SUCCESS (PRJ-TEST integrates seamlessly)")

        # ────────────────────────────────────────────────────────
        # Scenario 7: TypeScript compiles cleanly
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 7: TypeScript Compile Verification...")
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
            raise AssertionError("TypeScript compilation failed")

        # ────────────────────────────────────────────────────────
        # Scenario 8: Print Preview / Printing endpoint verification
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 8: Print API Query Param Check...")
        # Get normal report
        response_normal = client.get(f"/projects/{temp_project}/cycles/cycle-001/report?format=html")
        assert response_normal.status_code == 200
        assert "window.print()" not in response_normal.text

        # Get print-triggered report
        response_print = client.get(f"/projects/{temp_project}/cycles/cycle-001/report?format=html&print=true")
        assert response_print.status_code == 200
        assert "window.print()" in response_print.text
        print("    - Scenario 8: SUCCESS (Print trigger endpoint verified)")

        # ────────────────────────────────────────────────────────
        # Scenario 9: Previous regressions pass
        # ────────────────────────────────────────────────────────
        print("\n[*] Test 9: Previous regressions...")
        import test_phase5
        test_phase5.run_phase5_tests()
        print("    - Scenario 9: SUCCESS (All Phase 0-5 regressions continue passing)")

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
    print("🎉 ALL PHASE 6 REGRESSION TESTS PASSED! 🎉")
    print("=========================================\n")

if __name__ == "__main__":
    run_phase6_tests()
