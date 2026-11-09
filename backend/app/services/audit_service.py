"""Auditoría persistente (ODON-222).

`record()` agrega un evento en la misma transacción que la operación auditada:
si la operación falla y se revierte, el evento también. Un bloqueo de
transacción por clínica (pg_advisory_xact_lock) ordena las escrituras para que
la cadena de hashes no se bifurque con peticiones simultáneas.
"""

import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.user import User

audit_logger = logging.getLogger("odontonet.audit")

_LOCK_NAMESPACE = 7222  # clave fija del bloqueo; la segunda es el id de la clínica
PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def compute_hash(event: AuditEvent) -> str:
    """SHA-256 del contenido del evento y del hash anterior (JSON canónico)."""
    content = [
        event.clinic_id,
        event.actor_user_id,
        event.actor_role,
        event.action,
        event.entity_type,
        event.entity_id,
        event.patient_id,
        event.fields,
        _utc_iso(event.occurred_at),
        event.prev_hash,
    ]
    payload = json.dumps(
        content, separators=(",", ":"), ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record(
    db: Session,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    *,
    patient_id: Optional[int] = None,
    fields: Optional[Iterable[str]] = None,
    clinic_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> AuditEvent:
    """Agrega un evento de auditoría (sin commit: lo hace la operación).

    `fields` lleva solo NOMBRES de campos. `detail` solo se agrega a la línea
    del log (no se guarda) y debe contener únicamente ids, números o códigos de
    estado, p. ej. "from=scheduled to=confirmed"; nunca datos personales.
    """
    clinic = clinic_id if clinic_id is not None else actor.clinic_id
    # Primero se escriben los cambios pendientes (bloquean sus filas) y al final
    # se toma el bloqueo de la clínica: siempre en ese orden, sin interbloqueos.
    db.flush()
    db.execute(
        text("SELECT pg_advisory_xact_lock(:ns, :clinic)"),
        {"ns": _LOCK_NAMESPACE, "clinic": clinic},
    )
    prev_hash = db.execute(
        select(AuditEvent.hash)
        .where(AuditEvent.clinic_id == clinic)
        .order_by(AuditEvent.id.desc())
        .limit(1)
    ).scalar()
    event = AuditEvent(
        clinic_id=clinic,
        actor_user_id=actor.id,
        actor_role=actor.role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        patient_id=patient_id,
        fields=sorted(fields) if fields is not None else None,
        occurred_at=datetime.now(timezone.utc),
        prev_hash=prev_hash,
    )
    event.hash = compute_hash(event)
    db.add(event)
    db.flush()
    message = "%s %s_id=%s user_id=%s clinic_id=%s"
    args = [action, entity_type, entity_id, actor.id, clinic]
    if detail:
        message += " %s"
        args.append(detail)
    audit_logger.info(message, *args)
    return event


def verify_chain(db: Session, clinic_id: int) -> list[str]:
    """Problemas de la cadena de una clínica (vacía si está íntegra)."""
    problems = []
    previous = None
    for event in db.execute(
        select(AuditEvent)
        .where(AuditEvent.clinic_id == clinic_id)
        .order_by(AuditEvent.id)
    ).scalars():
        if event.prev_hash != previous:
            problems.append(f"evento {event.id}: no enlaza con el anterior")
        if compute_hash(event) != event.hash:
            problems.append(f"evento {event.id}: el contenido no coincide con su hash")
        previous = event.hash
    return problems


# --- Consulta -------------------------------------------------------------------


def _encode_cursor(event_id: int) -> str:
    return base64.urlsafe_b64encode(str(event_id).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Cursor inválido."
        )


def list_events(
    db: Session,
    clinic_id: int,
    *,
    actor_user_id: Optional[int] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    patient_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    cursor: Optional[str] = None,
    limit: int = PAGE_SIZE,
) -> dict:
    """Eventos de la clínica, del más reciente al más antiguo, por páginas."""
    query = (
        select(AuditEvent, User.name)
        .join(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.clinic_id == clinic_id)
    )
    if actor_user_id is not None:
        query = query.where(AuditEvent.actor_user_id == actor_user_id)
    if action:
        query = query.where(AuditEvent.action == action)
    if entity_type:
        query = query.where(AuditEvent.entity_type == entity_type)
    if patient_id is not None:
        query = query.where(AuditEvent.patient_id == patient_id)
    if date_from is not None:
        query = query.where(AuditEvent.occurred_at >= date_from)
    if date_to is not None:
        query = query.where(AuditEvent.occurred_at < date_to)
    if cursor:
        query = query.where(AuditEvent.id < _decode_cursor(cursor))
    rows = db.execute(query.order_by(AuditEvent.id.desc()).limit(limit + 1)).all()
    items = [
        {
            "id": event.id,
            "occurred_at": event.occurred_at,
            "actor": {
                "id": event.actor_user_id,
                "name": name,
                "role": event.actor_role,
            },
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "patient_id": event.patient_id,
            "fields": event.fields or [],
        }
        for event, name in rows[:limit]
    ]
    next_cursor = _encode_cursor(rows[limit - 1][0].id) if len(rows) > limit else None
    return {"items": items, "next_cursor": next_cursor}


def actions_in_use(db: Session, clinic_id: int) -> list[str]:
    return list(
        db.execute(
            select(AuditEvent.action)
            .where(AuditEvent.clinic_id == clinic_id)
            .group_by(AuditEvent.action)
            .order_by(func.min(AuditEvent.action))
        ).scalars()
    )
