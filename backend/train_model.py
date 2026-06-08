import json
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

def load_and_flatten_data(json_file):
    print(f"[*] Loading massive dataset: {json_file}")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Flatten the nested JSON structure into a Pandas DataFrame
    df = pd.json_normalize(data)
    print(f"[*] Extracted {len(df)} records with {len(df.columns)} columns.")
    return df

def train_xgboost():
    print("=========================================")
    print("🚀 INFRA-AI XGBOOST TRAINING ENGINE 🚀")
    print("=========================================\n")
    
    # 1. Load Data
    json_path = "cppp_historical_training_data.json"
    df = load_and_flatten_data(json_path)
    
    # 2. Feature Engineering
    # We want to use the mathematical features, dropping strings like department/state for this MVP
    # Features: budget_cr, time_gap_months, and all the nested violation flags
    feature_cols = [col for col in df.columns if col.startswith('violations.') or col in ['budget_cr', 'time_gap_months']]
    
    X = df[feature_cols]
    y = df['status']
    
    print("\n[*] Training Features Used:")
    for col in feature_cols:
        print(f"    - {col}")
        
    # 3. Split Dataset
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"\n[*] Split complete: {len(X_train)} training records, {len(X_test)} testing records.")
    
    # 4. Train Model
    print("\n[*] Initializing XGBoost Classifier...")
    model = XGBClassifier(
        n_estimators=100, 
        learning_rate=0.1, 
        max_depth=5, 
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    print("[*] Training in progress (this may take a few seconds due to 115k records)...")
    model.fit(X_train, y_train)
    print("[*] Training Complete! ✅")
    
    # 5. Evaluate Model
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n[*] Model Accuracy: {acc * 100:.2f}%")
    print("\n[*] Classification Report:")
    print(classification_report(y_test, y_pred))
    
    # 6. Feature Importance Extract
    print("\n[*] Top 5 Critical Features Driving Government Rejections:")
    importance = model.feature_importances_
    sorted_idx = np.argsort(importance)[::-1]
    
    for i in range(5):
        idx = sorted_idx[i]
        print(f"    {i+1}. {feature_cols[idx]} (Weight: {importance[idx]:.4f})")
        
    # 7. Save Artifact
    model_path = "infra_ai_xgboost.pkl"
    joblib.dump(model, model_path)
    
    # Save the feature column names so the backend API knows what order to feed them in later
    joblib.dump(feature_cols, "infra_ai_features.pkl")
    
    print(f"\n[*] Model securely saved to {model_path}")
    print("[*] Feature list saved to infra_ai_features.pkl")
    print("\n=========================================")
    print("🏆 PHASE 2 ML TRAINING COMPLETE 🏆")
    print("=========================================")

if __name__ == "__main__":
    train_xgboost()
