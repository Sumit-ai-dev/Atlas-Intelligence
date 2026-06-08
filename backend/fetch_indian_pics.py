import os
import requests
from duckduckgo_search import DDGS
from ultralytics import YOLO
import cv2
import time

ARTIFACTS_DIR = "/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c"
DOWNLOAD_DIR = os.path.join(ARTIFACTS_DIR, "indian_raw_downloads_2")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

print("Fetching 20 image URLs from DuckDuckGo...")
results = []
for attempt in range(3):
    try:
        results = DDGS().images("indian construction site workers laborers photo", max_results=30)
        break
    except Exception as e:
        print(f"Ratelimited, sleeping 5s... {e}")
        time.sleep(5)
        
downloaded_images = []
for idx, r in enumerate(results):
    if len(downloaded_images) >= 20: break
    url = r.get("image")
    if not url: continue
    
    try:
        ext = "jpg"
        img_path = os.path.join(DOWNLOAD_DIR, f"raw_img_{idx}.{ext}")
        response = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            with open(img_path, "wb") as f: f.write(response.content)
            downloaded_images.append(img_path)
            print(f"Downloaded: {img_path}")
    except: pass

print("Loading model...")
model = YOLO("/Users/sumitdas/Desktop/InfraAI/backend/models/Hexmon-yolov8m-ppe.pt")

report_lines = ["# Indian Construction Site Mass Test Report"]
for idx, img_path in enumerate(downloaded_images):
    print(f"Testing {idx+1}/{len(downloaded_images)}")
    try:
        img = cv2.imread(img_path)
        if img is not None:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl,a,b))
            enhanced_img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            target_path = os.path.join(DOWNLOAD_DIR, f"clahe_{os.path.basename(img_path)}")
            cv2.imwrite(target_path, enhanced_img)
        else:
            target_path = img_path

        results = model(target_path, imgsz=640, conf=0.15, iou=0.45, verbose=False)
        out_name = f"indian_tested_batch_{idx}.jpg"
        out_path = os.path.join(ARTIFACTS_DIR, out_name)
        
        for r in results:
            r.save(filename=out_path)
            objects = []
            p, h, v = 0, 0, 0
            for box in r.boxes:
                label = model.names[int(box.cls)]
                objects.append(f"{label}({float(box.conf):.2f})")
                if label == "Person": p += 1
                if label == "Hardhat": h += 1
                if label == "Safety Vest": v += 1
                
            ratio_alerts = []
            if p > h: ratio_alerts.append("MISSING-Hardhat (Ratio Alert)")
            if p > v: ratio_alerts.append("MISSING-Safety Vest (Ratio Alert)")
            
            report_lines.append(f"## Image {idx+1}")
            report_lines.append(f"![Result {idx+1}](/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c/{out_name})")
            report_lines.append(f"*   **Raw Detections:** {', '.join(objects) if objects else 'None'}")
            report_lines.append(f"*   **Mathematical Ratios:** {p} People | {h} Hardhats | {v} Vests")
            if ratio_alerts: report_lines.append(f"*   **🚨 VIOLATIONS:** {', '.join(ratio_alerts)}")
            else: report_lines.append("*   **✅ Status:** Compliant")
            report_lines.append("---")
    except: pass

with open(os.path.join(ARTIFACTS_DIR, "indian_test_report.md"), "w") as f:
    f.write("\n".join(report_lines))
print("Done!")
