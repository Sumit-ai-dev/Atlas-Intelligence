import cv2
import numpy as np

def verify_hardhat(cropped_img):
    """
    Returns True if the object is mathematically likely to be an industrial hardhat.
    Returns False if it is likely a Gamcha/cloth/cement bowl based on shape and color.
    """
    if cropped_img is None or cropped_img.size == 0:
        return True # Default to True if crop fails
        
    h, w, _ = cropped_img.shape
    if h == 0 or w == 0:
        return True
        
    # 1. Aspect Ratio Check
    # A standard hardhat sitting on a head is generally slightly wider than it is tall, or roughly square.
    # If it's extremely tall (e.g. height is 1.5x width), it's likely a wrapped cloth stacked high.
    # If it's extremely wide (e.g. width is 2.5x height), it might be a cement bowl.
    aspect_ratio = w / float(h)
    if aspect_ratio < 0.6 or aspect_ratio > 2.5:
        return False
        
    # 2. Industrial Color Check (HSV Masking)
    # Industrial hardhats in India are predominantly Yellow, White, or Green.
    # Gamchas are often red, brown, plaid, or dirty grey.
    hsv = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2HSV)
    
    # Yellow Mask
    lower_yellow = np.array([20, 50, 50])
    upper_yellow = np.array([40, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    # White Mask (Low saturation, high value)
    lower_white = np.array([0, 0, 180])
    upper_white = np.array([180, 50, 255])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    
    # Green Mask
    lower_green = np.array([40, 40, 40])
    upper_green = np.array([80, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    
    # Combine Masks
    combined_mask = cv2.bitwise_or(mask_yellow, mask_white)
    combined_mask = cv2.bitwise_or(combined_mask, mask_green)
    
    # Calculate percentage of industrial colors in the crop
    color_ratio = cv2.countNonZero(combined_mask) / (h * w)
    
    # 3. Decision Logic
    # If less than 5% of the bounding box matches industrial colors, it's highly likely to be a Gamcha or dirt/cement.
    # We aggressively reject it.
    if color_ratio < 0.05:
        return False
        
    return True
