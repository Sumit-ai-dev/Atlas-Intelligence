# Atlas Intelligence

**Autonomous Assurance for Physical Infrastructure**  
FAR AWAY 2026 — Agentic & Autonomous Systems

---

## Live Deployments

| Service | URL |
|---|---|
| Frontend | https://infra-ai-frontend-5fvzoiirja-ew.a.run.app |
| Backend API | https://infra-ai-governance-mvp-5fvzoiirja-ew.a.run.app |
| API Docs | https://infra-ai-governance-mvp-5fvzoiirja-ew.a.run.app/docs |

---

## What This Is

Infrastructure projects generate massive volumes of evidence — DPRs, budgets, satellite imagery, site photos, contractor records, compliance reports. These streams are reviewed in silos, manually, and long after problems have already developed.

Atlas Intelligence connects these streams. It ingests project intent (the DPR), tracks how reality evolves during execution, and surfaces discrepancies before they become failures. Oversight shifts from periodic audits to continuous assurance.

The core principle: **Atlas recommends. Humans decide.** The system highlights risks and generates investigation outputs, but every consequential action requires a human approval.

---

## The Problem

Current infrastructure oversight has four structural gaps:

1. **Delayed visibility** — Audits happen periodically. By the time issues are found, corrective action is expensive.
2. **Fragmented evidence** — Plans, satellite data, site photos, contractor history, and inspection reports are never correlated.
3. **Static expectations** — DPRs are written at project initiation but executed over years. Inflation, cost escalation, and regulatory changes are never factored into subsequent reviews.
4. **Cognitive overload** — Auditors manually process thousands of pages of documentation while simultaneously identifying anomalies and assessing severity.

---

## System Design

### High-Level Architecture

```mermaid
graph TB
    subgraph Client["Frontend - Next.js"]
        UI[Executive Dashboard]
        DPRPage[DPR Validator]
        SatPage[Satellite View]
        SafePage[SiteGuard]
        ForPage[TruthLens]
        ProcPage[Contractor Trust]
        FraudPage[Fraud Analytics]
    end

    subgraph Gateway["API Layer - FastAPI"]
        API[REST API]
        Docs[Swagger UI]
    end

    subgraph Orchestration["Orchestrator"]
        Orch[agent.py + orchestrator.py]
    end

    subgraph Agents["Specialist Agents"]
        Planning[Planning Agent]
        Verify[Verification Agent]
        Invest[Investigation Agent]
        Gov[Governance Agent]
        Proc[Procurement Agent]
    end

    subgraph Models["ML Models"]
        YOLO[YOLOv8 - PPE Detection]
        CF[ChangeFormerV6 - Satellite]
        XGB[XGBoost - Contractor Risk]
        ELA[ELA - Image Forensics]
        LLM[Mistral 7B - Reasoning]
        OCR[Tesseract OCR]
    end

    subgraph Storage["Storage"]
        Chroma[(ChromaDB Vector Store)]
        Policies[(Policy JSONs)]
        Cache[(Satellite Cache)]
        Files[(File Store)]
    end

    subgraph Infra["Infrastructure"]
        CR1[Cloud Run - Backend]
        CR2[Cloud Run - Frontend]
        CB[Cloud Build - CI/CD]
    end

    UI --> API
    DPRPage --> API
    SatPage --> API
    SafePage --> API
    ForPage --> API
    ProcPage --> API
    FraudPage --> API

    API --> Orch
    Orch --> Planning
    Orch --> Verify
    Orch --> Invest
    Orch --> Gov
    Orch --> Proc

    Planning --> OCR
    Planning --> LLM
    Planning --> Chroma

    Verify --> CF
    Verify --> YOLO
    Verify --> Cache

    Invest --> ELA
    Invest --> LLM
    Invest --> Policies

    Gov --> LLM
    Gov --> Policies

    Proc --> XGB
    Proc --> Chroma

    CR1 --- API
    CR2 --- UI
    CB --> CR1
    CB --> CR2
```

