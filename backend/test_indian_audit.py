import os
import cv2
from ultralytics import YOLO

# Directories
ARTIFACTS_DIR = "/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c"
DOWNLOAD_DIR = os.path.join(ARTIFACTS_DIR, "indian_raw_downloads")

print("Loading Hexmon Model...")
model = YOLO("/Users/sumitdas/Desktop/InfraAI/backend/models/Hexmon-yolov8m-ppe.pt")

report_lines = []
report_lines.append("# Indian Construction Site Mass Test Report")
report_lines.append("I extracted real, raw photos from the `real_construction_audit.pdf` (which contains hundreds of raw Indian construction site photos) and ran them through the new OpenCV CLAHE + Hexmon pipeline.\n")

# Get first 20 images from the extracted PDF images
all_images = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith("page_") and f.endswith(".jpg")]
all_images.sort(key=lambda x: int(x.split("_")[1].split(".")[0]))  # Sort numerically
test_images = all_images[20:40] # Skip the first 20 which might be cover pages or text

for idx, img_name in enumerate(test_images):
    img_path = os.path.join(DOWNLOAD_DIR, img_name)
    print(f"Testing image {idx+1}/{len(test_images)}: {img_name}")
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
            target_path = os.path.join(DOWNLOAD_DIR, f"clahe_{img_name}")
            cv2.imwrite(target_path, enhanced_img)
        else:
            target_path = img_path

        # Run inference using the new 0.15 threshold
        results = model(target_path, imgsz=640, conf=0.15, iou=0.45)
        
        out_name = f"indian_tested_{idx}.jpg"
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

with open(os.path.join(ARTIFACTS_DIR, "indian_test_report.md"), "w") as f:
    f.write("\n".join(report_lines))
    
print("Batch testing complete!")
