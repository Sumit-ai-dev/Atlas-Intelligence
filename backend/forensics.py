from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageEnhance

TMP_ELA_PATH = str(Path(__file__).parent / "temp_ela.jpg")


def detect_ela(image_path, quality=90):
    orig = Image.open(image_path).convert("RGB")
    orig.save(TMP_ELA_PATH, "JPEG", quality=quality)
    tmp = Image.open(TMP_ELA_PATH)
    ela = ImageChops.difference(orig, tmp)
    extrema = ela.getextrema()
    max_diff = max([ex[1] for ex in extrema]) or 1
    scale_factor = 255.0 / max_diff
    ela = ImageEnhance.Brightness(ela).enhance(scale_factor)
    return ela


def analyze_image_forensics(image_path):
    ela_img = detect_ela(image_path)
    arr = np.array(ela_img.convert("L"), dtype=np.float32)
    mean_err = float(arr.mean())
    std_err = float(arr.std())
    max_err = float(arr.max())
    p95 = float(np.percentile(arr, 95))
    # Heuristic: tampered regions create non-uniform error patches.
    # Score combines spatial inconsistency (std) with localized brightness (p95).
    score = float(min(1.0, (std_err / 60.0) * 0.6 + (p95 / 255.0) * 0.4))
    return {
        "ela_image": ela_img,
        "stats": {
            "mean_error": round(mean_err, 2),
            "std_error": round(std_err, 2),
            "max_error": round(max_err, 2),
            "p95_error": round(p95, 2),
        },
        "tampering_score": round(score, 3),
        "tampering_detected": score > 0.45,
    }
