import pandas as pd

def map_input_to_features(data):
    # claim
    claim = data.get("amount", 0)

    # dispute type mapping
    type_map = {
        "Consumer Product Defect": "refund",
        "Service Failure": "service",
        "Payment Default": "delivery",
        "Contract Breach": "service",
        "Property Dispute": "fraud",
        "MSME Supply Dispute": "delivery"
    }

    dtype = type_map.get(data.get("dispute_type"), "service")

    # strength → evidence
    strength_map = {
        "Strong": 5,
        "Moderate": 3,
        "Weak": 1
    }

    evidence = strength_map.get(data.get("strength_assessment"), 3)

    # severity based on facts + clauses
    severity = min(5, len(data.get("key_facts", [])) + len(data.get("disputed_clauses", [])))

    # default behavior assumptions
    aggressiveness = 3
    flexibility = 3

    return {
        "claim": claim,
        "type": dtype,
        "severity": severity,
        "evidence": evidence,
        "aggressiveness": aggressiveness,
        "flexibility": flexibility
    }


def preprocess_input(data, model):
    features = map_input_to_features(data)

    df = pd.DataFrame([features])
    df = pd.get_dummies(df)

    df = df.reindex(columns=model.feature_names_in_, fill_value=0)

    return df