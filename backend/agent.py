"""
agent.py
========
Atlas Assurance — Notice Generation Engine

Two-tier notice generation strategy:
  Tier 1 (preferred) : Local Mistral-7B GGUF via llama-cpp, with category-specific
                       prompts for three violation classes.
  Tier 2 (fallback)  : Zero-latency CPWD regulatory template engine — generates
                       legally-accurate show-cause notices citing IS:7969, Clause 14A,
                       and IPC Section 471 without any model dependency.

Violation categories:
  "safety"    — PPE non-compliance detected by YOLO
  "dpr"       — DPR progress ghost/lag discrepancy vs satellite telemetry
  "forensics" — Image manipulation detected by ELA analysis
"""

import os
from datetime import date
from pathlib import Path
from typing import Optional

MODEL_PATH = str(Path(__file__).parent / "models" / "mistral-7b-instruct-v0.2.Q4_K_M.gguf")

# ---------------------------------------------------------------------------
# Category-specific LLM prompt templates
# ---------------------------------------------------------------------------

def _build_safety_prompt(contractor: str, site: str, context: str) -> str:
    return (
        f"<s>[INST] You are an AI Infrastructure Governance Officer for the Government of India, "
        f"acting under the Central Public Works Department (CPWD).\n\n"
        f"Generate a formal, authoritative legal show-cause notice for the PPE safety violation below.\n\n"
        f"CONTRACTOR: {contractor}\n"
        f"SITE/PROJECT: {site}\n"
        f"VIOLATION EVIDENCE: {context}\n\n"
        f"Requirements:\n"
        f"1. Professional, legalistic tone as per CPWD norms.\n"
        f"2. Cite IS:7969 (Safety Code for Construction Workers) and Clause 14A of the contract.\n"
        f"3. State that financial penalty will be deducted from the next DPR milestone payment.\n"
        f"4. Demand corrective action and PPE compliance certification within 24 hours.\n"
        f"5. Warn that repeated violations will trigger NCRI score deduction and tender debarment.\n\n"
        f"Format: Formal Letter Header → Body (3 paragraphs) → Signature (Superintending Engineer, CPWD). [/INST]"
    )


def _build_dpr_prompt(contractor: str, site: str, context: str) -> str:
    return (
        f"<s>[INST] You are an AI Infrastructure Governance Officer for the Government of India, "
        f"acting under the Central Public Works Department (CPWD).\n\n"
        f"Generate a formal, authoritative legal show-cause notice for DPR progress discrepancy detected "
        f"by satellite telemetry analysis.\n\n"
        f"CONTRACTOR: {contractor}\n"
        f"SITE/PROJECT: {site}\n"
        f"DISCREPANCY EVIDENCE: {context}\n\n"
        f"Requirements:\n"
        f"1. Professional, legalistic tone.\n"
        f"2. Reference the DPR filing discrepancy as a potential violation of Contract Clause 17 "
        f"   (Progress Reporting Obligations) and Section 12 of CPWD Works Manual.\n"
        f"3. State that all milestone disbursements are frozen pending physical site verification.\n"
        f"4. Demand submission of a rectified DPR with photographic evidence within 72 hours.\n"
        f"5. Warn that ghost billing (if confirmed) will be referred to the Central Vigilance Commission (CVC).\n\n"
        f"Format: Formal Letter Header → Body (3 paragraphs) → Signature (Chief Engineer, CPWD). [/INST]"
    )


def _build_forensics_prompt(contractor: str, site: str, context: str) -> str:
    return (
        f"<s>[INST] You are an AI Infrastructure Governance Officer for the Government of India, "
        f"acting under the Ministry of Road Transport and Highways.\n\n"
        f"Generate a formal, authoritative legal notice for digital evidence tampering detected in "
        f"site photographs submitted with the DPR filing.\n\n"
        f"CONTRACTOR: {contractor}\n"
        f"SITE/PROJECT: {site}\n"
        f"FORENSIC EVIDENCE: {context}\n\n"
        f"Requirements:\n"
        f"1. Gravely serious, legalistic tone.\n"
        f"2. Cite IPC Section 471 (using forged documents as genuine) and IT Act Section 66C.\n"
        f"3. State that the contractor's National Contractor Reliability Index (NCRI) score is "
        f"   immediately reduced by 50 points and bidding eligibility is suspended.\n"
        f"4. Demand surrender of original, unedited site photographs within 24 hours.\n"
        f"5. State that failure to comply will result in FIR filing and 3-year tender debarment.\n\n"
        f"Format: Formal Letter Header → Body (4 paragraphs) → Signature (Director General, CPWD). [/INST]"
    )


# ---------------------------------------------------------------------------
# Fallback CPWD template engine (zero-latency, no model dependency)
# ---------------------------------------------------------------------------

