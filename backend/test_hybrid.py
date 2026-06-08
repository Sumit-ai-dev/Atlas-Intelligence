import sys
from geocoder import parse_google_maps_url
from satellite import analyze_project
import main

def test():
    url = "https://maps.google.com/?q=28.25,77.06"
    bbox = parse_google_maps_url(url)
    print(f"BBOX from URL: {bbox}")
    
    new_id = "PRJ-TEST123"
    main.PROJECTS[new_id] = {
        "id": new_id,
        "name": "Sohna Test Location",
        "contractor": "Test Contractor",
        "location": [28.25, 77.06],
        "bbox": bbox,
        "baseline_date": "2020-01-01",
        "started": "2020-01-01",
        "type": "Auto-Generated"
    }
    
    print("Running analyze_project...")
    res = analyze_project(new_id)
    print("Done! Result:")
    print(res)

if __name__ == "__main__":
    test()
