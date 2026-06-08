import sys
import json
import joblib
import pandas as pd
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

def predict():
    if len(sys.argv) < 2:
        print("Error: Missing features payload.")
        sys.exit(1)
        
    try:
        payload = json.loads(sys.argv[1])
        xgb_model = joblib.load("infra_ai_xgboost.pkl")
        xgb_features = joblib.load("infra_ai_features.pkl")
        
        df_inference = pd.DataFrame([payload])[xgb_features]
        prediction = xgb_model.predict(df_inference)[0]
        probability = xgb_model.predict_proba(df_inference)[0]
        
        approval_chance = probability[1] * 100
        rejection_chance = probability[0] * 100
        
        result = {
            "prediction": int(prediction),
            "approval_probability": float(approval_chance),
            "rejection_probability": float(rejection_chance)
        }
        
        # Print ONLY the JSON so the parent process can parse it
        print(json.dumps(result))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    predict()
