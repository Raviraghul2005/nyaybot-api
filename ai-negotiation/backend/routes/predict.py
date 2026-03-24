from fastapi import APIRouter
from services.ml_model import get_model
from utils.preprocess import preprocess_input

router = APIRouter()

@router.post("/predict")
def predict(data: dict):
    model = get_model()
    processed = preprocess_input(data, model)
    prediction = model.predict(processed)[0]

    return {"predicted_settlement": int(prediction)}