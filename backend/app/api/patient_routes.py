import logging
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, joinedload

from app.auth.dependencies import get_current_clinic_id, get_current_user
from app.auth.permissions import ALL_ROLES, require_roles
from app.database.dependencies import get_db
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient_schema import PatientCreate, PatientPage, PatientResponse, PatientUpdate

# Eventos de auditoría (sin datos personales: solo ids y nombres de campos).
# La auditoría persistente se diseña en ODON-222.
audit_logger = logging.getLogger("odontonet.audit")

# Administración, doctores y recepción gestionan pacientes (docs/PERMISSIONS.md).
router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
    dependencies=[Depends(require_roles(*ALL_ROLES))],
)


# Búsqueda sin tildes ni mayúsculas que no depende de la collation de la base
# ni de extensiones (unaccent): translate quita las tildes y lower el resto.
_ACCENTED = "ÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛÑÇáàäâéèëêíìïîóòöôúùüûñç"
_PLAIN = "AAAAEEEEIIIIOOOOUUUUNCaaaaeeeeiiiioooouuuunc"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# Para ordenar, la ñ va después de la n: "n~" queda entre "nz" y "o" en
# COLLATE "C" ('~' es mayor que cualquier letra ASCII).
_ACCENTED_NO_ENE = _ACCENTED.replace("Ñ", "").replace("ñ", "")
_PLAIN_NO_ENE = _PLAIN[:_ACCENTED.index("Ñ")] + _PLAIN[_ACCENTED.index("Ñ") + 1 : _ACCENTED.index("ñ")] + _PLAIN[_ACCENTED.index("ñ") + 1 :]

# Un término de solo dígitos y separadores también busca en el teléfono.
_MIN_PHONE_DIGITS = 3


def _normalized_sql(column):
    """Texto para buscar: sin tildes ni mayúsculas ("Núñez" → "nunez")."""
    return func.lower(func.translate(column, _ACCENTED, _PLAIN))


def _sort_key_sql(column):
    """Texto para ordenar alfabéticamente en español ("Núñez" → "nun~ez")."""
    plain = func.translate(column, _ACCENTED_NO_ENE, _PLAIN_NO_ENE)
    return func.lower(func.replace(func.replace(plain, "ñ", "n~"), "Ñ", "n~")).collate("C")


def _phone_digits(term: str) -> str | None:
    """Dígitos del término si parece un teléfono ("5555-01" → "555501")."""
    if not all(ch.isdigit() or ch in " -+()" for ch in term):
        return None
    digits = "".join(ch for ch in term if ch.isdigit())
    return digits if len(digits) >= _MIN_PHONE_DIGITS else None


def _normalized_text(text_value: str) -> str:
    """Mismo criterio que _normalized_sql, en Python: "José  PÉREZ" → "jose perez"."""
    decomposed = unicodedata.normalize("NFD", text_value)
    plain = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(plain.lower().split())


def _clinic_patients(db: Session, clinic_id: int) -> Query:
    """Pacientes de la clínica indicada, con su doctor y usuario cargados."""
    return (
        db.query(Patient)
        .options(joinedload(Patient.doctor).joinedload(Doctor.user))
        .filter(Patient.clinic_id == clinic_id)
    )


def _ensure_doctor_in_clinic(db: Session, doctor_id: int, clinic_id: int) -> None:
    doctor = (
        db.query(Doctor)
        .options(joinedload(Doctor.user))
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic_id)
        .first()
    )

    if not doctor:
        # Mismo mensaje si no existe o si es de otra clínica: no se revela nada.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El doctor seleccionado no pertenece a la clínica.",
        )

    if doctor.user.is_active is False:
        # Los pacientes ya asignados lo conservan (ODON-94); no se asignan nuevos.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El doctor seleccionado está inactivo.",
        )


def _get_clinic_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    """Paciente de la clínica o 404 (también si es de otra clínica)."""
    patient = _clinic_patients(db, clinic_id).filter(Patient.id == patient_id).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado."
        )

    return patient


