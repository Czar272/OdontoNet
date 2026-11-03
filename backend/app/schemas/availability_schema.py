from datetime import time

from pydantic import BaseModel, conint, conlist, validator

from app.models.availability import WEEKDAY_LABELS

Weekday = conint(ge=0, le=6)


class AvailabilityBlock(BaseModel):
    """Un bloque del horario semanal: 0 = lunes … 6 = domingo, hora local de la clínica."""

    weekday: Weekday
    start_time: time
    end_time: time

    @validator("start_time", "end_time")
    def whole_minutes(cls, value: time) -> time:
        if value.second or value.microsecond:
            raise ValueError("La hora debe ser exacta al minuto.")
        return value

    @validator("end_time")
    def end_after_start(cls, value: time, values: dict) -> time:
        start = values.get("start_time")
        if start is not None and value <= start:
            raise ValueError("La hora de fin debe ser posterior a la de inicio.")
        return value

    class Config:
        orm_mode = True


class AvailabilityUpdate(BaseModel):
    """Horario semanal completo: reemplaza al anterior. Una lista vacía lo
    borra y el doctor vuelve a agendarse libremente."""

    blocks: conlist(AvailabilityBlock, max_items=70)

    @validator("blocks")
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
