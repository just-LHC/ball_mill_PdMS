# backend/ml_engine.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier

try:
    from db_engine import fetch_labeled_feedback, init_alert_db_table
    from db_engine import DATABASE_URL
    if DATABASE_URL:
        init_alert_db_table()
except Exception:
    pass

# Retrieve Email Secrets safely from environment
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
MAINTENANCE_LEADS = os.getenv("MAINTENANCE_LEADS")

_MODEL_REGISTRY = {}
_BUFFER_REGISTRY = {}
_FEEDBACK_MODEL_REGISTRY = {}

def _get_model_key(mill: str, equipment: str) -> tuple:
    return (mill.strip(), equipment.strip())

def retrain_equipment_model(mill: str, equipment: str):
    try:
        feedback_rows = fetch_labeled_feedback(mill, equipment)
    except Exception as exc:
        print(f"[MODEL FEEDBACK ERROR] {exc}")
        return {"trained": False, "samples": 0, "message": "Could not load servicing feedback."}

    features = []
    labels = []
    for row in feedback_rows:
        if row["outcome"] == "GENUINE_ISSUE":
            labels.append(1)
        elif row["outcome"] == "FALSE_ALARM":
            labels.append(0)
        else:
            continue
        features.append([row["vibration_snapshot"], row["temperature_snapshot"]])

    class_counts = {"GENUINE_ISSUE": labels.count(1), "FALSE_ALARM": labels.count(0)}
    if min(class_counts.values()) < 2:
        return {
            "trained": False,
            "samples": len(labels),
            "class_counts": class_counts,
            "message": "Collect at least two examples of each servicing outcome before updating this equipment model.",
        }

    model = RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42)
    model.fit(features, labels)
    _FEEDBACK_MODEL_REGISTRY[_get_model_key(mill, equipment)] = model
    return {
        "trained": True,
        "samples": len(labels),
        "class_counts": class_counts,
        "message": "Model retrained with servicing feedback.",
    }

def init_equipment_model(mill: str, equipment: str):
    key = _get_model_key(mill, equipment)
    if key not in _MODEL_REGISTRY:
        model = IsolationForest(contamination=0.05, random_state=42)
        vib_base = 4.0 if equipment == "Mill Main Control" else 2.5
        temp_base = 62.0 if equipment == "E5 & E8 Cement Pumps" else 55.0
        
        initial_features = []
        for _ in range(300):
            vib = np.random.normal(vib_base, 0.4)
            temp = np.random.normal(temp_base, 1.5)
            initial_features.append([max(0, vib), temp])
        
        buffer_df = pd.DataFrame(initial_features, columns=["vibration_mm_s", "temperature_c"])
        model.fit(buffer_df)
        
        _MODEL_REGISTRY[key] = model
        _BUFFER_REGISTRY[key] = buffer_df
        retrain_equipment_model(mill, equipment)

def analyze_telemetry_diagnostics(mill: str, equipment: str, vib: float, temp: float):
    key = _get_model_key(mill, equipment)
    if key not in _MODEL_REGISTRY:
        init_equipment_model(mill, equipment)
        
    model = _MODEL_REGISTRY[key]
    comments = []
    severity = "NORMAL"
    
    if vib > 7.0:
        comments.append("Demo rule flagged high vibration; its boundary is not an engineering-verified plant limit.")
        severity = "CRITICAL"
    elif vib > 4.5:
        comments.append("Demo rule flagged elevated vibration; its boundary is not an engineering-verified plant limit.")
        if severity != "CRITICAL": severity = "WARNING"

    if temp > 90.0:
        comments.append("Demo rule flagged high temperature; its boundary is not an engineering-verified plant limit.")
        severity = "CRITICAL"
    elif temp > 75.0:
        comments.append("Demo rule flagged elevated temperature; its boundary is not an engineering-verified plant limit.")
        if severity != "CRITICAL": severity = "WARNING"

    features = pd.DataFrame([[vib, temp]], columns=["vibration_mm_s", "temperature_c"])
    feedback_model = _FEEDBACK_MODEL_REGISTRY.get(key)
    if feedback_model is not None:
        prediction = feedback_model.predict(features)
        probabilities = feedback_model.predict_proba(features)[0]
        failure_index = list(feedback_model.classes_).index(1)
        is_ml_anomaly = bool(prediction[0] == 1)
        anomaly_score = float(probabilities[failure_index])
        score_label = "Uncalibrated feedback-model class score"
    else:
        prediction = model.predict(features)
        decision_score = model.decision_function(features)
        is_ml_anomaly = bool(prediction[0] == -1)
        anomaly_score = -float(decision_score[0])
        score_label = "Uncalibrated Isolation Forest decision score"

    return {
        "severity": severity,
        "is_anomaly": is_ml_anomaly,
        "anomaly_prob": None,
        "anomaly_score": round(anomaly_score, 4),
        "score_label": score_label,
        "score_calibrated": False,
        "severity_source": "Unverified demo rules; not plant alarm configuration",
        "diagnostic_comments": " | ".join(comments) if comments else "Demo data only; no verified plant limits configured.",
    }