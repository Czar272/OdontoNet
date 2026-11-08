"""Historia médica y odontológica del paciente (ODON-150)."""
from typing import Annotated, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.core.errors import root_error
from app.models.medical_history import MEDICAL_CONDITIONS
from app.schemas.fields import DateTime

# Textos libres: sin espacios sobrantes; vacío se guarda como "sin dato" (null).
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


def _blank_to_none(value):
    return None if isinstance(value, str) and value == "" else value


class ConditionEntry(BaseModel):
    # None = sin dato; False = no; True = sí.
    present: Optional[bool] = None
    detail: Optional[ShortText] = None

    _blank_detail = field_validator("detail")(_blank_to_none)


class MedicalHistoryData(BaseModel):
    """Contenido de una versión. Toda la historia se envía en cada guardado."""

    conditions: Dict[str, ConditionEntry] = {}
    other_conditions: Optional[LongText] = None
    allergies: Optional[LongText] = None
    current_medications: Optional[LongText] = None

    smoking_status: Optional[Literal["never", "former", "current"]] = None
    cigarettes_per_day: Optional[Annotated[int, Field(ge=1, le=200)]] = None
    alcohol: Optional[bool] = None
    alcohol_detail: Optional[ShortText] = None
    bruxism: Optional[bool] = None

    chief_complaint: Optional[LongText] = None
    last_dental_visit: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]] = None
    previous_treatments: Optional[LongText] = None
    brushing_per_day: Optional[Annotated[int, Field(ge=0, le=10)]] = None
    uses_floss: Optional[bool] = None
    gum_bleeding: Optional[bool] = None

    notes: Optional[LongText] = None

    _blank_texts = field_validator(
        "other_conditions",
        "allergies",
        "current_medications",
        "alcohol_detail",
        "chief_complaint",
        "last_dental_visit",
        "previous_treatments",
        "notes",
    )(_blank_to_none)

    @field_validator("conditions")
    def _known_conditions(cls, value: Dict[str, ConditionEntry]) -> Dict[str, ConditionEntry]:
        unknown = sorted(set(value) - set(MEDICAL_CONDITIONS))
        if unknown:
            raise ValueError(f"Condición desconocida: {', '.join(unknown)}.")
        # Siempre la lista completa, en orden fijo: lo no enviado queda sin dato.
        return {key: value.get(key, ConditionEntry()) for key in MEDICAL_CONDITIONS}

    @model_validator(mode="after")
    def _cigarettes_only_if_smoker(self):
        if self.cigarettes_per_day is not None and self.smoking_status != "current":
            raise root_error("Indica cigarrillos al día solo si el paciente fuma actualmente.")
        return self


class MedicalHistoryCreate(MedicalHistoryData):
    # Versión que se estaba editando (null si el paciente aún no tiene historia).
    # Si otra persona guardó antes, la API responde 409 en vez de pisar su cambio.
    base_version: Optional[Annotated[int, Field(ge=1)]] = None


class HistoryAuthor(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MedicalHistoryVersionSummary(BaseModel):
    version: int
    created_at: DateTime
    created_by: HistoryAuthor

    model_config = ConfigDict(from_attributes=True)


class MedicalHistoryResponse(MedicalHistoryData):
    version: int
    created_at: DateTime
    created_by: HistoryAuthor

    model_config = ConfigDict(from_attributes=True)
