"""Periodontograma manual (ODON-9)."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, conint, constr, root_validator, validator

from app.models.periodontal import (
    FURCATION_ENTRANCES,
    FURCATION_RANGE,
    GINGIVAL_MARGIN_RANGE,
    MOBILITY_RANGE,
    PERMANENT_TEETH,
    PROBING_DEPTH_RANGE,
    SITES,
)

Depth = conint(ge=PROBING_DEPTH_RANGE[0], le=PROBING_DEPTH_RANGE[1])
Margin = conint(ge=GINGIVAL_MARGIN_RANGE[0], le=GINGIVAL_MARGIN_RANGE[1])
Mobility = conint(ge=MOBILITY_RANGE[0], le=MOBILITY_RANGE[1])
Grade = conint(ge=FURCATION_RANGE[0], le=FURCATION_RANGE[1])
Note = constr(strip_whitespace=True, max_length=500)


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class SiteData(BaseModel):
    probing_depth: Optional[Depth] = None
    # Distancia del margen a la UAC: negativa = recesión, positiva = agrandamiento.
    gingival_margin: Optional[Margin] = None
    bleeding: bool = False
    suppuration: bool = False
    plaque: bool = False
    # 'default': valor propuesto (valores de salud o copia) que el profesional aún no editó.
    source: Literal["manual", "default"] = "manual"

    def is_empty(self) -> bool:
        return (
            self.probing_depth is None
            and self.gingival_margin is None
            and not (self.bleeding or self.suppuration or self.plaque)
        )


class Furcation(BaseModel):
    b: Optional[Grade] = None
    mp: Optional[Grade] = None
    dp: Optional[Grade] = None
    l: Optional[Grade] = None  # noqa: E741 (entrada lingual)

    def recorded(self) -> dict[str, int]:
        return {entrance: grade for entrance, grade in self.dict().items() if grade is not None}


class ToothData(BaseModel):
    tooth: int
    missing: bool = False
    implant: bool = False
    mobility: Optional[Mobility] = None
    furcation: Furcation = Furcation()
    note: Optional[Note] = None
    # 'default' si la movilidad se propuso con los valores de salud y no se editó.
    source: Literal["manual", "default"] = "manual"
    sites: dict[str, SiteData] = {}

    _blank_note = validator("note", pre=True, allow_reuse=True)(_blank_to_none)

    @validator("tooth")
    def _permanent(cls, value: int) -> int:
        if value not in PERMANENT_TEETH:
            raise ValueError("La pieza no es una pieza permanente válida (numeración FDI 11–48).")
        return value

    @validator("sites")
    def _known_sites(cls, value: dict) -> dict:
        unknown = set(value) - set(SITES)
        if unknown:
            raise ValueError(f"Sitio desconocido: {', '.join(sorted(unknown))}.")
        return value

    @root_validator(skip_on_failure=True)
    def _consistent(cls, values: dict) -> dict:
        tooth = values["tooth"]
        furcation: Furcation = values["furcation"]
        allowed = set(FURCATION_ENTRANCES.get(tooth, ()))
        invalid = set(furcation.recorded()) - allowed
        if invalid:
            raise ValueError(f"La pieza {tooth} no tiene esa entrada de furcación.")
        if values["missing"]:
            if values["implant"]:
                raise ValueError(f"La pieza {tooth} no puede estar ausente y ser implante a la vez.")
            if values["mobility"] is not None or furcation.recorded():
                raise ValueError(f"La pieza {tooth} está ausente: no lleva movilidad ni furcación.")
            if any(not site.is_empty() for site in values["sites"].values()):
                raise ValueError(f"La pieza {tooth} está ausente: no lleva mediciones.")
        if values["implant"] and furcation.recorded():
            raise ValueError(f"La pieza {tooth} es un implante: no lleva furcación.")
        return values


class ExamContent(BaseModel):
    """Examen completo; se envía entero en cada guardado."""

    exam_date: date
    clinical_visit_id: Optional[int] = None
    notes: Optional[constr(strip_whitespace=True, max_length=4000)] = None
    teeth: list[ToothData] = []

    _blank_notes = validator("notes", pre=True, allow_reuse=True)(_blank_to_none)

    @validator("teeth")
    def _unique_teeth(cls, value: list[ToothData]) -> list[ToothData]:
        seen = [tooth.tooth for tooth in value]
        if len(seen) != len(set(seen)):
            raise ValueError("Cada pieza se envía una sola vez.")
        return value


class ExamCreate(ExamContent):
    pass


class ExamUpdate(ExamContent):
    # Revisión que se estaba editando: si otra persona guardó antes, 409.
    base_revision: conint(ge=1)


class ExamFinalize(BaseModel):
    base_revision: conint(ge=1)


class ExamVoid(BaseModel):
    reason: constr(strip_whitespace=True, min_length=1, max_length=500)


class PersonRef(BaseModel):
    id: int
    name: str


class VisitRef(BaseModel):
    id: int
    reason: str
    visit_at: datetime


class SiteResponse(SiteData):
    # Nivel de inserción clínica = sondaje − margen gingival (calculado).
    attachment_level: Optional[int]


class ToothResponse(BaseModel):
    tooth: int
    missing: bool
    implant: bool
    mobility: Optional[int]
    furcation: Furcation
    note: Optional[str]
    source: str
    sites: dict[str, SiteResponse]


class ExamSummary(BaseModel):
    """Estadística descriptiva; no constituye diagnóstico."""

    present_teeth: int
    measured_sites: int
    mean_probing_depth: Optional[float]
    mean_attachment_level: Optional[float]
    bleeding_pct: Optional[float]
    plaque_pct: Optional[float]
    deep_sites_pct: Optional[float]
    # Sitios con sondaje cuyo valor es predeterminado (no editado por el profesional).
    default_sites: int


class ExamListItem(BaseModel):
    id: int
    patient_id: int
    exam_date: date
    clinical_visit: Optional[VisitRef]
    notes: Optional[str]
    status: str
    revision: int
    created_by: PersonRef
    created_at: datetime
    updated_at: datetime
    finalized_by: Optional[PersonRef]
    finalized_at: Optional[datetime]
    voided_by: Optional[PersonRef]
    voided_at: Optional[datetime]
    void_reason: Optional[str]
    summary: ExamSummary


class ExamResponse(ExamListItem):
    teeth: list[ToothResponse]


class ExamRevisionResponse(BaseModel):
    revision: int
    edited_by: PersonRef
    edited_at: datetime
