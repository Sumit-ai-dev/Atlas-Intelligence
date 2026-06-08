import os
from fpdf import FPDF

# Ensure demo directory exists
demo_dir = os.path.expanduser("~/Desktop/demo")
os.makedirs(demo_dir, exist_ok=True)

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'DETAILED PROJECT REPORT (DPR) - MASTER SCHEDULE', 0, 1, 'C')
        self.ln(5)

def create_dme_pdf():
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Authority: National Highways Authority of India (NHAI)', 0, 1)
    pdf.cell(0, 10, 'Project: Delhi-Mumbai Expressway (Sohna Segment)', 0, 1)
    pdf.cell(0, 10, 'Contractor: L&T / NHAI', 0, 1)
    pdf.cell(0, 10, 'Project Code: PRJ-DME', 0, 1)
    pdf.ln(10)
    
    pdf.set_font('Arial', '', 11)
    text = (
        "This document is the official Detailed Project Report (DPR) Master Schedule for the "
        "Sohna Segment of the Delhi-Mumbai Expressway project. This schedule dictates the "
        "required target milestones for the contractor. Failure to meet these physical progress "
        "milestones will result in a reduction of the NCRI rating.\n\n"
        "Master Schedule & Target Milestones:\n"
        "- Jan 2026: 10%\n"
        "- Feb 2026: 25%\n"
        "- Mar 2026: 40%\n"
        "- Apr 2026: 52%\n"
        "- May 2026: 60%\n"
        "- Jun 2026: 67%\n"
        "- Jul 2026: 75%\n"
        "- Aug 2026: 85%\n"
        "- Dec 2026: 100%\n\n"
        "Contractor disbursements are strictly tied to these cumulative physical progress milestones."
    )
    pdf.multi_cell(0, 10, text)
    
    pdf.ln(20)
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(0, 10, 'Generated via NHAI Project Management Information System (PMIS)', 0, 1, 'C')
    
    out_path = os.path.join(demo_dir, "PRJ-DME_dpr.pdf")
    pdf.output(out_path, 'F')
    print(f"Created: {out_path}")

def create_nma_pdf():
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Authority: CIDCO / Adani Airport Holdings', 0, 1)
    pdf.cell(0, 10, 'Project: Navi Mumbai International Airport', 0, 1)
    pdf.cell(0, 10, 'Contractor: Hindustan Infra Construction Ltd.', 0, 1)
    pdf.cell(0, 10, 'Project Code: PRJ-NMA', 0, 1)
    pdf.ln(10)
    
    pdf.set_font('Arial', '', 11)
    text = (
        "This document is the official Detailed Project Report (DPR) Master Schedule for the "
        "Navi Mumbai International Airport Phase III. This schedule tracks the cumulative "
        "physical completion targets for runway grading and terminal foundation works.\n\n"
        "Master Schedule & Target Milestones:\n"
        "- Jan 2026: 5%\n"
        "- Feb 2026: 12%\n"
        "- Mar 2026: 20%\n"
        "- Apr 2026: 30%\n"
        "- May 2026: 38%\n"
        "- Jun 2026: 42%\n"
        "- Jul 2026: 50%\n"
        "- Nov 2026: 80%\n"
        "- Dec 2026: 100%\n\n"
        "The current expected progress target must be met. Minor safety observations regarding "
        "PPE compliance do not affect these targets but impact the NCRI score separately."
    )
    pdf.multi_cell(0, 10, text)
    
    pdf.ln(20)
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(0, 10, 'Approved by CIDCO Master Engineering Board', 0, 1, 'C')
    
    out_path = os.path.join(demo_dir, "PRJ-NMA_dpr.pdf")
    pdf.output(out_path, 'F')
    print(f"Created: {out_path}")

create_dme_pdf()
create_nma_pdf()
