from fastapi import FastAPI
from app.database.connection import Base, engine
from app.models.user import User
from app.api.auth_routes import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="OdontoNet API")

app.include_router(auth_router)


@app.get("/")
def root():
    return {"message": "OdontoNet API running"}
