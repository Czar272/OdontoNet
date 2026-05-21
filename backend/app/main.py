from fastapi import FastAPI
from app.database.connection import Base, engine
from app.models.user import User
from app.models.patient import Patient
from app.api.auth_routes import router as auth_router
from app.api.patient_routes import router as patient_router
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)


app = FastAPI(title="OdontoNet API")

app.include_router(auth_router)
app.include_router(patient_router)

origins = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "OdontoNet API running"}