def _fallback_safety_notice(contractor: str, site: str, context: str) -> str:
    today = date.today().strftime("%d %B %Y")
    return f"""GOVERNMENT OF INDIA
CENTRAL PUBLIC WORKS DEPARTMENT
OFFICE OF THE SUPERINTENDING ENGINEER

DATE: {today}
REF: CPWD/SE/SAFETY/{today.replace(' ', '')}/NOTICE

TO:
The Authorized Representative,
{contractor}
Project Site: {site}

SUBJECT: SHOW-CAUSE NOTICE — NON-COMPLIANCE WITH PPE SAFETY REGULATIONS UNDER IS:7969

Sir/Madam,

This office has received a verified AI-assisted site audit report indicating critical Personal \
Protective Equipment (PPE) non-compliance at the above-referenced construction site. The violation \
evidence is as follows:

{context}

Under the Central Public Works Department Safety Code (IS:7969) and Clause 14A of your construction \
contract, all contractor personnel are mandatorily required to wear approved safety helmets, high-\
visibility safety vests, and respiratory masks at all times within the active construction zone. \
Failure to maintain this standard constitutes a material breach of contractual safety obligations.

You are hereby directed to: (a) immediately enforce 100% PPE compliance for all on-site personnel, \
(b) submit photographic evidence of corrective measures within 24 hours of receipt of this notice, \
and (c) provide a written compliance certification signed by your Site Safety Officer. A financial \
penalty as prescribed under Clause 14A shall be deducted from your next DPR milestone payment. \
Continued non-compliance will result in deductions to your National Contractor Reliability Index \
(NCRI) score and may render you ineligible for future CPWD tenders.

This notice is issued under the authority vested in this office and requires immediate compliance.

Yours faithfully,

(Superintending Engineer)
Central Public Works Department
Government of India"""


def _fallback_dpr_notice(contractor: str, site: str, context: str) -> str:
    today = date.today().strftime("%d %B %Y")
    return f"""GOVERNMENT OF INDIA
CENTRAL PUBLIC WORKS DEPARTMENT
OFFICE OF THE CHIEF ENGINEER

DATE: {today}
REF: CPWD/CE/DPR/{today.replace(' ', '')}/NOTICE

TO:
The Authorized Representative,
{contractor}
Project Site: {site}

SUBJECT: SHOW-CAUSE NOTICE — DPR PROGRESS DISCREPANCY DETECTED VIA SENTINEL-2 SATELLITE TELEMETRY

Sir/Madam,

This office has conducted a cross-verification of your latest Daily Progress Report (DPR) submission \
against independently obtained Sentinel-2 satellite imagery for the project site. The analysis has \
revealed a material discrepancy between the progress claimed in your DPR filing and the physical \
development verified by satellite telemetry:

{context}

Under Contract Clause 17 (Progress Reporting Obligations) and Section 12 of the CPWD Works Manual, \
contractors are legally bound to submit accurate and verifiable progress data in all DPR filings. A \
discrepancy of the magnitude detected constitutes a potential violation of these obligations and may \
indicate inflated billing — an offence referrable to the Central Vigilance Commission (CVC).

With immediate effect: (a) all milestone disbursements for this project are frozen pending physical \
site inspection by a CPWD-appointed audit team, (b) you are required to submit a rectified DPR \
accompanied by time-stamped, unedited photographic evidence of actual site conditions within 72 hours, \
and (c) a financial recovery equivalent to the overbilled amount may be initiated from funds already \
disbursed. Your National Contractor Reliability Index (NCRI) score has been adjusted accordingly.

This notice is issued under the authority vested in this office and requires immediate compliance.

Yours faithfully,

(Chief Engineer)
Central Public Works Department
Government of India"""


def _fallback_forensics_notice(contractor: str, site: str, context: str) -> str:
    today = date.today().strftime("%d %B %Y")
    return f"""GOVERNMENT OF INDIA
CENTRAL PUBLIC WORKS DEPARTMENT
OFFICE OF THE DIRECTOR GENERAL

DATE: {today}
REF: CPWD/DG/FORENSICS/{today.replace(' ', '')}/NOTICE

TO:
The Authorized Representative,
{contractor}
Project Site: {site}

SUBJECT: URGENT LEGAL NOTICE — DIGITAL EVIDENCE TAMPERING DETECTED IN DPR PHOTOGRAPH SUBMISSIONS

Sir/Madam,

It is brought to your immediate notice that forensic analysis conducted using Error Level Analysis \
(ELA) methodology has detected indicators of digital manipulation in site photographs submitted as \
supporting evidence with your recent DPR filing for the above-referenced project:

{context}

The submission of digitally altered photographs as authentic evidence constitutes a grave offence \
under IPC Section 471 (using forged documents as genuine) and Section 66C of the Information \
Technology Act, 2000. Such conduct undermines the integrity of the public infrastructure audit \
process and represents a serious breach of your contractual obligations under the CPWD Works Manual.

Effective immediately: (a) your National Contractor Reliability Index (NCRI) score has been reduced \
by 50 points, resulting in immediate suspension of bidding eligibility, (b) all project disbursements \
are frozen with no exceptions, (c) you are required to surrender original, unedited photographs of \
the referenced site activities to this office within 24 hours, and (d) your firm is placed under \
mandatory CVC surveillance for the duration of this project.

Failure to comply with the directives in this notice within the stipulated timeframe will result in \
the filing of a First Information Report (FIR) with the appropriate law enforcement authorities and \
a formal recommendation for 3-year debarment from all public infrastructure tenders in India.

This notice is issued under the authority vested in the Office of the Director General, CPWD, and \
demands your immediate and full compliance.

Yours faithfully,

(Director General)
Central Public Works Department
Government of India"""


