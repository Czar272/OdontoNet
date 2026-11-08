"""Seed sintético de desarrollo (ODON-34).

Crea dos clínicas de demostración, cada una con administración, recepción,
dos doctores, pacientes ficticios relacionados y una agenda de citas
alrededor de la fecha de ejecución (ODON-138). Sirve para probar la
aplicación y el aislamiento entre clínicas sin datos reales.

Garantías:
- Idempotente: se puede ejecutar varias veces sin duplicar registros. Las
  citas solo se crean si la clínica todavía no tiene ninguna, para no
  cruzarse con una agenda que ya existe.
- No borra ni modifica datos existentes; solo agrega lo que falte.
- Transaccional: si algo falla, no queda nada a medias.
- Solo desarrollo: se niega a correr si la base no es local o si
  APP_ENV es distinto de "development".
- Sin credenciales en el código: la contraseña se toma de SEED_PASSWORD.

Uso, desde backend/ con odonto_venv activo:

    $env:SEED_PASSWORD = "<contraseña de al menos 10 caracteres, no común>"
    python -m scripts.seed_dev
"""

import os
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.core.password_policy import MIN_LENGTH, check_new_password  # noqa: E402
from app.models import (  # noqa: E402
    Appointment,
    AppointmentStatusChange,
    Clinic,
    Doctor,
    DoctorAvailabilityBlock,
    Patient,
    User,
)

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
EMAIL_DOMAIN = "odontonet-demo.com"
PATIENTS_PER_CLINIC = 15

# Agenda demo: días hábiles desde 3 días antes hasta 10 después de hoy.
APPOINTMENT_DAYS = range(-3, 11)
# Horas por doctor (índice en STAFF de doctores): no se cruzan entre doctores,
# así un paciente nunca queda con dos citas a la vez.
DOCTOR_HOURS = [(9, 11, 15), (10, 14, 16)]
APPOINTMENT_REASONS = ["Limpieza", "Control", "Evaluación periodontal", "Raspado y alisado", "Consulta"]
CLINIC_TZ = timezone(timedelta(hours=-6))  # America/Guatemala, sin horario de verano
# Horario demo (ODON-142): lunes a viernes, mañana y tarde. Cubre la agenda demo.
DEMO_SCHEDULE = [(time(8, 0), time(13, 0)), (time(14, 0), time(18, 0))]

CLINICS = [
    {
        "slug": "norte",
        "name": "Clínica Demo Norte",
        "address": "Zona 1, Ciudad de Guatemala",
        "phone": "2200-0001",
    },
    {
        "slug": "sur",
        "name": "Clínica Demo Sur",
        "address": "Zona 12, Ciudad de Guatemala",
        "phone": "2200-0002",
    },
]

# (prefijo de correo, nombre, rol, especialidad si es doctor)
STAFF = [
    ("admin", "Administración", "admin", None),
    ("recepcion", "Recepción", "receptionist", None),
    ("doctor1", "Dra. Ana Morales", "doctor", "Periodoncia"),
    ("doctor2", "Dr. Luis Herrera", "doctor", "Odontología general"),
]

FIRST_NAMES = [
    "María",
    "José",
    "Ana",
    "Carlos",
    "Lucía",
    "Jorge",
    "Sofía",
    "Diego",
    "Valeria",
    "Andrés",
    "Gabriela",
    "Fernando",
    "Camila",
    "Ricardo",
    "Daniela",
    "Miguel",
]
LAST_NAMES = [
    "García",
    "López",
    "Pérez",
    "Hernández",
    "Gómez",
    "Morales",
    "Castillo",
    "Ramírez",
    "Méndez",
    "Ruiz",
    "Ortiz",
    "Cruz",
    "Reyes",
    "Flores",
    "Juárez",
    "Sandoval",
]


class SeedError(RuntimeError):
    """Condición que impide ejecutar el seed de forma segura."""


def ensure_development(database_url: str, environment: str) -> None:
    if environment != "development":
        raise SeedError(
            f"APP_ENV={environment!r}: el seed solo se ejecuta en desarrollo."
        )

    host = make_url(database_url).host
    if host not in LOCAL_HOSTS:
        raise SeedError(
            f"La base está en {host!r}; el seed solo se ejecuta contra una base local."
        )


