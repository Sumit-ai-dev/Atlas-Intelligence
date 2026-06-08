from satellite import analyze_project

if __name__ == "__main__":
    print("Fetching PRJ-DME...", flush=True)
    analyze_project("PRJ-DME")
    print("Done!", flush=True)
