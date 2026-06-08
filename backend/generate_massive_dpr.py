import os
import random
from fpdf import FPDF

out_path = os.path.expanduser("~/Desktop/demo/Massive_500Page_DPR.pdf")

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 10)
        self.cell(0, 10, 'DETAILED PROJECT REPORT - VOLUME II', 0, 1, 'C')

def create_massive_pdf():
    print("Generating massive 500-page DPR. This will take a few seconds...")
    pdf = PDF()
    
    # Generate 500 pages of filler text (simulating engineering specs, soil tests, etc.)
    target_page = 347
    
    for page_num in range(1, 501):
        pdf.add_page()
        pdf.set_font('Arial', '', 11)
        
        if page_num == target_page:
            # Inject the Master Schedule hidden deep inside the document!
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'SECTION 8.4: MASTER SCHEDULE & TARGET MILESTONES', 0, 1)
            pdf.set_font('Arial', '', 11)
            text = (
                "The following timeline dictates the physical progress milestones for the EPC contractor. "
                "Any deviations will trigger financial penalties.\n\n"
                "- Jan 2026: 10%\n"
                "- Feb 2026: 25%\n"
                "- Mar 2026: 40%\n"
                "- Jun 2026: 67%\n"
                "- Jul 2026: 75%\n"
                "- Dec 2026: 100%\n\n"
                "End of schedule."
            )
            pdf.multi_cell(0, 10, text)
        else:
            # Filler text to simulate a real massive document
            filler = "This page contains standard technical specifications, geotechnical survey results, " \
                     "and environmental impact assessments as mandated by the MoRT&H guidelines. " * 30
            pdf.multi_cell(0, 10, filler)
            
    pdf.output(out_path, 'F')
    print(f"Successfully generated 500-page DPR at: {out_path}")
    print(f"Master Schedule injected on Page {target_page}")

if __name__ == "__main__":
    create_massive_pdf()
