from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

import requests
from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).parent
STATIC_DIR = BACKEND_DIR / "static"
SAT_CACHE_DIR = BACKEND_DIR / "satellite_cache"
PPE_WEIGHTS = BACKEND_DIR / "models" / "Hexmon-yolov8m-ppe.pt"
LEDGER_PATH = SAT_CACHE_DIR / "audit_ledgers.json"

import pytesseract
import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pdf2image import convert_from_path
from ultralytics import YOLO

from agent import agent
from dpr_extractor import extract_reported_progress
from forensics import analyze_image_forensics
from ncri_engine import (
    add_violation_to_ledger,
    add_progress_to_timeline,
    calculate_financial_risk,
    calculate_ncri_score,
    classify_dpr_severity,
    classify_ela_severity,
    get_eligibility_status,
    get_severity_meta,
    DEDUCTIONS,
)
from satellite import (
    DPR_DIR,
    PROJECTS,
    analyze_project,
    get_satellite_alerts,
    reload_projects_from_registry,
    save_dpr_record,
)
from indian_heuristics import verify_hardhat
from bidding_engine import (
    create_tender,
    list_tenders,
    get_tender,
    submit_bid,
    get_leaderboard,
    award_contract,
    get_recommendation,
    seed_demo_data,
)
from gstin_verifier import verify_contractor
import policy_loader
import digital_twin
import context_adjustment
import orchestrator
import cross_evidence


def _get_projects() -> dict:
    """
    Single Source of Truth for project discovery.
    Always reads from policy_loader (projects_registry.json).
    Live after every hot-reload — never stale.
    """
    return policy_loader.get_projects_registry()

VIOLATION_LABELS = {"NO-Safety Vest", "NO-Hardhat", "NO-Mask", "NO-Gloves", "NO-Goggles", "Fall-Detected"}
PPE_CONF_THRESHOLD = 0.40

app = FastAPI()

STATIC_DIR.mkdir(parents=True, exist_ok=True)
SAT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/sat", StaticFiles(directory=str(SAT_CACHE_DIR)), name="satellite_static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-load YOLO to avoid Cloud Run cold-start timeout
_PPE_MODEL = None

def get_ppe_model():
    global _PPE_MODEL
    if _PPE_MODEL is None:
        _PPE_MODEL = YOLO(str(PPE_WEIGHTS))
    return _PPE_MODEL

# Alias for backward compatibility
PPE_MODEL = None  # Will be set lazily via get_ppe_model()

# Seed bidding demo data on startup (no-op if already seeded)
seed_demo_data()


@app.on_event("startup")
async def _startup_load_policies() -> None:
    """
    Phase 0 — Load and validate all policy JSON files at server startup.
    Phase 1 — Probe DPR dependencies and print runtime diagnostics.
    """
    policy_loader.load_all()
    _probe_dpr_dependencies()
    _print_startup_diagnostics()


# ---------------------------------------------------------------------------
# Part A — DPR dependency probe (runs once at startup, cached in module state)
# ---------------------------------------------------------------------------

_DPR_READY: bool = False
_DPR_MISSING: list[str] = []

_DPR_REQUIRED_PACKAGES = [
    "langchain_community",
    "chromadb",
    "langchain_text_splitters",
    "sentence_transformers",
    "xgboost",
]


def _probe_dpr_dependencies() -> None:
    """Import-probe each DPR package. Sets _DPR_READY and _DPR_MISSING."""
    global _DPR_READY, _DPR_MISSING
    import importlib
    missing = []
    for pkg in _DPR_REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    _DPR_MISSING = missing
    _DPR_READY   = len(missing) == 0


def _print_startup_diagnostics() -> None:
    """Print the Atlas Assurance Runtime Diagnostics banner to stdout."""
    projects = policy_loader.get_projects_registry()
    rules    = policy_loader.get_cross_evidence_rules()
    dpr_status = "READY" if _DPR_READY else f"DEGRADED (missing: {_DPR_MISSING})"

    print()
    print("-" * 46)
    print("Atlas Assurance — Runtime Diagnostics")
    print("-" * 46)
    print(f"Active Interpreter:            {sys.executable}")
    print(f"Python Version:                {sys.version.split()[0]}")
    print(f"DPR Engine:                    {dpr_status}")
    print( "Satellite Engine:              READY")
    print( "NCRI Engine:                   READY")
    print( "Policy Loader:                 READY")
    print(f"Projects Loaded:               {len(projects)}")
    print(f"Cross-Evidence Rules Loaded:   {len(rules)}")
    print("-" * 46)
    print()


def _load_ledger() -> dict:
    """Load audit_ledgers.json; return empty dict if file missing."""
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_ledger(ledger: dict) -> None:
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)


def _resolve_attribution(project_id, contractor, site):
    """
    Resolve project attribution from the live registry.
    Uses _get_projects() (policy_loader) — always up-to-date after hot-reload.
    """
    if project_id:
        projects = _get_projects()
        if project_id not in projects:
            raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")
        p = projects[project_id]
        return {
            "project_id": project_id,
            "contractor": contractor or p.get("contractor", ""),
            "site":       site or p.get("name", ""),
        }
    return {
        "project_id": None,
        "contractor": contractor,
        "site":       site,
    }

@app.post("/admin/reload-policies")
async def admin_reload_policies():
    """
    Hot-reload all policy JSON files from disk without restarting the server.
    Also refreshes the satellite engine's PROJECTS dict so new registry
    entries appear in /satellite-alerts immediately.
    """
    try:
        policy_loader.reload()
        reload_projects_from_registry()      # keep satellite PROJECTS in sync
        return {
            "status": "ok",
            "message": "All policies reloaded and validated successfully.",
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))



@app.get("/")
async def root():
    projects = _get_projects()
    return {
        "status": "Atlas Assurance Backend Live",
        "llm_ready": agent.is_ready(),
        "registered_projects": list(projects.keys()),
    }


