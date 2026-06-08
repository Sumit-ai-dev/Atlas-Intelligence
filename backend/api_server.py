import os
import sys
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import uvicorn
import warnings

# Suppress warnings for clean output
# warnings.filterwarnings("ignore")

app = FastAPI(title="Atlas Assurance Backend API", description="Unifies RAG and XGBoost for infrastructure governance.")

# --- 1. Global AI Model Loading ---
# We load them lazily inside the endpoint to prevent macOS OpenMP Segfaults between PyTorch and XGBoost
print("[*] API Server Ready. Models will be loaded dynamically upon request.")

# --- 2. Request Models ---
class AnalyzeRequest(BaseModel):
    department: str
    budget_cr: float
    time_gap_months: int
    dpr_text: str  # The raw text of the 500-page document uploaded by the user

# --- 3. The Core API Endpoint ---
@app.post("/analyze")
def analyze_project(req: AnalyzeRequest):
    print(f"\n--- New Request Received for {req.department} ---")
    
    print("[*] Booting up Atlas Assurance Backend Engines dynamically...")
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    vector_db = Chroma(
        collection_name="infra_dpr_collection",
        embedding_function=embeddings,
        persist_directory="./chroma_db"
    )
    
    # STEP 1: INGEST DOCUMENT INTO RAG
    print("[1] Ingesting document into RAG...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.create_documents([req.dpr_text])
    
    # CRITICAL FIX: Ensure complete isolation between API requests
    import uuid
    collection_id = f"project_{uuid.uuid4().hex}"
    temp_db = Chroma.from_documents(chunks, embeddings, collection_name=collection_id)
    
    # STEP 2: USE RAG TO ANSWER THE 58 CAG AUDIT QUESTIONS
    print("[2] RAG Engine scanning document for risk factors (58 Enterprise Parameters)...")
    
    # We dynamically load the 58 questions the XGBoost model needs answered
    from violations_schema import VIOLATIONS_DICT
    violation_checks = VIOLATIONS_DICT
    
    extracted_features = {
        "budget_cr": req.budget_cr,
        "time_gap_months": req.time_gap_months
    }
    
    evidence_log = []
    
    for feature_key, question in violation_checks.items():
        # Reduce k to 3 to avoid pulling noisy Table of Contents pages
        results = temp_db.similarity_search(question, k=3)
        evidence_text = " ".join([r.page_content.lower() for r in results]) if results else ""
        
        # Strict NLP Heuristic: Only flag if explicit legal failure phrases are found
        risk_keywords = ["has been delayed", "failure to obtain", "not obtained", "is pending", "stay order", "unauthorized subcontracting", "substandard material", "clearance missing", "was rejected", "severe non-compliance", "objection raised", "discrepancy found", "critical error", "high risk", "fraud"]
        
        is_violation = 0
        if any(phrase in evidence_text for phrase in risk_keywords):
            is_violation = 1
            evidence_log.append(f"Risk Found: {feature_key.split('.')[-1].replace('_', ' ').title()} - '{results[0].page_content.strip()}'")
            
        extracted_features[f"violations.{feature_key}"] = is_violation

    # STEP 3: FEED EXTRACTED FEATURES INTO XGBOOST
    print("[3] Feeding RAG-extracted features into isolated XGBoost process...")
    
    import subprocess
    import json
    import sys
    
    # Run XGBoost in an entirely isolated memory space to avoid macOS ARM64 OpenMP Segfaults
    try:
        payload_str = json.dumps(extracted_features)
        result_str = subprocess.check_output(
            [sys.executable, "predict_xgboost.py", payload_str],
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        xgb_result = json.loads(result_str.strip())
        
        if "error" in xgb_result:
            raise Exception(xgb_result["error"])
            
        prediction = xgb_result["prediction"]
        approval_chance = xgb_result["approval_probability"]
        rejection_chance = xgb_result["rejection_probability"]
        
    except Exception as e:
        print(f"[!] Subprocess Error: {e}")
        raise HTTPException(status_code=500, detail="XGBoost Core Error")
        
    print(f"--> Final Verdict: {'LOW RISK' if prediction == 1 else 'HIGH RISK'}")
    
    # Return everything to the React Frontend
    return {
        "department": req.department,
        "risk_level": "LOW_RISK" if prediction == 1 else "HIGH_RISK",
        "approval_probability": round(approval_chance, 2),
        "rejection_probability": round(rejection_chance, 2),
        "critical_evidence_found": evidence_log,
        "extracted_ml_features": extracted_features
    }

if __name__ == "__main__":
    print("[*] Starting API Server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
