"""Historia médica y odontológica del paciente (ODON-150)."""
from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import BaseModel, conint, constr, root_validator, validator

from app.models.medical_history import MEDICAL_CONDITIONS

# Textos libres: sin espacios sobrantes; vacío se guarda como "sin dato" (null).
LongText = constr(strip_whitespace=True, max_length=2000)
ShortText = constr(strip_whitespace=True, max_length=500)


def _blank_to_none(value):
    return None if isinstance(value, str) and value == "" else value


class ConditionEntry(BaseModel):
    # None = sin dato; False = no; True = sí.
    present: Optional[bool] = None
    detail: Optional[ShortText] = None

    _blank_detail = validator("detail", allow_reuse=True)(_blank_to_none)


class MedicalHistoryData(BaseModel):
    """Contenido de una versión. Toda la historia se envía en cada guardado."""

    conditions: Dict[str, ConditionEntry] = {}
    other_conditions: Optional[LongText] = None
    allergies: Optional[LongText] = None
    current_medications: Optional[LongText] = None

    smoking_status: Optional[Literal["never", "former", "current"]] = None
    cigarettes_per_day: Optional[conint(ge=1, le=200)] = None
    alcohol: Optional[bool] = None
    alcohol_detail: Optional[ShortText] = None
    bruxism: Optional[bool] = None

    chief_complaint: Optional[LongText] = None
    last_dental_visit: Optional[constr(strip_whitespace=True, max_length=80)] = None
    previous_treatments: Optional[LongText] = None
    brushing_per_day: Optional[conint(ge=0, le=10)] = None
    uses_floss: Optional[bool] = None
    gum_bleeding: Optional[bool] = None

    notes: Optional[LongText] = None

    _blank_texts = validator(
        "other_conditions",
        "allergies",
        "current_medications",
        "alcohol_detail",
        "chief_complaint",
        "last_dental_visit",
        "previous_treatments",
        "notes",
        allow_reuse=True,
    )(_blank_to_none)

    @validator("conditions")
    def _known_conditions(cls, value: Dict[str, ConditionEntry]) -> Dict[str, ConditionEntry]:
        unknown = sorted(set(value) - set(MEDICAL_CONDITIONS))
        if unknown:
            raise ValueError(f"Condición desconocida: {', '.join(unknown)}.")
        # Siempre la lista completa, en orden fijo: lo no enviado queda sin dato.
        return {key: value.get(key, ConditionEntry()) for key in MEDICAL_CONDITIONS}

    @root_validator(skip_on_failure=True)
    def _cigarettes_only_if_smoker(cls, values):
        if values.get("cigarettes_per_day") is not None and values.get("smoking_status") != "current":
            raise ValueError("Indica cigarrillos al día solo si el paciente fuma actualmente.")
        return values


class MedicalHistoryCreate(MedicalHistoryData):
    # Versión que se estaba editando (null si el paciente aún no tiene historia).
    # Si otra persona guardó antes, la API responde 409 en vez de pisar su cambio.
    base_version: Optional[conint(ge=1)] = None


class HistoryAuthor(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class MedicalHistoryVersionSummary(BaseModel):
    version: int
    created_at: datetime
    created_by: HistoryAuthor

    class Config:
        orm_mode = True


class MedicalHistoryResponse(MedicalHistoryData):
    version: int
    created_at: datetime
    created_by: HistoryAuthor

    class Config:
        orm_mode = True
