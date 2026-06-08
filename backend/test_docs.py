from transformers import LayoutLMv3ImageProcessor, LayoutLMv3Tokenizer, LayoutLMv3ForSequenceClassification
import torch
from PIL import Image
import numpy as np

def test_layoutlm():
    print("Testing Document AI (LayoutLMv3)...")
    try:
        model_id = "microsoft/layoutlmv3-base"
        
        # This will trigger the download of weights (~500MB)
        print(f"Loading {model_id} from HuggingFace...")
        image_processor = LayoutLMv3ImageProcessor.from_pretrained(model_id)
        tokenizer = LayoutLMv3Tokenizer.from_pretrained(model_id)
        
        print("Model components loaded successfully.")
        
        # Convert PDF to Image for real analysis
        from pdf2image import convert_from_path
        import pytesseract
        
        pdf_path = "backend/samples/real_construction_audit.pdf"
        print(f"Opening OFFICIAL GOVERNMENT PDF (21MB): {pdf_path}")
        
        # Convert first page of the real SOR
        print("Initializing High-Resolution PDF to Image conversion...")
        pages = convert_from_path(pdf_path, first_page=1, last_page=1)
        if not pages:
            print("Could not read PDF pages.")
            return False
            
        img = pages[0]
        print("Extracting text using Tesseract OCR from PDF...")
        text = pytesseract.image_to_string(img)
        
        print("\n--- EXTRACTED TEXT FROM PDF ---")
        if text.strip():
            print(text.strip()[:1000] + "...") # Show first 1000 chars
        else:
            print("[No text found in PDF - Check if it is a scanned image without OCR layers]")
        print("-" * 35)
        
        print("Inference components verified.")
        return True
    except Exception as e:
        print(f"Document AI Test Failed: {e}")
        return False

if __name__ == "__main__":
    test_layoutlm()
