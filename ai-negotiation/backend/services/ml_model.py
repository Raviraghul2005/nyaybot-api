import joblib
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parents[2] / "ml" / "model.pkl"
model = joblib.load(MODEL_PATH)

def get_model():
    return model