import os
from pathlib import Path
from typing import Any, Dict

import joblib
import pandas as pd


MODEL_RELATIVE_PATH = Path("ai-negotiation") / "ml" / "model.pkl"


def _map_input_to_features(data: Dict[str, Any]) -> Dict[str, Any]:
    claim = int(data.get("amount", 0) or 0)

    type_map = {
        "Consumer Product Defect": "refund",
        "Service Failure": "service",
        "Payment Default": "delivery",
        "Contract Breach": "service",
        "Property Dispute": "fraud",
        "MSME Supply Dispute": "delivery",
    }
    dispute_type = type_map.get(data.get("dispute_type"), "service")

    strength_map = {
        "Strong": 5,
        "Moderate": 3,
        "Weak": 1,
    }
    evidence = strength_map.get(data.get("strength_assessment"), 3)

    severity = min(
        5,
        len(data.get("key_facts", [])) + len(data.get("disputed_clauses", [])),
    )

    return {
        "claim": claim,
        "type": dispute_type,
        "severity": severity,
        "evidence": evidence,
        "aggressiveness": 3,
        "flexibility": 3,
    }


def _load_model():
    model_path = Path(__file__).resolve().parents[1] / MODEL_RELATIVE_PATH
    if not model_path.exists():
        raise FileNotFoundError(
            f"ML model not found at '{model_path}'. Train and save model.pkl first."
        )
    return joblib.load(model_path)


def predict_boundary_values(intake: Dict[str, Any], spread_ratio: float = 0.15) -> Dict[str, int]:
    model = _load_model()

    features = _map_input_to_features(intake)
    df = pd.DataFrame([features])
    df = pd.get_dummies(df)
    df = df.reindex(columns=model.feature_names_in_, fill_value=0)

    predicted_settlement = int(model.predict(df)[0])
    claim_amount = int(intake.get("amount", 0) or 0)

    if claim_amount > 0:
        predicted_settlement = max(0, min(predicted_settlement, claim_amount))

    lower = int(predicted_settlement * (1 - spread_ratio))
    upper = int(predicted_settlement * (1 + spread_ratio))

    if claim_amount > 0:
        upper = min(upper, claim_amount)

    return {
        "predicted_settlement": predicted_settlement,
        "boundary_low": max(0, lower),
        "boundary_high": max(0, upper),
    }
