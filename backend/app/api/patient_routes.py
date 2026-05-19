from fastapi import APIRouter

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/")
def get_patients():
    return {"message": "Patients endpoint"}