def read_password(value: str | None) -> str:
    # Misma política que la API (ODON-230): 10 caracteres y no una contraseña filtrada.
    if not value or len(value) < MIN_LENGTH:
        raise SeedError(
            f"Define SEED_PASSWORD con al menos {MIN_LENGTH} caracteres antes de ejecutar el seed."
        )
    try:
        check_new_password(value)
    except ValueError as exc:
        raise SeedError(f"SEED_PASSWORD no es válida: {exc}") from exc
    return value


def staff_email(prefix: str, clinic_slug: str) -> str:
    return f"{prefix}.{clinic_slug}@{EMAIL_DOMAIN}"


def _patient_data(clinic_slug: str, index: int) -> dict:
    # Semilla por paciente: los datos son siempre los mismos en cada ejecución.
    rng = random.Random(f"{clinic_slug}-{index}")
    first_name = rng.choice(FIRST_NAMES)
    last_name = f"{rng.choice(LAST_NAMES)} {rng.choice(LAST_NAMES)}"
    return {
        "first_name": first_name,
        "last_name": last_name,
        "birth_date": date(1950, 1, 1) + timedelta(days=rng.randint(0, 365 * 65)),
        "phone": f"5{rng.randint(1000000, 9999999)}",
        "email": f"paciente{index:02d}.{clinic_slug}@{EMAIL_DOMAIN}",
        "address": f"Zona {rng.randint(1, 21)}, Ciudad de Guatemala",
    }


def seed(db: Session, password: str) -> dict:
    """Crea los datos que falten y devuelve cuántos registros nuevos agregó."""
    created = {
        "clinics": 0,
        "users": 0,
        "doctors": 0,
        "patients": 0,
        "appointments": 0,
        "schedules": 0,
    }
    password_hash = None

    for spec in CLINICS:
        clinic = db.query(Clinic).filter(Clinic.name == spec["name"]).first()
        if clinic is None:
            clinic = Clinic(
                name=spec["name"],
                address=spec["address"],
                phone=spec["phone"],
                email=f"contacto.{spec['slug']}@{EMAIL_DOMAIN}",
            )
            db.add(clinic)
            db.flush()
            created["clinics"] += 1

        doctors = []
        receptionist = None
        for prefix, name, role, specialization in STAFF:
            email = staff_email(prefix, spec["slug"])
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                password_hash = password_hash or hash_password(password)
                user = User(
                    name=name,
                    email=email,
                    hashed_password=password_hash,
                    role=role,
                    is_active=True,
                    clinic_id=clinic.id,
                )
                db.add(user)
                db.flush()
                created["users"] += 1

            if role == "receptionist":
                receptionist = user

            if role == "doctor":
                doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
                if doctor is None:
                    doctor = Doctor(
                        user_id=user.id,
                        clinic_id=clinic.id,
                        specialization=specialization,
                        license_number=f"DEMO-{spec['slug'].upper()}-{prefix[-1]}",
                    )
                    db.add(doctor)
                    db.flush()
                    created["doctors"] += 1
                doctors.append(doctor)
                # Horario demo solo para doctores que aún no tienen uno.
                if not doctor.availability:
                    doctor.availability = [
                        DoctorAvailabilityBlock(
                            clinic_id=clinic.id, weekday=weekday, start_time=start, end_time=end
                        )
                        for weekday in range(5)
                        for start, end in DEMO_SCHEDULE
                    ]
                    created["schedules"] += 1

        for index in range(1, PATIENTS_PER_CLINIC + 1):
            data = _patient_data(spec["slug"], index)
            exists = (
                db.query(Patient.id)
                .filter(Patient.clinic_id == clinic.id, Patient.email == data["email"])
                .first()
            )
            if exists:
                continue
            # Cada tercer paciente queda sin doctor asignado.
            doctor = None if index % 3 == 0 else doctors[index % len(doctors)]
            db.add(
                Patient(
                    **data, clinic_id=clinic.id, doctor_id=doctor.id if doctor else None
                )
            )
            created["patients"] += 1

        db.flush()
        created["appointments"] += _seed_appointments(db, clinic, doctors, receptionist)

    db.flush()
    validate_relations(db)
    db.commit()
    return created


