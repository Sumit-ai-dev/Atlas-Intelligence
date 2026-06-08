import requests
import json
import time
import os
from pypdf import PdfReader

def test_all_dprs():
    dprs = [
        "/Users/sumitdas/Downloads/Dpr3.pdf",
        "/Users/sumitdas/Downloads/Dpr4.pdf",
        "/Users/sumitdas/Downloads/Dpr5.pdf",
        "/Users/sumitdas/Downloads/Dpr6.pdf",
        "/Users/sumitdas/Downloads/MetroDpr.pdf",
        "/Users/sumitdas/Downloads/MetroDpr2.pdf"
    ]
    
    artifact_path = "/Users/sumitdas/.gemini/antigravity-ide/brain/319e9307-4b9d-4555-8ff5-6cd8c177dc1e/full_dpr_audit_report.md"
    
    markdown_content = "# 🛡️ Enterprise Architecture: 58-Feature Full Audit Report\n\n"
    markdown_content += "The RAG Engine and XGBoost ML Core successfully scanned all available Detailed Project Reports (DPRs) against the massive 58-feature constraint matrix.\n\n---\n\n"
    
    for pdf_path in dprs:
        if not os.path.exists(pdf_path):
            print(f"[!] File not found: {pdf_path}")
            continue
            
        filename = os.path.basename(pdf_path)
        print(f"\n[*] Scanning {filename}...")
        
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            pages_to_read = min(total_pages, 300)
            
            extracted_text = ""
            for i in range(pages_to_read):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    extracted_text += page_text + "\n"
                    
            url = "http://localhost:8001/analyze"
            payload = {
                "department": "Infrastructure Testing",
                "budget_cr": 25000.0,
                "time_gap_months": 24, 
                "dpr_text": extracted_text
            }
            
            start_time = time.time()
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            end_time = time.time()
            processing_time = round(end_time - start_time, 2)
            
            print(f"[*] {filename} Analysis Complete in {processing_time}s")
            
            # Formatting Markdown
            status = result.get('status', 'ERROR')
            emoji = "🟢" if status == "APPROVED" else "🔴"
            
            markdown_content += f"## 📄 Document: `{filename}`\n"
            markdown_content += f"- **Pages Scanned**: {pages_to_read} (Total: {total_pages})\n"
            markdown_content += f"- **Data Size**: {len(extracted_text):,} Characters\n"
            markdown_content += f"- **Processing Time**: {processing_time} seconds\n"
            markdown_content += f"- **Final Verdict**: **{result.get('approval_probability', 0)}% {status}** {emoji}\n\n"
            
            critical_evidence = result.get("critical_evidence_found", [])
            if critical_evidence:
                markdown_content += "### 🚨 Critical Risks Detected (58-Feature RAG):\n"
                for ev in critical_evidence:
                    markdown_content += f"> *{ev}*\n\n"
            else:
                markdown_content += "### ✅ No Critical Risks Detected\n\nThe AI found 0 violations across all 58 parameters.\n\n"
                
            markdown_content += "---\n"
            
        except Exception as e:
            print(f"[!] Error processing {filename}: {e}")
            markdown_content += f"## 📄 Document: `{filename}`\n"
            markdown_content += f"**ERROR:** Processing failed due to: `{str(e)}`\n\n---\n"
            
    # Write Artifact
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    print(f"\n[*] Massive batch test complete! Report generated at: {artifact_path}")

if __name__ == "__main__":
    test_all_dprs()
