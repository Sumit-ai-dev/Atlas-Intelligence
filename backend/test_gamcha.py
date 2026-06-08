import os
import cv2
from ultralytics import YOLO
from indian_heuristics import verify_hardhat

ARTIFACTS_DIR = "/Users/sumitdas/.gemini/antigravity-ide/brain/453ce593-1d2b-4564-84ff-394c7f839b8c"
DOWNLOAD_DIR = os.path.join(ARTIFACTS_DIR, "indian_raw_downloads_2")
img_path = os.path.join(DOWNLOAD_DIR, "raw_img_13.jpg") # Result 14

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
    print("Failed to load image!")
    exit()

print("Running YOLO inference...")
results = model(enhanced_img, imgsz=640, conf=0.15, iou=0.45)

# We will draw our own bounding boxes to show the filter in action
output_img = img.copy()

for r in results:
    for box in r.boxes:
        conf = float(box.conf)
        label = model.names[int(box.cls)]
        
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        
        if label == "Hardhat":
            # Crop the bounding box from the ORIGINAL un-CLAHE'd image for accurate color check
            cropped = img[y1:y2, x1:x2]
            
            is_real = verify_hardhat(cropped)
            if is_real:
                # Green box for verified hardhat
                cv2.rectangle(output_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(output_img, f"Real Hardhat {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            else:
                # Red box for Fake Hardhat (Gamcha)
                cv2.rectangle(output_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(output_img, f"Fake Hardhat (Gamcha Rejected) {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        else:
            # Draw normal boxes
            cv2.rectangle(output_img, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(output_img, f"{label} {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)

out_path = os.path.join(ARTIFACTS_DIR, "gamcha_filter_test.jpg")
cv2.imwrite(out_path, output_img)
print(f"Saved result to {out_path}")