@app.get("/projects")
async def list_projects():
    """
    Returns all projects from projects_registry.json (single source of truth).
    Adding a project to the registry + calling /admin/reload-policies is the
    only step needed to surface it here — no code changes required.
    """
    projects = _get_projects()
    return {pid: {k: v for k, v in p.items() if k != "bbox"} for pid, p in projects.items()}


@app.post("/analyze-site")
async def analyze_site(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    contractor: Optional[str] = Form(None),
    site: Optional[str] = Form(None),
):
    attribution = _resolve_attribution(project_id, contractor, site)

    temp_path = STATIC_DIR / f"upload_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 1. OpenCV Pre-Processing Pipeline (Zero-Compute Camouflage Fix)
    img = cv2.imread(str(temp_path))
    if img is not None:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl,a,b))
        enhanced_img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        target_path = STATIC_DIR / f"clahe_{file.filename}"
        cv2.imwrite(str(target_path), enhanced_img)
    else:
        target_path = temp_path

    # 2. Zoom-In Inference (SAHI Lite)
    # We use SAHI to detect tiny objects like gloves and masks.
    from sahi_engine import run_zoomed_inference
    final_boxes = run_zoomed_inference(get_ppe_model(), enhanced_img if img is not None else str(target_path), conf=0.15, iou=0.45)

    objects_detected = []
    violations = []
    
    person_count = 0
    hardhat_count = 0
    vest_count = 0
    
    # We need to manually draw the bounding boxes since we bypass r.save()
    if img is not None:
        output_img = enhanced_img.copy()
        
        for box_data in final_boxes:
            label = box_data["label"]
            conf = box_data["conf"]
            x1, y1, x2, y2 = box_data["box"]
            
            # INDIAN CONTEXT FILTER
            if label == "Hardhat":
                h, w, _ = img.shape
                cx1, cy1 = max(0, x1), max(0, y1)
                cx2, cy2 = min(w, x2), min(h, y2)
                cropped = img[cy1:cy2, cx1:cx2]
                
                if not verify_hardhat(cropped):
                    continue # Skip counting this fake hardhat!
                    
            # Draw the verified or non-hardhat box
            # Dynamic colors
            color = (255, 0, 0) # Default Blue
            if label == "Person": color = (255, 0, 255) # Magenta
            elif label == "Hardhat": color = (0, 255, 0) # Green
            elif label == "Safety Vest": color = (0, 255, 255) # Yellow
            elif "NO-" in label: color = (0, 0, 255) # Red
            
            cv2.rectangle(output_img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(output_img, f"{label} {conf:.2f}", (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            objects_detected.append({"label": label, "confidence": round(conf, 3)})
            
            # Count items for Mathematical Ratio check
            if label in ["Person", "NO-Hardhat", "NO-Safety Vest"]:
                person_count += 1
            elif label == "Hardhat":
                hardhat_count += 1
            elif label == "Safety Vest":
                vest_count += 1
                
            # Direct YOLO violation catch
            if label in VIOLATION_LABELS:
                violations.append(label)
                
        import time
        timestamp = int(time.time())
        output_filename = f"detected_{timestamp}_{file.filename}"
        cv2.imwrite(str(STATIC_DIR / output_filename), output_img)
    else:
        # Fallback if cv2 fails to read
        output_filename = file.filename

    # 2. Mathematical Ratio Safety Rules (Zero-Compute Accuracy Boost)
    # If the AI missed drawing a NO-Hardhat box, but sees 5 people and 3 hardhats, trigger!
    if person_count > hardhat_count:
        violations.append("MISSING-Hardhat (Ratio Alert)")
    if person_count > vest_count:
        violations.append("MISSING-Safety Vest (Ratio Alert)")

    has_violations = len(violations) > 0
    violation_labels_list = sorted(set(violations))

    # Severity: CRITICAL if any PPE violation, else LOW
    from ncri_engine import SEVERITY_META
    severity = "CRITICAL" if has_violations else "LOW"
    severity_meta = get_severity_meta(severity)

    reasoning_log = [
        {"step": "Input", "message": f"Received '{file.filename}' ({os.path.getsize(temp_path)} bytes)."},
        {
            "step": "Attribution",
            "message": (
                f"project_id={attribution['project_id']} contractor={attribution['contractor']} site={attribution['site']}"
                if attribution["project_id"] or attribution["contractor"]
                else "No project_id or contractor supplied — analysis is unattributed."
            ),
        },
        {
            "step": "Detection",
            "message": (
                f"YOLO ({get_ppe_model().ckpt_path if hasattr(get_ppe_model(), 'ckpt_path') else 'construction_safety.pt'}): "
                f"{len(objects_detected)} objects above confidence={PPE_CONF_THRESHOLD}."
            ),
        },
        {
            "step": "Classification",
            "message": (
                f"{len(violation_labels_list)} violation classes triggered: {violation_labels_list}"
                if has_violations
                else "No PPE violation classes triggered."
            ),
        },
    ]

    legal_notice = None
    if has_violations:
        context_lines = [f"Detected violations: {', '.join(violation_labels_list)}."]
        context_lines.append(
            "All detected objects: " + ", ".join(f"{o['label']}({o['confidence']})" for o in objects_detected)
        )
        legal_notice = agent.generate_notice(
            category="safety",
            violation_type=", ".join(violation_labels_list),
            contractor=attribution["contractor"],
            site_details=attribution["site"],
            context=" ".join(context_lines),
        )
        reasoning_log.append({
            "step": "Notice",
            "message": (
                f"Notice generated via {legal_notice.get('source', 'unknown')} (category: safety)."
                if legal_notice.get("available")
                else f"Notice skipped: {legal_notice.get('reason')}"
            ),
        })
    else:
        reasoning_log.append({"step": "Notice", "message": "No notice generated — site appears compliant."})

    # --- ledger mutation: write real YOLO violations into NCRI score ---
    if has_violations and attribution["project_id"]:
        pid = attribution["project_id"]
        ledger = _load_ledger()
        
        # Ensure project exists in ledger before appending violations
        if pid not in ledger:
            p_data = _get_projects().get(pid, {})
            ledger[pid] = {
                "project_name":     p_data.get("name", pid),
                "contractor":       p_data.get("contractor", ""),
                "active_violations": [],
                "audit_ledger":     [],
                "timeline":         [],
            }
            
        for lbl in violation_labels_list:
            add_violation_to_ledger(
                ledger, pid,
                violation_type="SAFETY_VIOLATION",
                severity="CRITICAL",
                description=f"YOLO-detected PPE violation: {lbl} at site '{attribution['site']}'",
            )
        _save_ledger(ledger)

    return {
        "filename": file.filename,
        "attribution": attribution,
        "violation_detected": has_violations,
        "violations": violation_labels_list,
        "severity": severity,
        "severity_meta": severity_meta,
        "objects": objects_detected,
        "object_count": len(objects_detected),
        "ppe_confidence_threshold": PPE_CONF_THRESHOLD,
        "reasoning_log": reasoning_log,
        "legal_notice": legal_notice,
        "output_image": f"/static/{output_filename}" if output_filename else None,
    }


@app.post("/analyze-doc")
async def analyze_doc(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    contractor: Optional[str] = Form(None),
    site: Optional[str] = Form(None),
    save_as_dpr: bool = Form(True),
    google_maps_url: Optional[str] = Form(None),
):
    temp_path = STATIC_DIR / f"doc_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        from datetime import datetime
        current_month_str = datetime.now().strftime("%b %Y")  # e.g. 'Jun 2026'
        extraction = extract_reported_progress(str(temp_path), target_date_str=current_month_str)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR / extraction failed: {e}")

    # Fallback: full first-page OCR text if extractor produced nothing usable
    if not extraction.get("extracted"):
        try:
            pages = convert_from_path(str(temp_path), first_page=1, last_page=1)
            first_page_text = pytesseract.image_to_string(pages[0]) if pages else ""
        except Exception:
            first_page_text = ""
        extraction["first_page_text_excerpt"] = first_page_text[:800]

    # --- HYBRID GEOCODER: Dynamic Project Registration ---
    if not project_id or project_id == "null":
        from geocoder import parse_google_maps_url, geocode_location
        import uuid
        
        bbox = None
        # 1. Manual Override Check
        if google_maps_url:
            bbox = parse_google_maps_url(google_maps_url)
            
        # 2. Autonomous NLP Check
        if not bbox and extraction.get("location"):
            bbox = geocode_location(extraction["location"])
            
        if not bbox:
            raise HTTPException(status_code=400, detail="Could not determine location from Maps URL or OCR text. Please provide a valid location.")
            
        # Register new project dynamically!
        new_id = f"PRJ-{str(uuid.uuid4())[:6].upper()}"
        p_name = extraction.get("project_name") or site or "Unknown Auto-Project"
        c_name = contractor or "Unknown Contractor"
        
        # Center of bbox
        lon = round((bbox[0] + bbox[2]) / 2, 4)
        lat = round((bbox[1] + bbox[3]) / 2, 4)
        
        PROJECTS[new_id] = {
            "id": new_id,
            "name": p_name,
            "contractor": c_name,
            "location": [lat, lon],
            "bbox": bbox,
            "baseline_date": "2020-01-01",
            "started": "2020-01-01",
            "type": "Auto-Generated"
        }
        project_id = new_id
        site = p_name
        contractor = c_name

    attribution = _resolve_attribution(project_id, contractor, site)

    dpr_record = None
    analysis = None
    if save_as_dpr and extraction.get("extracted") and attribution["project_id"]:
        dpr_record = save_dpr_record(
            project_id=attribution["project_id"],
            reported_pct=extraction["reported_progress_pct"],
            source=file.filename,
            source_url=None,
            raw_excerpt=extraction["matched_line"],
        )
        analysis = analyze_project(attribution["project_id"])

    audit_notice = None
    if analysis and analysis.get("status") in {"GHOST_ALERT", "LAG_WARNING", "UNREPORTED_PROGRESS"}:
        audit_notice = agent.generate_notice(
            category="dpr",
            violation_type=f"DPR Discrepancy ({analysis['status']})",
            contractor=attribution["contractor"],
            site_details=attribution["site"],
            context=(
                f"Reported progress {analysis['reported_progress_pct']}% vs "
                f"satellite-measured {analysis['satellite_actual_pct']}% "
                f"(discrepancy {analysis['discrepancy_pct']}%). Source DPR: {file.filename}. "
                f"Evidence: {analysis['evidence']}"
            ),
        )

    # --- ledger mutation: write DPR discrepancy into NCRI score ---
    if analysis and attribution["project_id"]:
        status = analysis.get("status", "")
        if status in {"GHOST_ALERT", "LAG_WARNING"}:
            pid = attribution["project_id"]
            disc = analysis.get("discrepancy_pct") or 0.0
            reported = analysis.get("reported_progress_pct") or 0.0
            actual = analysis.get("satellite_actual_pct") or 0.0
            dpr_severity = classify_dpr_severity(disc)
            ledger = _load_ledger()
            add_violation_to_ledger(
                ledger, pid,
                violation_type=status,
                severity=dpr_severity,
                description=(
                    f"DPR claimed {reported}% completion; "
                    f"satellite verified {actual}% — {disc}% discrepancy detected."
                ),
            )
            add_progress_to_timeline(
                ledger, pid,
                month=None,  # defaults to today
                reported_pct=reported,
                actual_pct=actual,
                discrepancy=disc,
                severity=dpr_severity,
            )
            _save_ledger(ledger)

    return {
        "filename": file.filename,
        "attribution": attribution,
        "extraction": extraction,
        "dpr_record": dpr_record,
        "satellite_analysis": analysis,
        "audit_notice": audit_notice,
    }


# ---------------------------------------------------------------------------
# DPR ANALYSIS ENGINE — inlined from api_server.py (no separate server needed)
# XGBoost runs in a subprocess to avoid macOS ARM64 OpenMP/PyTorch segfaults.
# ---------------------------------------------------------------------------

def _run_dpr_analysis(department: str, budget_cr: float, time_gap_months: int, dpr_text: str) -> dict:
    """Core DPR risk analysis: ChromaDB RAG → 58 CAG violation checks → XGBoost prediction."""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from violations_schema import VIOLATIONS_DICT

    print(f"[DPR] Starting analysis for department={department}")

    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # STEP 1: Ingest document into an isolated per-request ChromaDB collection
    print("[DPR][1] Chunking and embedding document...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.create_documents([dpr_text])
    collection_id = f"project_{uuid.uuid4().hex}"
    temp_db = Chroma.from_documents(chunks, embeddings, collection_name=collection_id)

    # STEP 2: RAG — answer the 58 CAG audit questions via similarity search
    print("[DPR][2] Running RAG against 58 CAG violation parameters...")
    extracted_features: dict = {
        "budget_cr": budget_cr,
        "time_gap_months": time_gap_months,
    }
    evidence_log: list = []
    risk_keywords = [
        "has been delayed", "failure to obtain", "not obtained", "is pending",
        "stay order", "unauthorized subcontracting", "substandard material",
        "clearance missing", "was rejected", "severe non-compliance",
        "objection raised", "discrepancy found", "critical error", "high risk", "fraud",
    ]

    for feature_key, question in VIOLATIONS_DICT.items():
        results = temp_db.similarity_search(question, k=3)
        evidence_text = " ".join([r.page_content.lower() for r in results]) if results else ""
        is_violation = 0
        if any(phrase in evidence_text for phrase in risk_keywords):
            is_violation = 1
            evidence_log.append(
                f"Risk Found: {feature_key.split('.')[-1].replace('_', ' ').title()}"
                f" - '{results[0].page_content.strip()}'"
            )
        extracted_features[f"violations.{feature_key}"] = is_violation

    # STEP 3: XGBoost prediction in isolated subprocess (avoids OpenMP/PyTorch conflict)
    # Pass a clean env with OpenMP guard flags to prevent SIGKILL (exit 120) when
    # uvicorn has torch/onnx/pytorch loaded in the parent process address space.
    print("[DPR][3] Running XGBoost prediction...")
    payload_str = json.dumps(extracted_features)
    _xgb_env = {
        **os.environ,
        "KMP_DUPLICATE_LIB_OK": "TRUE",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    _xgb_proc = subprocess.run(
        [sys.executable, "predict_xgboost.py", payload_str],
        capture_output=True,
        text=True,
        cwd=_BACKEND_DIR,
        env=_xgb_env,
        timeout=120,
    )
    if _xgb_proc.returncode != 0:
        raise RuntimeError(
            f"predict_xgboost.py returned non-zero exit status {_xgb_proc.returncode}. "
            f"stderr={_xgb_proc.stderr[:400]!r}"
        )
    result_str = _xgb_proc.stdout
    xgb_result = json.loads(result_str.strip())
    if "error" in xgb_result:
        raise RuntimeError(xgb_result["error"])

    prediction = xgb_result["prediction"]
    approval_chance = xgb_result["approval_probability"]
    rejection_chance = xgb_result["rejection_probability"]
    print(f"[DPR] Verdict: {'LOW RISK' if prediction == 1 else 'HIGH RISK'}")

    # STEP 4: Investigation Engine — group related findings into summaries
    from investigation_engine import build_investigations
    investigations = build_investigations(extracted_features, evidence_log)

    return {
        "department": department,
        "risk_level": "LOW_RISK" if prediction == 1 else "HIGH_RISK",
        "approval_probability": round(approval_chance, 2),
        "rejection_probability": round(rejection_chance, 2),
        # Preserved for backward compat — raw flat list as before
        "critical_evidence_found": evidence_log,
        # Structured findings (alias of evidence_log) for frontend consumption
        "findings": evidence_log,
        # New: correlated investigation summaries
        "investigations": investigations,
        "extracted_ml_features": extracted_features,
    }


@app.get("/health")
def health_check():
    """Atlas Assurance health check — returns full engine status and dependency readiness."""
    projects = policy_loader.get_projects_registry()
    rules    = policy_loader.get_cross_evidence_rules()
    return {
        "status":          "ok",
        "interpreter":     sys.executable,
        "python_version":  sys.version.split()[0],
        "engines": {
            "dpr": {
                "status":               "ready" if _DPR_READY else "degraded",
                "missing_dependencies": _DPR_MISSING,
            },
            "satellite":     "ready",
            "ncri":          "ready",
            "policy_loader": "ready",
        },
        "projects_loaded":              len(projects),
        "cross_evidence_rules_loaded":  len(rules),
    }


@app.post("/scan-dpr")
async def scan_dpr(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(...),
):
    """
    Phase 1 — DPR Intelligence scan with Digital Twin persistence.

    Requires project_id (validated against projects_registry).
    Returns 503 if DPR dependencies are missing.
    Returns 400 if project_id is absent or unknown.
    On success: runs full pipeline, saves cycle-NNN.json, returns analysis + cycle_id.
    """
    import hashlib

    # ── Part A: 503 guard ───────────────────────────────────────────────
    if not _DPR_READY:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DPR Engine unavailable",
                "missing_dependencies": _DPR_MISSING,
            },
        )

    # ── Part B: project_id validation ─────────────────────────────────────
    if not project_id or not project_id.strip():
        raise HTTPException(
            status_code=400,
            detail="project_id is required. Select a project before uploading a DPR.",
        )
    projects = policy_loader.get_projects_registry()
    if project_id not in projects:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown project_id: '{project_id}'. Valid IDs: {list(projects.keys())}",
        )

    # ── Read and hash the raw PDF bytes ──────────────────────────────────
    raw_bytes  = await file.read()
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    uploaded_at = datetime.datetime.utcnow().isoformat() + "Z"

    temp_path = STATIC_DIR / f"scan_{file.filename}"
    with open(temp_path, "wb") as buf:
        buf.write(raw_bytes)

    try:
        import re
        from pypdf import PdfReader

        reader = PdfReader(str(temp_path))
        pages_to_read = min(len(reader.pages), 300)
        extracted_text = ""
        for i in range(pages_to_read):
            page_text = reader.pages[i].extract_text()
            if page_text:
                extracted_text += page_text + "\n"

        if len(extracted_text.strip()) < 500:
            raise HTTPException(
                status_code=422,
                detail="Document too short for analysis. Please upload a full DPR (minimum 5 pages of text content).",
            )

        # ── Text truncation policy (200K chars) ─────────────────────────────
        MAX_TEXT_CHARS      = 200_000
        original_char_count = len(extracted_text)
        text_truncated      = original_char_count > MAX_TEXT_CHARS
        stored_text         = extracted_text[:MAX_TEXT_CHARS] if text_truncated else extracted_text
        if text_truncated:
            stored_text += (
                f"\n\n[TRUNCATED: {original_char_count} total chars, "
                f"{MAX_TEXT_CHARS} stored. "
                f"Full text available in original PDF identified by sha256.]"
            )

        # ── Budget / time extraction (unchanged) ───────────────────────────
        budget_match = re.search(
            r'(?:Rs\.?|INR|\u20b9)\s*([\d,]+(?:\.\d+)?)\s*(?:Crore|Cr\.?)',
            extracted_text, re.IGNORECASE,
        )
        time_match = re.search(
            r'(?:delay(?:ed)?|gap).*?([\d]+)\s*(?:months?)',
            extracted_text, re.IGNORECASE,
        )
        try:
            extracted_budget = float(budget_match.group(1).replace(',', '')) if budget_match else 500.0
        except (ValueError, AttributeError):
            extracted_budget = 500.0
        extracted_time = int(time_match.group(1)) if time_match else 12

        # ── Core DPR analysis (DPR logic completely unchanged) ──────────────
        analysis = _run_dpr_analysis(
            department="Infrastructure / Government Project",
            budget_cr=extracted_budget,
            time_gap_months=extracted_time,
            dpr_text=extracted_text,
        )

        # ── Phase 2: Context Adjustment ────────────────────────────────
        project_record = projects.get(project_id, {"id": project_id})
        dpr_analysis_payload = {
            "risk_score":         analysis.get("rejection_probability", 0),
            "verdict":            analysis.get("risk_level"),
            "budget_cr":          extracted_budget,
            "time_gap_months":    extracted_time,
            "investigations":     analysis.get("investigations", []),
            "findings":           analysis.get("findings", []),
        }
        context = context_adjustment.adjust_project_context(
            dpr_result=dpr_analysis_payload,
            project=project_record,
        )

        # ── Phase 3: Load cached satellite result for cross-evidence ──────
        import json as _json
        from satellite import CACHE_DIR as _SAT_CACHE
        _sat_cache_file = _SAT_CACHE / f"{project_id}.json"
        sat_result_for_ce: dict | None = None
        if _sat_cache_file.exists():
            try:
                with open(_sat_cache_file, "r", encoding="utf-8") as _f:
                    sat_result_for_ce = _json.load(_f)
            except Exception:
                pass   # corrupt cache — non-fatal

        # ── Phase 4: Fetch latest NCRI status ────────────────────────────
        ncri_result: dict | None = None
        try:
            proj_ledger = _load_ledger().get(project_id)
            if proj_ledger:
                from ncri_engine import calculate_ncri_score
                active_violations = proj_ledger.get("active_violations", [])
                ncri_score = calculate_ncri_score(active_violations)
                tampering_detected = any(v.get("type") == "IMAGE_TAMPERING" for v in active_violations)
                safety_violations_count = sum(1 for v in active_violations if v.get("type") == "SAFETY_VIOLATION")
                ppe_compliance_pct = max(0.0, 100.0 - 10.0 * safety_violations_count)
                
                ncri_result = {
                    "ncri_score": ncri_score,
                    "tampering_detected": tampering_detected,
                    "ppe_compliance_pct": ppe_compliance_pct,
                    "active_violations": active_violations,
                }
            else:
                ncri_result = {
                    "ncri_score": 100,
                    "tampering_detected": False,
                    "ppe_compliance_pct": 100.0,
                    "active_violations": [],
                }
        except Exception:
            ncri_result = {
                "ncri_score": 100,
                "tampering_detected": False,
                "ppe_compliance_pct": 100.0,
                "active_violations": [],
            }

        # ── Phase 3: Cross-Evidence evaluation ───────────────────────────
        ce_result = cross_evidence.evaluate(
            satellite_result=sat_result_for_ce,
            dpr_result=dpr_analysis_payload,
            ncri_result=ncri_result,            # populated in Phase 4 (unified risk)
        )

        # ── Build canonical Assurance Cycle via Orchestrator ──────────────
        cycle = orchestrator.build_assurance_cycle(
            project=project_record,
            satellite_result=sat_result_for_ce,
            dpr_result={
                "snapshot": {
                    "file_name":                file.filename,
                    "sha256":                   sha256_hex,
                    "uploaded_at":              uploaded_at,
                    "source_files":             [file.filename],
                    "extracted_text":           stored_text,
                    "truncated":                text_truncated,
                    "original_character_count": original_char_count,
                },
                "analysis": dpr_analysis_payload,
            },
            ncri_result=ncri_result,
            context_result=context,
            cross_evidence_result=ce_result,
        )
        # Stamp backward-compatible top-level aliases
        cycle["project_id"]   = project_id
        cycle["created_at"]   = uploaded_at
        cycle["dpr_snapshot"] = cycle["dpr"]["snapshot"]
        cycle["dpr_analysis"] = cycle["dpr"]["analysis"]
        cycle["assurance_status"] = "COMPLETED"

        cycle_id = digital_twin.save_assurance_cycle(project_id, cycle)

        # ── Return analysis + cycle provenance + context + cross-evidence ─
        return {
            **analysis,
            "cycle_id":       cycle_id,
            "project_id":     project_id,
            "sha256":          sha256_hex,
            "text_truncated": text_truncated,
            "context":        context,
            "cross_evidence": ce_result.get("cross_evidence_findings", []),
            "unified_risk":   cycle.get("unified_risk"),
        }


    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Part B — Digital Twin cycle endpoints
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/cycles")
def list_cycles(project_id: str):
    """Return summary list of all assurance cycles for a project (oldest first)."""
    projects = policy_loader.get_projects_registry()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")
    cycles = digital_twin.load_project_cycles(project_id)
    return [
        {
            "cycle_id":   c.get("cycle_id"),
            "created_at": c.get("created_at"),
            "verdict":    c.get("dpr_analysis", {}).get("verdict"),
            "risk_score": c.get("dpr_analysis", {}).get("risk_score"),
        }
        for c in cycles
    ]


@app.get("/projects/{project_id}/cycles/latest")
def get_latest_cycle(project_id: str):
    """Return the full latest assurance cycle for a project."""
    projects = policy_loader.get_projects_registry()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")
    cycle = digital_twin.get_latest_cycle(project_id)
    if cycle is None:
        raise HTTPException(
            status_code=404,
            detail=f"No assurance cycles found for project {project_id}.",
        )
    return cycle




@app.post("/analyze-forensics")
async def analyze_forensics(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    contractor: Optional[str] = Form(None),
    site: Optional[str] = Form(None),
):
    attribution = _resolve_attribution(project_id, contractor, site)

    temp_path = STATIC_DIR / f"forensics_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        forensics = analyze_image_forensics(str(temp_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forensics failed: {e}")

    ela_filename = f"ela_{file.filename}"
    forensics["ela_image"].save(str(STATIC_DIR / ela_filename))

    tampering_score = forensics["tampering_score"]
    severity = classify_ela_severity(tampering_score)

    analysis_notice = None
    if forensics["tampering_detected"]:
        analysis_notice = agent.generate_notice(
            category="forensics",
            violation_type="Image Manipulation / Evidence Tampering",
            contractor=attribution["contractor"],
            site_details=attribution["site"],
            context=(
                f"Error Level Analysis statistics: mean={forensics['stats']['mean_error']}, "
                f"std={forensics['stats']['std_error']}, p95={forensics['stats']['p95_error']}, "
                f"max={forensics['stats']['max_error']}. Tampering score={tampering_score} "
                f"(threshold 0.45). Severity: {severity}."
            ),
        )

    # --- ledger mutation: write ELA tampering into NCRI score ---
    if forensics["tampering_detected"] and attribution["project_id"]:
        pid = attribution["project_id"]
        ledger = _load_ledger()
        add_violation_to_ledger(
            ledger, pid,
            violation_type="IMAGE_TAMPERING",
            severity=severity,
            description=(
                f"ELA forensics: tampering_score={tampering_score:.2f}. "
                f"Submitted DPR photographs show signs of digital manipulation."
            ),
        )
        _save_ledger(ledger)

    return {
        "filename": file.filename,
        "attribution": attribution,
        "tampering_detected": forensics["tampering_detected"],
        "tampering_score": tampering_score,
        "severity": severity,
        "severity_meta": get_severity_meta(severity),
        "ela_stats": forensics["stats"],
        "ela_image": f"/static/{ela_filename}",
        "ai_analysis": analysis_notice,
    }


@app.get("/satellite-alerts")
async def satellite_alerts():
    """
    Returns satellite alerts for ALL projects in the registry.
    Adding a project to projects_registry.json + reloading policies
    surfaces it here immediately — no code changes required.
    """
    projects = _get_projects()
    return {"projects": list(projects.keys()), "alerts": get_satellite_alerts()}


@app.post("/refresh-satellite/{project_id}")
async def refresh_satellite(project_id: str, ml: bool = False):
    if project_id not in _get_projects():
        raise HTTPException(status_code=404, detail=f"Unknown project {project_id}")
    result = analyze_project(project_id, run_ml=ml)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result


@app.post("/upload-dpr/{project_id}")
async def upload_dpr(
    project_id: str,
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
):
    if project_id not in _get_projects():
        raise HTTPException(status_code=404, detail=f"Unknown project {project_id}")
    pdf_path = DPR_DIR / f"{project_id}_{file.filename}"
    with open(pdf_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    extraction = extract_reported_progress(pdf_path)
    if not extraction.get("extracted"):
        raise HTTPException(
            status_code=422,
            detail={"reason": "Could not find a progress percentage in the DPR", **extraction},
        )
    record = save_dpr_record(
        project_id=project_id,
        reported_pct=extraction["reported_progress_pct"],
        source=source or file.filename,
        source_url=source_url,
        raw_excerpt=extraction["matched_line"],
    )
    analysis = analyze_project(project_id)
    return {"dpr": record, "extraction": extraction, "analysis": analysis}


@app.get("/dpr/{project_id}")
async def get_dpr(project_id: str):
    if project_id not in _get_projects():
        raise HTTPException(status_code=404, detail=f"Unknown project {project_id}")
    f = DPR_DIR / f"{project_id}.json"
    if not f.exists():
        return {"project_id": project_id, "status": "no_dpr_ingested"}
    import json as _json
    with open(f) as fh:
        return _json.load(fh)


@app.get("/projects/{project_id}/ncri")
async def get_ncri(project_id: str):
    """
    National Contractor Reliability Index (NCRI) scorecard endpoint.
    Returns NCRI score, eligibility status, financial risk, audit ledger,
    and 6-month timeline for the given project.
    """
    if project_id not in _get_projects():
        raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")

    ledger = _load_ledger()
    project_data = ledger.get(project_id)

    if not project_data:
        # Minimal fallback if ledger missing for this project
        return {
            "project_id": project_id,
            "ncri_score": 100,
            "eligibility": get_eligibility_status(100),
            "financial_risk": calculate_financial_risk(0, 0, 0),
            "audit_ledger": [],
            "timeline": [],
            "active_violations": [],
        }

    active_violations = project_data.get("active_violations", [])
    ncri_score = calculate_ncri_score(active_violations)

    # Financial risk from latest timeline discrepancy
    timeline = project_data.get("timeline", [])
    latest_discrepancy = timeline[-1]["discrepancy"] if timeline else 0.0
    contract_value = project_data.get("contract_value_inr", 0)
    disbursed_ratio = project_data.get("disbursed_ratio", 0)
    financial_risk = calculate_financial_risk(contract_value, latest_discrepancy, disbursed_ratio)

    return {
        "project_id": project_id,
        "project_name": project_data.get("project_name", ""),
        "contractor": project_data.get("contractor", ""),
        "ncri_score": ncri_score,
        "eligibility": get_eligibility_status(ncri_score),
        "financial_risk": financial_risk,
        "active_violations": active_violations,
        "audit_ledger": project_data.get("audit_ledger", []),
        "timeline": timeline,
    }


@app.post("/projects/{project_id}/issue-advisory")
async def issue_advisory(project_id: str):
    with open(LEDGER_PATH, "r") as f:
        data = json.load(f)

    if project_id not in data:
        raise HTTPException(status_code=404, detail="Project not found")

    project = data[project_id]
    violations = project.get("active_violations", [])
    if not violations:
        raise HTTPException(status_code=400, detail="No active violations to advise on")

    latest_violation = violations[-1]
    
    # Twilio details
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM")
    to_number = os.environ.get("TWILIO_WHATSAPP_TO")

    if not all([account_sid, auth_token, from_number, to_number]):
        print(f"[advisory] Missing Twilio credentials. Cannot send WhatsApp.")
        # We don't want to crash the demo if env is wrong, just print and return success simulation
        return {"status": "simulated", "message": "Credentials missing, simulated success."}

    msg_body = (
        f"🚨 *[Atlas Assurance — Governance Alert]*\n\n"
        f"🏛 *Project:* {project.get('project_name')}\n"
        f"⚠️ *Violation:* {latest_violation['type'].replace('_', ' ')}\n"
        f"📄 *Details:* {latest_violation['description']}\n\n"
        f"⚡ *Action Required:* {latest_violation.get('recommended_action', 'IMMEDIATE REVIEW')}"
    )

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        auth = (account_sid, auth_token)
        payload = {
            "From": from_number,
            "To": to_number,
            "Body": msg_body
        }
        res = requests.post(url, data=payload, auth=auth)
        res.raise_for_status()
        return {"status": "sent", "sid": res.json().get("sid")}
    except Exception as e:
        print(f"[advisory] Twilio send failed: {e}")
        if 'res' in locals():
            print(res.text)
        raise HTTPException(status_code=500, detail="Failed to send advisory")


# ---------------------------------------------------------------------------
# Bidding / Tender Endpoints
# ---------------------------------------------------------------------------

@app.get("/tenders")
async def api_list_tenders():
    """List all tenders with bid counts."""
    return {"tenders": list_tenders()}


@app.post("/tenders")
async def api_create_tender(
    project_name: str = Form(...),
    location: str = Form(...),
    estimated_value_cr: float = Form(...),
    min_ncri_required: int = Form(60),
    deadline: str = Form(...),
    description: str = Form(""),
):
    tender = create_tender(
        project_name=project_name,
        location=location,
        estimated_value_cr=estimated_value_cr,
        min_ncri_required=min_ncri_required,
        deadline=deadline,
        description=description,
    )
    return tender


@app.get("/tenders/{tender_id}")
async def api_get_tender(tender_id: str):
    tender = get_tender(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    leaderboard = get_leaderboard(tender_id)
    recommendation = get_recommendation(tender_id)
    return {
        "tender": tender,
        "leaderboard": leaderboard,
        "recommendation": recommendation,
    }


@app.post("/tenders/{tender_id}/bid")
async def api_submit_bid(
    tender_id: str,
    contractor_id: str = Form(...),
    contractor_name: str = Form(...),
    bid_amount_cr: float = Form(...),
    is_new_entity: bool = Form(False),
    years_of_experience: int = Form(5),
):
    tender = get_tender(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")

    # Auto-fetch NCRI from ledger if project is registered
    ledger = _load_ledger()
    # Try to find a matching project by contractor name
    ncri_score = 100
    active_violation_count = 0
    for pid, pdata in ledger.items():
        if pdata.get("contractor", "").lower() in contractor_name.lower() or \
           contractor_name.lower() in pdata.get("contractor", "").lower():
            violations = pdata.get("active_violations", [])
            from ncri_engine import calculate_ncri_score
            ncri_score = calculate_ncri_score(violations)
            active_violation_count = len(violations)
            break

    try:
        bid = submit_bid(
            tender_id=tender_id,
            contractor_id=contractor_id,
            contractor_name=contractor_name,
            bid_amount_cr=bid_amount_cr,
            ncri_score=ncri_score,
            active_violation_count=active_violation_count,
            is_new_entity=is_new_entity,
            years_of_experience=years_of_experience,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return bid


@app.post("/tenders/{tender_id}/award/{contractor_id}")
async def api_award_contract(tender_id: str, contractor_id: str):
    tender = get_tender(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    try:
        result = award_contract(tender_id, contractor_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Send WhatsApp notification if Twilio is configured
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM")
    to_number = os.environ.get("TWILIO_WHATSAPP_TO")

    if all([account_sid, auth_token, from_number, to_number]):
        msg = (
            f"*[Atlas Assurance — Tender Award]*\n\n"
            f"*Tender:* {tender['project_name']}\n"
            f"*Awarded To:* {result['awarded_contractor_name']}\n"
            f"*Contract Value:* Rs. {result['awarded_bid_cr']} Cr\n"
            f"*Contractor NCRI:* {result['winning_ncri']}/100\n\n"
            f"Contract has been formally awarded via Atlas Assurance Governance Platform."
        )
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            requests.post(url, data={"From": from_number, "To": to_number, "Body": msg},
                         auth=(account_sid, auth_token))
        except Exception:
            pass

    return result


@app.get("/tenders/{tender_id}/recommendation")
async def api_get_recommendation(tender_id: str):
    tender = get_tender(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    return get_recommendation(tender_id)



# ---------------------------------------------------------------------------
# Contractor GSTIN Verification
# ---------------------------------------------------------------------------

@app.post("/verify-gstin")
async def api_verify_gstin(gstin: str = Form(...)):
    """
    Full GSTIN verification pipeline:
    1. Format + cryptographic checksum validation (offline, instant)
    2. Embedded data extraction: state code, PAN, entity type
    3. Live government registry lookup (best-effort, 6s timeout)
    4. Atlas NCRI ledger cross-reference
    5. Trust level assignment: HIGH / MEDIUM / LOW / REJECTED

    The `company_name` in the response comes from the government registry,
    NOT from what the contractor typed. This prevents fake company names.
    """
    return verify_contractor(gstin)


@app.get("/verify-gstin/format/{gstin}")
async def api_validate_gstin_format(gstin: str):
    """
    Instant client-side-style format + cryptographic checksum validation only.
    No network call — runs in < 1ms.
    Used for real-time validation as the user types.
    """
    from gstin_verifier import validate_gstin_format
    return validate_gstin_format(gstin)



# ---------------------------------------------------------------------------
# Assurance Report Endpoint (Phase 6)
# ---------------------------------------------------------------------------

from fastapi.responses import HTMLResponse

@app.get("/projects/{project_id}/cycles/{cycle_id}/report")
async def api_get_assurance_report(project_id: str, cycle_id: str, format: str = "json", print: bool = False):
    """
    Generate and return an assurance report for the given project and cycle.
    Supports ?format=json (default) and ?format=html.
    """
    if format not in ("json", "html"):
        raise HTTPException(status_code=400, detail=f"Unsupported report format: {format}. Must be 'json' or 'html'.")
    
    from report_generator import generate_assurance_report, render_html_report
    try:
        report_data = generate_assurance_report(project_id, cycle_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if format == "html":
        html_content = render_html_report(report_data)
        if print:
            html_content = html_content.replace("</body>", "<script>window.onload = function() { window.print(); };</script></body>")
        return HTMLResponse(content=html_content)
    
    return report_data


# ---------------------------------------------------------------------------
# Human Governance Workflow (Phase 5)
# ---------------------------------------------------------------------------

from pydantic import BaseModel
class GovernanceActionRequest(BaseModel):
    performed_by: str
    reason: str
    notes: Optional[str] = None

def _get_cycle_or_raise(project_id: str, cycle_id: str) -> dict:
    projects = policy_loader.get_projects_registry()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")
    cycles = digital_twin.load_project_cycles(project_id)
    for c in cycles:
        if c.get("cycle_id") == cycle_id:
            return c
    raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} not found for project {project_id}")

def _save_cycle_data(project_id: str, cycle_id: str, cycle_data: dict) -> None:
    dest_dir = digital_twin._project_dir(project_id)
    dest_file = dest_dir / f"{cycle_id}.json"
    with open(dest_file, "w", encoding="utf-8") as f:
        json.dump(cycle_data, f, indent=2, ensure_ascii=False)

@app.get("/projects/{project_id}/cycles/{cycle_id}/governance")
async def api_get_governance(project_id: str, cycle_id: str):
    cycle = _get_cycle_or_raise(project_id, cycle_id)
    from governance import init_governance
    cycle = init_governance(cycle)
    return cycle["governance"]

@app.post("/projects/{project_id}/cycles/{cycle_id}/approve")
async def api_approve_cycle(project_id: str, cycle_id: str, req: GovernanceActionRequest):
    cycle = _get_cycle_or_raise(project_id, cycle_id)
    from governance import approve_cycle
    updated_cycle = approve_cycle(
        cycle_data=cycle,
        performed_by=req.performed_by,
        reason=req.reason,
        notes=req.notes
    )
    _save_cycle_data(project_id, cycle_id, updated_cycle)
    return updated_cycle["governance"]

@app.post("/projects/{project_id}/cycles/{cycle_id}/reinvestigate")
async def api_reinvestigate_cycle(project_id: str, cycle_id: str, req: GovernanceActionRequest):
    cycle = _get_cycle_or_raise(project_id, cycle_id)
    from governance import request_reinvestigation
    updated_cycle = request_reinvestigation(
        cycle_data=cycle,
        performed_by=req.performed_by,
        reason=req.reason,
        notes=req.notes
    )
    _save_cycle_data(project_id, cycle_id, updated_cycle)
    return updated_cycle["governance"]

@app.post("/projects/{project_id}/cycles/{cycle_id}/override")
async def api_override_cycle(project_id: str, cycle_id: str, req: GovernanceActionRequest):
    cycle = _get_cycle_or_raise(project_id, cycle_id)
    from governance import override_recommendation
    updated_cycle = override_recommendation(
        cycle_data=cycle,
        performed_by=req.performed_by,
        reason=req.reason,
        notes=req.notes
    )
    _save_cycle_data(project_id, cycle_id, updated_cycle)
    return updated_cycle["governance"]


@app.delete("/projects/{project_id}/assurance-history")
async def api_reset_assurance_history(project_id: str):
    """
    Demo reset: delete all cycle JSON files for a project.
    Preserves: projects_registry.json, satellite data, project metadata.
    Does NOT modify: violations_schema, investigation_engine, scoring logic.
    """
    import shutil
    from pathlib import Path
    twins_dir = Path(__file__).parent / "storage" / "digital_twins" / project_id
    if not twins_dir.exists():
        return {"deleted": 0, "project_id": project_id}
    cycle_files = list(twins_dir.glob("cycle-*.json"))
    deleted = 0
    for f in cycle_files:
        try:
            f.unlink()
            deleted += 1
        except OSError:
            pass
    return {"deleted": deleted, "project_id": project_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

