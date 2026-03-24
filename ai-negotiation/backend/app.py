from fastapi import FastAPI
from routes.predict import router as predict_router

app = FastAPI()

app.include_router(predict_router)

@app.get("/")
def home():
    return {"message": "Backend running"}