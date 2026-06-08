import os
import cv2
from ultralytics import YOLO
from sahi_engine import run_zoomed_inference
from indian_heuristics import verify_hardhat

ARTIFACTS_DIR = "/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c"
DOWNLOAD_DIR = os.path.join(ARTIFACTS_DIR, "indian_raw_downloads_2")

print("Loading Hexmon Model...")
model = YOLO("/Users/sumitdas/Desktop/InfraAI/backend/models/Hexmon-yolov8m-ppe.pt")

report_content = "# Final Pipeline Stress Test (15 Indian Images)\n\n"
report_content += "This batch test runs the full, upgraded pipeline on 15 unedited Indian construction photos:\n"
report_content += "1. **CLAHE:** Boosts micro-contrast to see through harsh sunlight and shadows.\n"
report_content += "2. **SAHI Zoom-In:** Slices the image into 4 quadrants to detect tiny objects (Masks, Gloves).\n"
report_content += "3. **Gamcha Filter:** Uses OpenCV math to aggressively reject loose clothing mistaken for hardhats.\n\n"

count = 0
for i in range(40): # Max 40 files in directory
    if count >= 15:
        break
        
    img_name = f"raw_img_{i}.jpg"
    img_path = os.path.join(DOWNLOAD_DIR, img_name)
    
    if not os.path.exists(img_path):
        continue
        
    print(f"Processing {img_name} ({count+1}/15)...")
    img = cv2.imread(img_path)
    if img is None:
        continue
        
    # 1. CLAHE
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl,a,b))
    enhanced_img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    # 2. SAHI Inference
    final_boxes = run_zoomed_inference(model, enhanced_img, conf=0.15, iou=0.45)
    
    output_img = enhanced_img.copy()
    objects_list = []
    
    for box_data in final_boxes:
        label = box_data["label"]
        conf = box_data["conf"]
        x1, y1, x2, y2 = box_data["box"]
        
        # 3. Gamcha Filter
        if label == "Hardhat":
            h, w, _ = img.shape
            cx1, cy1 = max(0, x1), max(0, y1)
            cx2, cy2 = min(w, x2), min(h, y2)
            cropped = img[cy1:cy2, cx1:cx2]
            
            if not verify_hardhat(cropped):
                continue # Rejected Gamcha!
                
        # Draw bounding boxes based on type
        tiny_classes = ["Gloves", "NO-Gloves", "Goggles", "NO-Goggles", "Mask", "NO-Mask"]
        if label in tiny_classes:
            color = (0, 255, 255) # Yellow for SAHI tiny objects
        elif label == "Hardhat" or label == "Safety Vest":
            color = (0, 255, 0) # Green for verified compliant gear
        elif "NO-" in label or label == "Fall-Detected":
            color = (0, 0, 255) # Red for Violations
        else:
            color = (255, 0, 0) # Blue for normal (Person, Ladder, etc)
            
        cv2.rectangle(output_img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(output_img, f"{label} {conf:.2f}", (x1, max(y1 - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        objects_list.append(f"{label}({conf:.2f})")
        
    # Save Image
    out_filename = f"final_test_{count}.jpg"
    out_path = os.path.join(ARTIFACTS_DIR, out_filename)
    cv2.imwrite(out_path, output_img)
    
    # Append to report
    report_content += f"## Result {count + 1}\n"
    report_content += f"![Image {count+1}](/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c/{out_filename})\n"
    report_content += f"*   **Raw Detections:** {', '.join(objects_list)}\n\n"
    
    count += 1

report_path = os.path.join(ARTIFACTS_DIR, "final_indian_report.md")
with open(report_path, "w") as f:
    f.write(report_content)
    
print("Batch complete!")