### Assurance Workflow

```mermaid
sequenceDiagram
    actor Authority
    participant Dashboard
    participant Orchestrator
    participant PlanningAgent
    participant VerifyAgent
    participant InvestAgent
    participant GovAgent
    participant Human

    Authority->>Dashboard: Upload DPR + Project Metadata
    Dashboard->>Orchestrator: POST /projects/{id}/dpr
    Orchestrator->>PlanningAgent: Extract baseline from DPR
    PlanningAgent-->>Orchestrator: Project Digital Twin + Expectations

    Note over Orchestrator: Contractor requests milestone payment

    Orchestrator->>VerifyAgent: Run parallel verification
    par Satellite Check
        VerifyAgent->>VerifyAgent: OrbitVerify (ChangeFormerV6)
    and Safety Check
        VerifyAgent->>VerifyAgent: SiteGuard (YOLOv8)
    and Evidence Integrity
        VerifyAgent->>VerifyAgent: TruthLens (ELA)
    end
    VerifyAgent-->>Orchestrator: Verification findings

    Orchestrator->>InvestAgent: Correlate findings
    InvestAgent-->>Orchestrator: Investigation narrative + severity

    Orchestrator->>GovAgent: Generate recommendations
    GovAgent-->>Orchestrator: Risk classification + actions

    Orchestrator->>Dashboard: Assurance report ready
    Dashboard->>Human: Present findings for decision

    alt Approve
        Human->>Dashboard: Approve recommendation
    else Request Reinvestigation
        Human->>Dashboard: Request more evidence
        Dashboard->>Orchestrator: Trigger new cycle
    else Override
        Human->>Dashboard: Override with own judgment
    end

    Dashboard-->>Authority: Decision recorded in audit trail
```

### Data Model

```mermaid
erDiagram
    PROJECT {
        string id PK
        string name
        string location
        float sanctioned_budget
        date start_date
        date expected_completion
        string status
    }

    DIGITAL_TWIN {
        string project_id FK
        json milestones
        json budget_allocations
        json contractor_assignments
        json baseline_expectations
        timestamp created_at
    }

    ASSURANCE_CYCLE {
        string id PK
        string project_id FK
        timestamp triggered_at
        string trigger_reason
        float overall_risk_score
        string status
    }

    EVIDENCE {
        string id PK
        string cycle_id FK
        string type
        string source
        string file_path
        json metadata
        timestamp collected_at
    }

    FINDING {
        string id PK
        string cycle_id FK
        string module
        string severity
        float confidence
        text description
        json supporting_evidence
    }

    DECISION {
        string id PK
        string cycle_id FK
        string decision_type
        string decided_by
        text notes
        timestamp decided_at
    }

    CONTRACTOR {
        string id PK
        string gstin
        string name
        float ncri_score
        string risk_category
        json historical_flags
    }

    PROJECT ||--|| DIGITAL_TWIN : "has baseline"
    PROJECT ||--o{ ASSURANCE_CYCLE : "undergoes"
    ASSURANCE_CYCLE ||--o{ EVIDENCE : "collects"
    ASSURANCE_CYCLE ||--o{ FINDING : "produces"
    ASSURANCE_CYCLE ||--o| DECISION : "concludes with"
    PROJECT }o--o{ CONTRACTOR : "assigned to"
```

---

## Architecture Layers

| Layer | Responsibility |
|---|---|
| Project Baseline | Ingests DPR, constructs Project Digital Twin |
| Context Adjustment | Adjusts expectations for inflation, cost escalation, and time |
| Evidence Collection | Gathers satellite observations, site photos, forensic images |
| Investigation | Correlates evidence streams, explains discrepancies |
| Governance | Generates risk classifications and recommended actions |
| Human Decision | Final approval, override, or escalation — recorded for audit |

---

## What We Built

### Backend (FastAPI + Python)