def _commit(db: Session, clinic_id: int, email: str | None) -> None:
    """Guarda y traduce las restricciones de la base a errores de la API."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_patients_clinic_email" in str(exc.orig):
            owner = (
                db.query(Patient.archived_at)
                .filter(Patient.clinic_id == clinic_id, Patient.email == email)
                .first()
            )
            if owner is not None and owner.archived_at is not None:
                # El correo lo conserva un archivado: reactivarlo evita duplicados.
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un paciente archivado con ese correo en la clínica. "
                    "Reactívalo desde la lista de archivados.",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un paciente con ese correo en la clínica.",
            )
        # Otra restricción (p. ej. fk_patients_doctor_clinic si el doctor cambió
        # entre la validación y el guardado): mismo mensaje que la validación.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El doctor seleccionado no pertenece a la clínica.",
        )


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    patient: PatientCreate,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):

    if patient.doctor_id is not None:
        _ensure_doctor_in_clinic(db, patient.doctor_id, clinic_id)

    new_patient = Patient(**patient.dict(), clinic_id=clinic_id)

    db.add(new_patient)

    _commit(db, clinic_id, patient.email)

    return _clinic_patients(db, clinic_id).filter(Patient.id == new_patient.id).one()


@router.get("/", response_model=PatientPage)
def get_patients(
    archived: bool = QueryParam(
        False, description="false: solo activos (por defecto) · true: solo archivados."
    ),
    q: str | None = QueryParam(
        None, max_length=100,
        description="Nombre y/o apellidos (en cualquier orden, sin tildes ni mayúsculas), "
        "correo o teléfono (solo dígitos, mínimo 3).",
    ),
    doctor_id: int | None = QueryParam(None, description="Solo pacientes de este doctor."),
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Listado paginado de la clínica (ODON-126), ordenado por apellidos y nombres."""
    filters = [Patient.clinic_id == clinic_id]
    filters.append(Patient.archived_at.is_not(None) if archived else Patient.archived_at.is_(None))

    if doctor_id is not None:
        # Un doctor de otra clínica no coincide con ningún paciente: lista vacía.
        filters.append(Patient.doctor_id == doctor_id)

    term = _normalized_text(q or "")
    if term:
        first = _normalized_sql(Patient.first_name)
        last = _normalized_sql(Patient.last_name)
        conditions = [
            (first.concat(" ").concat(last)).contains(term, autoescape=True),
            (last.concat(" ").concat(first)).contains(term, autoescape=True),
            func.lower(Patient.email).contains(term, autoescape=True),
        ]
        digits = _phone_digits(term)
        if digits:
            # El teléfono se compara solo por dígitos: "5555 0101" encuentra "5555-0101".
            conditions.append(
                func.regexp_replace(Patient.phone, "[^0-9]", "", "g").contains(digits, autoescape=True)
            )
        filters.append(or_(*conditions))

    total = db.query(func.count(Patient.id)).filter(*filters).scalar()

    items = (
        _clinic_patients(db, clinic_id)
        .filter(*filters)
        # COLLATE "C" (en _sort_key_sql): mismo orden en Windows (en_US) y en CI (C.UTF-8).
        .order_by(
            _sort_key_sql(Patient.last_name),
            _sort_key_sql(Patient.first_name),
            Patient.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):

    # Los archivados también se consultan: su ficha e historial se conservan.
    return _get_clinic_patient(db, patient_id, clinic_id)


@router.patch("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    changes: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Edita datos del paciente o reasigna su doctor (ODON-118)."""
    patient = _get_clinic_patient(db, patient_id, clinic_id)

    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para editar sus datos.",
        )

    data = changes.dict(exclude_unset=True)

    for required in ("first_name", "last_name"):
        if required in data and data[required] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nombres y apellidos son obligatorios.",
            )

    previous_doctor_id = patient.doctor_id
    new_doctor_id = data.get("doctor_id", previous_doctor_id)
    # Solo se valida si cambia: editar el teléfono de un paciente cuyo doctor
    # se desactivó no debe fallar.
    if new_doctor_id != previous_doctor_id and new_doctor_id is not None:
        _ensure_doctor_in_clinic(db, new_doctor_id, clinic_id)

    changed = [field for field, value in data.items() if getattr(patient, field) != value]
    for field in changed:
        setattr(patient, field, data[field])

    if changed:
        _commit(db, clinic_id, patient.email)
        audit_logger.info(
            "patient.updated patient_id=%s user_id=%s clinic_id=%s fields=%s",
            patient.id, current_user.id, clinic_id, ",".join(sorted(changed)),
        )
        if "doctor_id" in changed:
            audit_logger.info(
                "patient.doctor_changed patient_id=%s user_id=%s from=%s to=%s",
                patient.id, current_user.id, previous_doctor_id, new_doctor_id,
            )

    db.expire_all()
    return _clinic_patients(db, clinic_id).filter(Patient.id == patient_id).one()


def _set_archived(
    db: Session, patient_id: int, clinic_id: int, current_user: User, archived: bool
) -> Patient:
    """Archiva o reactiva sin borrar nada. Es idempotente: repetir la acción
    no cambia la fecha de archivo ni genera un evento de auditoría nuevo."""
    patient = _get_clinic_patient(db, patient_id, clinic_id)

    if (patient.archived_at is not None) is not archived:
        patient.archived_at = datetime.now(timezone.utc) if archived else None
        db.commit()
        audit_logger.info(
            "patient.%s patient_id=%s user_id=%s clinic_id=%s",
            "archived" if archived else "reactivated",
            patient.id, current_user.id, clinic_id,
        )

    db.expire_all()
    return _clinic_patients(db, clinic_id).filter(Patient.id == patient_id).one()


@router.post("/{patient_id}/archive", response_model=PatientResponse)
def archive_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Archiva al paciente (ODON-122): sale del listado de activos, pero sus
    datos e historial se conservan y se puede reactivar."""
    return _set_archived(db, patient_id, clinic_id, current_user, archived=True)


@router.post("/{patient_id}/reactivate", response_model=PatientResponse)
def reactivate_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Devuelve un paciente archivado al listado de activos (ODON-122)."""
    return _set_archived(db, patient_id, clinic_id, current_user, archived=False)
