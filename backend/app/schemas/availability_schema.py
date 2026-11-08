from datetime import time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.models.availability import WEEKDAY_LABELS

Weekday = Annotated[int, Field(ge=0, le=6)]


class AvailabilityBlock(BaseModel):
    """Un bloque del horario semanal: 0 = lunes … 6 = domingo, hora local de la clínica."""

    weekday: Weekday
    start_time: time
    end_time: time

    @field_validator("start_time", "end_time")
    def whole_minutes(cls, value: time) -> time:
        if value.second or value.microsecond:
            raise ValueError("La hora debe ser exacta al minuto.")
        return value

    @field_validator("end_time")
    def end_after_start(cls, value: time, info: ValidationInfo) -> time:
        start = info.data.get("start_time")
        if start is not None and value <= start:
            raise ValueError("La hora de fin debe ser posterior a la de inicio.")
        return value

    model_config = ConfigDict(from_attributes=True)


class AvailabilityUpdate(BaseModel):
    """Horario semanal completo: reemplaza al anterior. Una lista vacía lo
    borra y el doctor vuelve a agendarse libremente."""

    blocks: Annotated[list[AvailabilityBlock], Field(max_length=70)]

    @field_validator("blocks")
    def no_overlaps(cls, blocks: list[AvailabilityBlock]) -> list[AvailabilityBlock]:
        ordered = sorted(blocks, key=lambda b: (b.weekday, b.start_time))
        for previous, current in zip(ordered, ordered[1:]):
            if previous.weekday == current.weekday and current.start_time < previous.end_time:
                raise ValueError(f"Los bloques del {WEEKDAY_LABELS[current.weekday]} se cruzan.")
        return ordered


class DoctorAvailabilityResponse(BaseModel):
    doctor_id: int
    timezone: str
    blocks: list[AvailabilityBlock]
