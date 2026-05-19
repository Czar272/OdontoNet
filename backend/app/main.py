from fastapi import FastAPI
from app.database.connection import Base, engine
from app.models.patient import Patient

from app.api.patient_routes import router as patient_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="OdontoNet API", version="1.0.0")


@app.get("/")
def root():
    return {"message": "OdontoNet API running"}


app.include_router(patient_router)
