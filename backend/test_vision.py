from ultralytics import YOLO
import cv2
import numpy as np
import os

import sys

def test_vision(img_path=None):
    if not img_path:
        img_path = "backend/samples/construction_site.jpg"
        
    print(f"Testing SPECIALIZED Construction-PPE Model on: {img_path}")
    try:
        # Using weights trained on 10,000+ construction site images
        model = YOLO('backend/construction_safety.pt')
        
        if not os.path.exists(img_path):
            print(f"File not found: {img_path}")
            return False
            
        img = cv2.imread(img_path)
        results = model(img)
        
        print("\n--- SPECIALIZED DETECTION RESULTS (50% Threshold) ---")
        for r in results:
            for box in r.boxes:
                conf = float(box.conf)
                if conf >= 0.50:
                    label = model.names[int(box.cls)]
                    print(f"Object: {label} | Confidence: {conf:.2f}")
        print("-" * 25)
        return True
    except Exception as e:
        print(f"Vision Test Failed: {e}")
        return False

if __name__ == "__main__":
    target_img = sys.argv[1] if len(sys.argv) > 1 else "backend/samples/construction_site.jpg"
    target_model = sys.argv[2] if len(sys.argv) > 2 else "backend/construction_safety.pt"
    
    print(f"--- INFRAAI VISION TEST ---")
    print(f"Using Model: {target_model}")
    print(f"Using Image: {target_img}")
    
    try:
        model = YOLO(target_model)
        img = cv2.imread(target_img)
        results = model(img)
        
        # Professional Filter: Only show construction-relevant objects
        CONSTRUCTION_CLASSES = [
            'person', 'truck', 'car', 'machinery', 'Hardhat', 'Safety Vest', 
            'excavator', 'crane', 'concrete_mixer', 'worker', 'helmet'
        ]
        
        print("\n--- PROFESSIONAL CONSTRUCTION RESULTS ---")
        for r in results:
            # Save the visual result
            r.save(filename='backend/test_output.jpg')
            
            for box in r.boxes:
                conf = float(box.conf)
                label = model.names[int(box.cls)]
                
                # Check if it's a construction object OR a critical violation
                is_violation = label in ['NO-Safety Vest', 'NO-Hardhat', 'NO-Mask']
                
                if (label in CONSTRUCTION_CLASSES or label.lower() in CONSTRUCTION_CLASSES or is_violation):
                    if conf >= 0.40:
                        status = "!!! VIOLATION !!!" if is_violation else "OK"
                        print(f"[{status}] Object: {label} | Confidence: {conf:.2f}")
                else:
                    # Silently ignore noise
                    pass
        print("-" * 25)
    except Exception as e:
        print(f"Test Failed: {e}")
