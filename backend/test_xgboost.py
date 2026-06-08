import joblib
import pandas as pd

def test_live_prediction():
    print("=========================================")
    print("🔍 INFRA-AI MODEL INFERENCE TEST 🔍")
    print("=========================================\n")
    
    try:
        # Load the artifacts we generated in training
        model = joblib.load("infra_ai_xgboost.pkl")
        features = joblib.load("infra_ai_features.pkl")
        print("[*] Successfully loaded infra_ai_xgboost.pkl")
        print("[*] Successfully loaded infra_ai_features.pkl")
    except Exception as e:
        print(f"[!] Error loading model: {e}")
        return

    # Let's create two mock Civil Engineering projects to test the AI.

    # Project 1: A perfect project (Approved)
    mock_project_1 = {
        "budget_cr": 150.0,
        "time_gap_months": 12,  # Good, < 36 months
        "violations.planning_and_dpr.faulty_topographical_survey": 0,
        "violations.planning_and_dpr.unplanned_utility_shifting": 0,
        "violations.clearances_and_land.land_acquisition_incomplete": 0,
        "violations.clearances_and_land.missing_forest_clearance": 0,
        "violations.clearances_and_land.missing_environmental_clearance": 0,
        "violations.financial_and_tendering.ineligible_bidder_awarded": 0,
        "violations.financial_and_tendering.ccea_scrutiny_bypassed": 0,
        "violations.financial_and_tendering.toll_management_system_noncompliant": 0
    }

    # Project 2: A terrible project (Rejected due to Land and Time)
    mock_project_2 = {
        "budget_cr": 800.0,
        "time_gap_months": 45,  # Fatal flaw! (> 36 months)
        "violations.planning_and_dpr.faulty_topographical_survey": 0,
        "violations.planning_and_dpr.unplanned_utility_shifting": 1,
        "violations.clearances_and_land.land_acquisition_incomplete": 1, # Fatal flaw!
        "violations.clearances_and_land.missing_forest_clearance": 0,
        "violations.clearances_and_land.missing_environmental_clearance": 0,
        "violations.financial_and_tendering.ineligible_bidder_awarded": 0,
        "violations.financial_and_tendering.ccea_scrutiny_bypassed": 0,
        "violations.financial_and_tendering.toll_management_system_noncompliant": 0
    }

    # Convert to DataFrame in the exact feature order the model expects
    df_1 = pd.DataFrame([mock_project_1])[features]
    df_2 = pd.DataFrame([mock_project_2])[features]

    print("\n-----------------------------------------")
    print("Testing Project 1: The 'Perfect' Project")
    print("Features:", mock_project_1)
    pred_1 = model.predict(df_1)[0]
    prob_1 = model.predict_proba(df_1)[0]
    print(f"--> AI Prediction: {'✅ APPROVED' if pred_1 == 1 else '❌ REJECTED'}")
    print(f"--> AI Confidence: {prob_1[1]*100:.2f}% chance of approval.")
    print("-----------------------------------------")

    print("\n-----------------------------------------")
    print("Testing Project 2: The 'Disaster' Project (45 mo gap, Missing Land)")
    print("Features:", mock_project_2)
    pred_2 = model.predict(df_2)[0]
    prob_2 = model.predict_proba(df_2)[0]
    print(f"--> AI Prediction: {'✅ APPROVED' if pred_2 == 1 else '❌ REJECTED'}")
    print(f"--> AI Confidence: {prob_2[0]*100:.2f}% chance of rejection.")
    print("-----------------------------------------")
    
if __name__ == "__main__":
    test_live_prediction()
