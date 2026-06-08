import re
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

PROGRESS_KEYWORDS = [
    "progress", "completed", "completion", "complete", "achieved",
    "physical progress", "financial progress", "work done", "achievement",
    "cumulative", "milestone",
]
PCT_PATTERN = re.compile(r"(\d{1,3}(?:\.\d{1,2})?)\s*%")


def _ocr_pdf(pdf_path, max_pages=10, dpi=200):
    pages = convert_from_path(str(pdf_path), first_page=1, last_page=max_pages, dpi=dpi)
    full_text = []
    for img in pages:
        full_text.append(pytesseract.image_to_string(img))
    return "\n".join(full_text)


def _score_candidate(line, pct_value):
    line_l = line.lower()
    score = 0.0
    for kw in PROGRESS_KEYWORDS:
        if kw in line_l:
            score += 1.0
    # Penalize obviously-wrong magnitudes
    if pct_value > 100 or pct_value < 0:
        return -1.0
    # Penalize lines that look like interest rates or tax rates
    if any(t in line_l for t in ["gst", "tax", "interest", "discount", "rebate", "tds"]):
        score -= 2.0
    # Reward "physical progress" / "cumulative" specifically
    if "physical progress" in line_l or "cumulative" in line_l:
        score += 2.0
    return score


def extract_reported_progress(pdf_path, target_date_str=None):
    pdf_path = Path(pdf_path)
    text = _ocr_pdf(pdf_path)
    
    # 1. Timeline Extractor Mode (DPR Master Schedule)
    if target_date_str:
        target_lower = target_date_str.lower()
        for line in text.splitlines():
            if target_lower in line.lower():
                # Look for a percentage on this specific timeline line
                m = PCT_PATTERN.search(line)
                if m:
                    try:
                        val = float(m.group(1))
                        from agent import agent
                        project_info = agent.extract_project_info(text)
                        return {
                            "extracted": True,
                            "reported_progress_pct": val,
                            "confidence_score": 10.0,  # Exact date match is high confidence
                            "matched_line": line.strip(),
                            "all_candidates": [{"value": val, "score": 10.0, "line": line.strip()}],
                            "text_excerpt": text[:800],
                            "project_name": project_info.get("project_name"),
                            "location": project_info.get("location")
                        }
                    except ValueError:
                        pass
                        
    # 2. Fallback Mode (Old logic: find highest scored progress keyword)
    candidates = []
    for line in text.splitlines():
        for m in PCT_PATTERN.finditer(line):
            try:
                val = float(m.group(1))
            except ValueError:
                continue
            score = _score_candidate(line, val)
            if score <= 0:
                continue
            candidates.append({"value": val, "score": score, "line": line.strip()})
            
    if not candidates:
        from agent import agent
        project_info = agent.extract_project_info(text)
        return {
            "extracted": False,
            "reason": f"Target date '{target_date_str}' not found, and no valid fallback progress found",
            "text_excerpt": text[:800],
            "candidates": [],
            "project_name": project_info.get("project_name"),
            "location": project_info.get("location")
        }
        
    candidates.sort(key=lambda c: (-c["score"], -c["value"]))
    best = candidates[0]
    
    # Extract project info using LLM
    from agent import agent
    project_info = agent.extract_project_info(text)
    
    return {
        "extracted": True,
        "reported_progress_pct": best["value"],
        "confidence_score": best["score"],
        "matched_line": best["line"],
        "all_candidates": candidates[:10],
        "text_excerpt": text[:800],
        "project_name": project_info.get("project_name"),
        "location": project_info.get("location")
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python dpr_extractor.py <pdf_path>")
        sys.exit(1)
    result = extract_reported_progress(sys.argv[1])
    import json
    print(json.dumps(result, indent=2))