def _seed_appointments(db: Session, clinic: Clinic, doctors: list, author: User) -> int:
    """Agenda demo de la clínica, solo si todavía no tiene citas.

    Pasadas: atendidas y algunas «No asistió». Futuras: programadas, algunas
    confirmadas y algunas canceladas. Siempre son de pacientes de la clínica."""
    if db.query(Appointment.id).filter(Appointment.clinic_id == clinic.id).first():
        return 0

    patients = (
        db.query(Patient)
        .filter(Patient.clinic_id == clinic.id, Patient.archived_at.is_(None))
        .order_by(Patient.id)
        .all()
    )
    if not patients or not doctors:
        return 0

    rng = random.Random(f"agenda-{clinic.name}")
    today = date.today()
    now = datetime.now(timezone.utc)
    count = 0
    for offset in APPOINTMENT_DAYS:
        day = today + timedelta(days=offset)
        if day.weekday() >= 5:  # sábado y domingo sin citas
            continue
        for doctor_index, doctor in enumerate(doctors):
            for hour in DOCTOR_HOURS[doctor_index % len(DOCTOR_HOURS)]:
                starts_at = datetime.combine(day, time(hour, rng.choice((0, 30))), CLINIC_TZ)
                if starts_at > now:
                    roll = rng.random()
                    status = "cancelled" if roll < 0.1 else "confirmed" if roll < 0.4 else "scheduled"
                else:
                    status = "no_show" if rng.random() < 0.15 else "completed"
                appointment = Appointment(
                    clinic_id=clinic.id,
                    patient_id=patients[count % len(patients)].id,
                    doctor_id=doctor.id,
                    starts_at=starts_at,
                    duration_minutes=rng.choice((30, 45, 60)),
                    status=status,
                    reason=rng.choice(APPOINTMENT_REASONS),
                    created_by_user_id=author.id,
                )
                # Historial mínimo (ODON-146): un registro con el estado demo.
                appointment.status_changes.append(
                    AppointmentStatusChange(
                        clinic_id=clinic.id,
                        to_status=status,
                        note="Agenda demo del seed",
                        changed_by_user_id=author.id,
                    )
                )
                db.add(appointment)
                count += 1
    return count


def validate_relations(db: Session) -> None:
    """Comprueba que todos los registros demo pertenezcan a su propia clínica."""
    names = [spec["name"] for spec in CLINICS]
    clinics = db.query(Clinic).filter(Clinic.name.in_(names)).all()
    if len(clinics) != len(CLINICS):
        raise SeedError("Faltan clínicas de demostración tras el seed.")

    for clinic in clinics:
        for doctor in db.query(Doctor).filter(Doctor.clinic_id == clinic.id):
            if doctor.user.clinic_id != clinic.id:
                raise SeedError(
                    f"El doctor {doctor.id} y su usuario pertenecen a clínicas distintas."
                )
        for patient in db.query(Patient).filter(Patient.clinic_id == clinic.id):
            if patient.doctor is not None and patient.doctor.clinic_id != clinic.id:
                raise SeedError(
                    f"El paciente {patient.id} tiene un doctor de otra clínica."
                )


def main() -> int:
    from app.database.connection import DATABASE_URL, SessionLocal

    try:
        ensure_development(DATABASE_URL, os.getenv("APP_ENV", "development"))
        password = read_password(os.getenv("SEED_PASSWORD"))
    except SeedError as exc:
        print(f"Error: {exc}")
        return 2

    db = SessionLocal()
    try:
        created = seed(db, password)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "Seed completado. Registros nuevos:",
        ", ".join(f"{k}={v}" for k, v in created.items()),
    )
    print("Usuarios de demostración (contraseña: la de SEED_PASSWORD):")
    for spec in CLINICS:
        for prefix, _, role, _ in STAFF:
            print(
                f"  {spec['name']:<20} {role:<13} {staff_email(prefix, spec['slug'])}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