| Module | File | What it does |
|---|---|---|
| DPR Intelligence (DeepScan) | `dpr_extractor.py`, `rag_engine.py` | OCR, budget/timeline extraction, RAG over uploaded DPRs |
| Project Digital Twin | `digital_twin.py` | Persists structured project baseline from DPR |
| Context Adjustment | `context_adjustment.py` | Adjusts expectations for inflation, time elapsed |
| Satellite Assurance (OrbitVerify) | `satellite.py`, `change_detector_ml.py` | ChangeFormerV6-based progress verification from satellite imagery |
| Safety Assurance (SiteGuard) | `main.py` (vision endpoints) | YOLOv8-based PPE detection and worker compliance on site photos |
| Evidence Integrity (TruthLens) | `forensics.py` | Error Level Analysis (ELA) for image tampering detection |
| Procurement Assurance (ProcureSense) | `ncri_engine.py`, `bidding_engine.py` | XGBoost-based contractor risk scoring (NCRI), GSTIN verification |
| Cross-Evidence Investigation | `investigation_engine.py`, `cross_evidence.py` | Correlates satellite + DPR + safety findings into a narrative |
| Governance & Recommendations | `governance.py`, `policy_loader.py` | Risk classification, recommended actions, escalation pathways |
| Report Generation | `report_generator.py` | PDF assurance reports with findings and audit trail |
| Orchestrator | `orchestrator.py`, `agent.py` | Coordinates the agent workflow across modules |

58-feature constraint matrix used in the DPR audit engine. Policies stored in `/policies/` as JSON (risk weights, severity definitions, cross-evidence rules, NCRI scoring).

### Frontend (Next.js + TypeScript)

| Component | What it does |
|---|---|
| `ProjectsRail` | Lists registered projects, status overview |
| `DPRValidator` | Upload and validate DPR documents, view extracted baseline |
| `SatelliteView` | Visual diff of satellite imagery, progress discrepancy estimate |
| `SiteGuard` | Upload site photos, view PPE detection and safety compliance |
| `TruthLens` | Upload images for ELA-based tampering analysis |
| `ContractorTrust` | Contractor NCRI scorecard and procurement risk view |
| `FraudAnalytics` | Cross-evidence risk aggregation and finding summaries |
| `TenderRegistry` | Browse live tender data |

---

## Tech Stack

**Backend**
- FastAPI, Python
- YOLOv8 (PPE detection)
- ChangeFormerV6 (satellite change detection)
- XGBoost (contractor risk scoring)
- Tesseract OCR (document intelligence)
- ChromaDB + RAG (DPR retrieval)
- Mistral 7B (reasoning and narrative generation)
- Error Level Analysis (image forensics)

**Frontend**
- Next.js 15, TypeScript, Tailwind CSS

**Infrastructure**
- Google Cloud Run (backend + frontend)
- Google Cloud Build (CI/CD)
- Docker

---

## Running Locally

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd infra-ai-app
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

---

## API Reference

Full interactive docs: `https://infra-ai-governance-mvp-5fvzoiirja-ew.a.run.app/docs`

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | System health and module status |
| `/projects` | GET | List registered projects |
| `/projects/{id}/dpr` | POST | Upload and process DPR |
| `/projects/{id}/satellite` | GET | Satellite assurance results |
| `/vision/analyze` | POST | Site safety photo analysis (YOLOv8) |
| `/forensics/ela` | POST | Image tampering analysis |
| `/ncri/{contractor_id}` | GET | Contractor risk score |
| `/projects/{id}/investigate` | POST | Trigger cross-evidence investigation |
| `/projects/{id}/report` | GET | Generate PDF assurance report |

---

## Team — Strawhats

- Sumit Das — [@Sumit-ai-dev](https://github.com/Sumit-ai-dev)
- Sakshi Kasat — [@SakshiKasat18](https://github.com/SakshiKasat18)
- Abhay Anand — [@abhayDoes](https://github.com/abhayDoes)
