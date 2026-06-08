import requests
import json
import time
from pypdf import PdfReader
import sys

def test_real_dpr(pdf_path):
    print(f"[*] Opening Real DPR: {pdf_path}")
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        print(f"[*] Found {total_pages} pages in PDF.")
        
        # Extract text (limit to first 300 pages to avoid local memory overload for this test)
        pages_to_read = min(total_pages, 300)
        extracted_text = ""
        
        print(f"[*] Extracting text from {pages_to_read} pages...")
        for i in range(pages_to_read):
            page_text = reader.pages[i].extract_text()
            if page_text:
                extracted_text += page_text + "\n"
                
        print(f"[*] Extraction complete! Total characters: {len(extracted_text)}")
        
        # Dynamically extract Budget & Time Gap instead of hardcoding
        import re
        budget_match = re.search(r'(?:Rs|INR|₹)\.?\s*([\d,\.]+)\s*(?:Crore|Cr)', extracted_text, re.IGNORECASE)
        # Only look for explicit delays, otherwise assume a standard 12 month gap
        time_match = re.search(r'(?:delay|gap).*?([\d]+)\s*(?:months|Months)', extracted_text, re.IGNORECASE)
        
        try:
            extracted_budget = float(budget_match.group(1).replace(',', '')) if budget_match else 500.0
        except ValueError:
            extracted_budget = 500.0
            
        extracted_time = int(time_match.group(1)) if time_match else 12
        
        print(f"[*] Dynamic Extractor -> Budget: ₹{extracted_budget} Cr | Time Gap: {extracted_time} Months")
        
        url = "http://localhost:8001/analyze"
        
        payload = {
            "department": "Urban Transport / Metro Rail",
            "budget_cr": extracted_budget,
            "time_gap_months": extracted_time, 
            "dpr_text": extracted_text
        }
        
        print("[*] Sending massive document to the AI Backend API...")
        print("[*] (This may take 10-20 seconds for the Vector Engine to parse)")
        
        start_time = time.time()
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        end_time = time.time()
        
        print("\n=========================================")
        print(f"🚀 AI ANALYSIS COMPLETE ({round(end_time - start_time, 2)} seconds) 🚀")
        print("=========================================\n")
        print(json.dumps(result, indent=4))
        
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_real_dpr(sys.argv[1])
    else:
        print("Please provide a path to a PDF file.")
