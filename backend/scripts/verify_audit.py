"""Verifica la integridad de la auditoría (ODON-222).

Recalcula la cadena de hashes de audit_events de cada clínica y reporta los
eventos alterados o desenlazados. Solo lectura. Uso, desde backend/:

    python -m scripts.verify_audit

Sale con código 1 si encuentra problemas. No detecta que se hayan borrado los
eventos más recientes de una clínica (la cola de la cadena): para eso, comparar
el último id con un respaldo (ODON-226).
"""
import sys

from sqlalchemy import select

from app.database.connection import SessionLocal
from app.models.audit_event import AuditEvent
from app.services.audit_service import verify_chain


def main() -> int:
    with SessionLocal() as db:
        clinics = db.execute(select(AuditEvent.clinic_id).distinct().order_by(AuditEvent.clinic_id)).scalars().all()
        total_problems = 0
        for clinic_id in clinics:
            count = db.query(AuditEvent).filter(AuditEvent.clinic_id == clinic_id).count()
            problems = verify_chain(db, clinic_id)
            total_problems += len(problems)
            status = "íntegra" if not problems else f"{len(problems)} problemas"
            print(f"Clínica {clinic_id}: {count} eventos, cadena {status}")
            for problem in problems:
                print(f"  - {problem}")
        if not clinics:
            print("Sin eventos de auditoría.")
    return 1 if total_problems else 0


if __name__ == "__main__":
    sys.exit(main())
