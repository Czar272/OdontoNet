from pydantic import BaseModel


class ClinicCreate(BaseModel):

    name: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None


class ClinicResponse(BaseModel):

    id: int
    name: str
    address: str | None
    phone: str | None
    email: str | None

    class Config:
        orm_mode = True