# ---------------------------------------------------------------------------
# InfraAgent — primary interface
# ---------------------------------------------------------------------------

class InfraAgent:
    def __init__(self):
        self.llm = None
        skip_llm = os.environ.get("SKIP_LLM", "0").strip() == "1"
        if skip_llm:
            print("[agent] SKIP_LLM=1 set — skipping Mistral load. Template engine active.")
        elif os.path.exists(MODEL_PATH):
            try:
                from llama_cpp import Llama  # lazy import — only if model exists
                print(f"[agent] Loading Mistral-7B from {MODEL_PATH}...")
                self.llm = Llama(
                    model_path=MODEL_PATH,
                    n_gpu_layers=-1,
                    n_ctx=2048,
                    verbose=False,
                )
                print("[agent] Mistral-7B ready.")
            except Exception as e:
                print(f"[agent] Failed to load Mistral model: {e}. Falling back to template engine.")
        else:
            print(f"[agent] Mistral model not found at {MODEL_PATH}. Template engine active.")

    def is_ready(self) -> bool:
        return self.llm is not None

    def generate_notice(
        self,
        category: str = "safety",
        violation_type: str = "",
        contractor: Optional[str] = None,
        site_details: Optional[str] = None,
        context: str = "",
    ) -> dict:
        """
        Generate a formal show-cause notice.

        Args:
            category:       "safety" | "dpr" | "forensics"
            violation_type: Short label for the violation (legacy compat)
            contractor:     Contractor name
            site_details:   Project / site name
            context:        Evidence summary string

        Returns:
            {
                "available": bool,
                "source": "llm" | "template" | "none",
                "category": str,
                "text": str | None,
                "reason": str | None   (only when unavailable)
            }
        """
        contractor = contractor or "Contractor (name pending attribution)"
        site_details = site_details or "Project site (pending attribution)"
        category = category.lower().strip()

        # --- Tier 1: LLM-backed notice ---
        if self.llm:
            try:
                prompt_builders = {
                    "safety":    _build_safety_prompt,
                    "dpr":       _build_dpr_prompt,
                    "forensics": _build_forensics_prompt,
                }
                builder = prompt_builders.get(category, _build_safety_prompt)
                prompt = builder(contractor, site_details, context)

                output = self.llm(prompt, max_tokens=600, stop=["</s>"], echo=False)
                return {
                    "available": True,
                    "source":   "llm",
                    "category": category,
                    "text":     output["choices"][0]["text"].strip(),
                }
            except Exception as e:
                print(f"[agent] LLM inference failed: {e}. Falling back to template.")

        # --- Tier 2: Template fallback ---
        template_map = {
            "safety":    _fallback_safety_notice,
            "dpr":       _fallback_dpr_notice,
            "forensics": _fallback_forensics_notice,
        }
        template_fn = template_map.get(category, _fallback_safety_notice)
        notice_text = template_fn(contractor, site_details, context)

        return {
            "available": True,
            "source":   "template",
            "category": category,
            "text":     notice_text,
        }

    def extract_project_info(self, text: str) -> dict:
        """
        Uses the LLM to extract the project name and location from OCR text.
        """
        if not self.llm:
            return {"project_name": None, "location": None}

        prompt = (
            f"<s>[INST] You are an AI assistant. Extract the specific 'Project Name' "
            f"and 'Geographic Location' from the following text. Be very specific with the location.\n\n"
            f"TEXT:\n{text[:1500]}\n\n"
            f"Respond ONLY with a JSON object containing keys 'project_name' and 'location'. "
            f"Do not include any other text or markdown. [/INST]"
        )

        try:
            output = self.llm(prompt, max_tokens=150, stop=["</s>"], echo=False)
            response_text = output["choices"][0]["text"].strip()
            
            # Simple parsing of the JSON response
            import json
            import re
            
            # Try to find JSON block
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return {
                    "project_name": data.get("project_name"),
                    "location": data.get("location")
                }
        except Exception as e:
            print(f"[agent] Failed to extract project info: {e}")
            
        return {"project_name": None, "location": None}

agent = InfraAgent()
