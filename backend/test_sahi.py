import os
import cv2
from ultralytics import YOLO
from sahi_engine import run_zoomed_inference
from indian_heuristics import verify_hardhat

ARTIFACTS_DIR = "/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c"
DOWNLOAD_DIR = os.path.join(ARTIFACTS_DIR, "indian_raw_downloads_2")
img_path = os.path.join(DOWNLOAD_DIR, "raw_img_16.jpg")

print("Loading Hexmon Model...")
model = YOLO("/Users/sumitdas/Desktop/InfraAI/backend/models/Hexmon-yolov8m-ppe.pt")

print("Processing Image with CLAHE...")
img = cv2.imread(img_path)
if img is not None:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl,a,b))
    enhanced_img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
else:
    print("Failed to load image")
    exit()

print("Running SAHI Zoom-In Inference...")
final_boxes = run_zoomed_inference(model, enhanced_img, conf=0.15, iou=0.45)

output_img = enhanced_img.copy()

for box_data in final_boxes:
    label = box_data["label"]
    conf = box_data["conf"]
    x1, y1, x2, y2 = box_data["box"]
    
    # INDIAN CONTEXT FILTER
    if label == "Hardhat":
        h, w, _ = img.shape
        cx1, cy1 = max(0, x1), max(0, y1)
        cx2, cy2 = min(w, x2), min(h, y2)
        cropped = img[cy1:cy2, cx1:cx2]
        
        if not verify_hardhat(cropped):
            continue
            
    cv2.rectangle(output_img, (x1, y1), (x2, y2), (255, 0, 0), 2)
    cv2.putText(output_img, f"{label} {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

out_path = os.path.join(ARTIFACTS_DIR, "sahi_filter_test.jpg")
cv2.imwrite(out_path, output_img)
print(f"Saved result to {out_path}")
