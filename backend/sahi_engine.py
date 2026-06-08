import cv2
import math

def run_zoomed_inference(model, img, conf=0.15, iou=0.45):
    """
    Runs YOLO inference on the full image and 4 zoomed-in quadrants.
    Mathematically remaps coordinates and merges results to detect tiny objects.
    Returns a unified list of detected objects.
    """
    if img is None:
        return []
        
    h, w, _ = img.shape
    mid_h, mid_w = h // 2, w // 2
    
    # Define the 4 quadrants with a 50px overlap to catch objects on the border
    overlap = 50
    quadrants = [
        (0, min(h, mid_h + overlap), 0, min(w, mid_w + overlap)), # Top-Left
        (0, min(h, mid_h + overlap), max(0, mid_w - overlap), w), # Top-Right
        (max(0, mid_h - overlap), h, 0, min(w, mid_w + overlap)), # Bottom-Left
        (max(0, mid_h - overlap), h, max(0, mid_w - overlap), w)  # Bottom-Right
    ]
    
    final_boxes = []
    
    # 1. Run Full Image (Catches big objects: Person, Hardhat, Vest, Ladder)
    results_full = model(img, imgsz=640, conf=conf, iou=iou, verbose=False)
    for r in results_full:
        for box in r.boxes:
            label = model.names[int(box.cls)]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            final_boxes.append({
                "label": label,
                "conf": float(box.conf),
                "box": (x1, y1, x2, y2)
            })
            
    # 2. Run Quadrants (Catches TINY objects only)
    # We only care about objects that are usually < 10 pixels wide in wide shots
    tiny_classes = ["Gloves", "NO-Gloves", "Goggles", "NO-Goggles", "Mask", "NO-Mask"]
    
    for q_y1, q_y2, q_x1, q_x2 in quadrants:
        crop = img[q_y1:q_y2, q_x1:q_x2]
        if crop.size == 0: continue
            
        # We run the crop at 640x640, which artificially zooms it in 2x!
        results_q = model(crop, imgsz=640, conf=conf, iou=iou, verbose=False)
        for r in results_q:
            for box in r.boxes:
                label = model.names[int(box.cls)]
                if label in tiny_classes:
                    # Remap coordinates to absolute full-image coordinates
                    bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                    abs_x1 = bx1 + q_x1
                    abs_y1 = by1 + q_y1
                    abs_x2 = bx2 + q_x1
                    abs_y2 = by2 + q_y1
                    
                    # Distance-based NMS to prevent duplicate overlapping boxes
                    is_duplicate = False
                    for existing in final_boxes:
                        if existing["label"] == label:
                            ex1, ey1, ex2, ey2 = existing["box"]
                            cx1, cy1 = (abs_x1 + abs_x2) / 2, (abs_y1 + abs_y2) / 2
                            cx2, cy2 = (ex1 + ex2) / 2, (ey1 + ey2) / 2
                            dist = math.hypot(cx1 - cx2, cy1 - cy2)
                            if dist < 40: # If it's within 40 pixels of another detection, it's a duplicate
                                is_duplicate = True
                                break
                    
                    if not is_duplicate:
                        final_boxes.append({
                            "label": label,
                            "conf": float(box.conf),
                            "box": (abs_x1, abs_y1, abs_x2, abs_y2)
                        })
                        
    return final_boxes
