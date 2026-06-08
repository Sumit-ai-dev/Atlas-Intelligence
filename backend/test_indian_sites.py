import os
import requests
from duckduckgo_search import DDGS
from ultralytics import YOLO
import cv2

# Directories
ARTIFACTS_DIR = "/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c"
DOWNLOAD_DIR = os.path.join(ARTIFACTS_DIR, "indian_raw_downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

print("Fetching 30 image URLs from DuckDuckGo...")
results = DDGS().images("indian construction workers laborers site raw photo", max_results=30)

downloaded_images = []
for idx, r in enumerate(results):
    if len(downloaded_images) >= 20:
        break
    url = r.get("image")
    if not url: continue
    
    try:
        ext = url.split(".")[-1].split("?")[0]
        if ext.lower() not in ["jpg", "jpeg", "png"]:
            ext = "jpg"
            
        img_path = os.path.join(DOWNLOAD_DIR, f"raw_img_{idx}.{ext}")
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(response.content)
            downloaded_images.append(img_path)
            print(f"Downloaded: {img_path}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

print(f"\nSuccessfully downloaded {len(downloaded_images)} images. Loading Hexmon Model...")
model = YOLO("/Users/sumitdas/Desktop/InfraAI/backend/models/Hexmon-yolov8m-ppe.pt")

report_lines = []

for idx, img_path in enumerate(downloaded_images):
    print(f"Testing image {idx+1}/{len(downloaded_images)}...")
    try:
        # APPLY OPENCV CLAHE EXACTLY LIKE MAIN.PY
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

        # Run inference using the new 0.15 threshold
        results = model(target_path, imgsz=640, conf=0.15, iou=0.45)
        
        out_name = f"indian_tested_batch_{idx}.jpg"
        out_path = os.path.join(ARTIFACTS_DIR, out_name)
        
        for r in results:
            r.save(filename=out_path)
            
            objects = []
            person_count = 0
            hardhat_count = 0
            vest_count = 0
            
            for box in r.boxes:
                conf = float(box.conf)
                label = model.names[int(box.cls)]
                objects.append(f"{label}({conf:.2f})")
                if label == "Person": person_count += 1
                if label == "Hardhat": hardhat_count += 1
                if label == "Safety Vest": vest_count += 1
                
            ratio_alerts = []
            if person_count > hardhat_count: ratio_alerts.append("MISSING-Hardhat (Ratio Alert)")
            if person_count > vest_count: ratio_alerts.append("MISSING-Safety Vest (Ratio Alert)")
            
            report_lines.append(f"## Indian Site Image {idx+1}")
            report_lines.append(f"![Result {idx+1}](/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c/{out_name})")
            report_lines.append(f"*   **Raw Detections:** {', '.join(objects) if objects else 'None'}")
            report_lines.append(f"*   **Mathematical Ratios:** {person_count} People | {hardhat_count} Hardhats | {vest_count} Vests")
            if ratio_alerts:
                report_lines.append(f"*   **🚨 VIOLATIONS:** {', '.join(ratio_alerts)}")
            else:
                report_lines.append("*   **✅ Status:** Compliant")
            report_lines.append("---")
            
    except Exception as e:
        print(f"Failed inference on {img_path}: {e}")

# Save the markdown report fragment
with open(os.path.join(ARTIFACTS_DIR, "indian_test_report.md"), "w") as f:
    f.write("\n".join(report_lines))
    
print("Batch testing complete!")
