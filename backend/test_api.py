import requests
import json
import time

def test_backend_api():
    url = "http://localhost:8001/analyze"
    
    # Wait for server to be fully ready
    time.sleep(2)
    
    mock_dpr_text = """
    DETAILED PROJECT REPORT (DPR)
    SECTION 7.1: LAND ACQUISITION STATUS
    Under the NHAI Act, 3G notifications have been published for 92% of the required land. However, physical 
    possession (3H) has only been completed for 65% of the right-of-way. There are massive ongoing farmer protests 
    in Village Y regarding compensation rates, leading to a temporary stay order by the local tribunal.
    
    SECTION 4.2: ENVIRONMENTAL IMPACT ASSESSMENT
    The proposed highway alignment passes through 4.5 kilometers of the densely forested buffer zone. 
    However, as of the current date, the Formal Forest Clearance (Stage II) from the Ministry of Environment, 
    Forest and Climate Change (MoEFCC) has not been secured.
    """

    payload = {
        "department": "National Highways Authority of India (NHAI)",
        "budget_cr": 450.50,
        "time_gap_months": 45, # 45 month gap + land protests + no forest clearance = 100% rejection
        "dpr_text": mock_dpr_text
    }
    
    print("[*] Sending 500-page Document to the Unified InfraAI Backend API...")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print("\n=========================================")
        print("🚀 API RESPONSE RECEIVED 🚀")
        print("=========================================\n")
        print(json.dumps(result, indent=4))
        
    except requests.exceptions.RequestException as e:
        print(f"[!] API Request Failed: {e}")

if __name__ == "__main__":
    test_backend_api()
