from satellite import analyze_project

def main():
    print("Running analyze_project for PRJ-DHL (Dholera Smart City)...", flush=True)
    try:
        analyze_project("PRJ-DHL")
    except Exception as e:
        print(f"Error on PRJ-DHL: {e}", flush=True)
        
    print("Running analyze_project for PRJ-DME (Delhi-Mumbai Expressway)...", flush=True)
    try:
        analyze_project("PRJ-DME")
    except Exception as e:
        print(f"Error on PRJ-DME: {e}", flush=True)

    print("All done!", flush=True)

if __name__ == "__main__":
    main()
