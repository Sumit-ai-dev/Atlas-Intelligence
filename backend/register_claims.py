from satellite import save_dpr_record, refresh_all
import os

def main():
    # Register the original fraudulent claims
    save_dpr_record("PRJ-DHL", 85.0, "DICDL_May2026_Activation_Progress.pdf", reported_date="2026-05-26", raw_excerpt="Overall Physical Progress: 85%")
    save_dpr_record("PRJ-DME", 92.0, "NHAI_March2026_DME_Progress.pdf", reported_date="2026-05-15", raw_excerpt="Phase 1 Completion: 92%")
    save_dpr_record("PRJ-NMA", 45.0, "CIDCO_April2026_NMA_Progress.pdf", reported_date="2026-06-02", raw_excerpt="Earthworks Progress: 45%")
    
    print("Claims registered.")

if __name__ == "__main__":
    main()
