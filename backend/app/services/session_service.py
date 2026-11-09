"""Sesiones con refresh token rotativo (ODON-265).

El refresh token vive en una cookie httpOnly y cambia en cada renovación. Si un
token ya usado reaparece, alguien lo copió: se revoca toda la familia. Hay una
excepción de `REUSE_GRACE`: dos pestañas pueden renovar a la vez con la misma
cookie; la segunda recibe un token de acceso, sin rotar, y conserva la cookie
que dejó la primera.

Toda operación que crea o revoca tokens de un usuario toma primero un bloqueo
por usuario: sin él, una rotación en curso crearía un token nuevo que la
revocación concurrente no alcanza a ver.
"""
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, exists, select, text, update
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.auth_session import AuthSession
from app.models.user import User

audit_logger = logging.getLogger("odontonet.audit")

REUSE_GRACE = timedelta(seconds=10)
_LOCK_NAMESPACE = 2650
# Las filas vencidas se conservan un día por si hay que revisar un incidente.
RETENTION = timedelta(days=1)


@dataclass(frozen=True)
class IssuedSession:
    user: User
    family_id: str
    remember_me: bool
    expires_at: datetime
    # None: renovación concurrente; la cookie vigente no cambia.
    refresh_token: Optional[str]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _lock_user(db: Session, user_id: int) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(:ns, :user_id)"), {"ns": _LOCK_NAMESPACE, "user_id": user_id})


def _locked_row(db: Session, token: str) -> Optional[AuthSession]:
    """Fila del token, leída de nuevo después de tomar el bloqueo de su usuario."""
    token_hash = _hash(token)
    user_id = db.execute(select(AuthSession.user_id).where(AuthSession.token_hash == token_hash)).scalar_one_or_none()
    if user_id is None:
        return None
    _lock_user(db, user_id)
    return db.execute(
        select(AuthSession).where(AuthSession.token_hash == token_hash).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _lifetime(remember_me: bool) -> timedelta:
    settings = get_settings()
    if remember_me:
        return timedelta(days=settings.remember_me_expire_days)
    return timedelta(hours=settings.session_expire_hours)


def _add_token(db: Session, user: User, family_id: str, remember_me: bool, expires_at: datetime) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(
        user_id=user.id, clinic_id=user.clinic_id, family_id=family_id,
        token_hash=_hash(token), remember_me=remember_me, expires_at=expires_at,
    ))
    return token


def start(db: Session, user: User, remember_me: bool) -> IssuedSession:
    """Abre una sesión nueva y depura las vencidas."""
    now = _now()
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now - RETENTION))
    family_id = str(uuid.uuid4())
    expires_at = now + _lifetime(remember_me)
    token = _add_token(db, user, family_id, remember_me, expires_at)
    db.commit()
    return IssuedSession(user, family_id, remember_me, expires_at, token)


def _revoke_family(db: Session, family_id: str, now: datetime) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def rotate(db: Session, token: str) -> Optional[IssuedSession]:
    """Cambia el refresh token por uno nuevo. None si la sesión no es válida."""
    row = _locked_row(db, token)
    now = _now()
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        return None

    user = db.get(User, row.user_id)
    if user is None or user.is_active is False:
        _revoke_family(db, row.family_id, now)
        db.commit()
        return None

    if row.used_at is not None:
        if now - row.used_at <= REUSE_GRACE:
            return IssuedSession(user, row.family_id, row.remember_me, row.expires_at, None)
        _revoke_family(db, row.family_id, now)
        db.commit()
        audit_logger.warning("auth.session_reuse_detected user_id=%s clinic_id=%s", row.user_id, row.clinic_id)
        return None

    row.used_at = now
    new_token = _add_token(db, user, row.family_id, row.remember_me, row.expires_at)
    db.commit()
    return IssuedSession(user, row.family_id, row.remember_me, row.expires_at, new_token)


def remember_me_of(db: Session, token: Optional[str]) -> Optional[bool]:
    """«Recuérdame» de la sesión de esa cookie; None si no se conoce."""
    if not token:
        return None
    return db.execute(select(AuthSession.remember_me).where(AuthSession.token_hash == _hash(token))).scalar_one_or_none()


def end(db: Session, token: Optional[str]) -> None:
    """Cierra la sesión de la cookie. Sin cookie o desconocida, no hace nada."""
    if not token:
        return
    row = _locked_row(db, token)
    if row is not None:
        _revoke_family(db, row.family_id, _now())
        db.commit()


def revoke_user_sessions(db: Session, user_id: int) -> None:
    """Revoca todas las sesiones del usuario, sin commit: lo hace la operación."""
    _lock_user(db, user_id)
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def family_is_active(db: Session, family_id: str, user_id: int) -> bool:
    """Un token de acceso solo vale mientras la sesión de ese usuario siga abierta."""
    return db.scalar(select(exists().where(
        AuthSession.family_id == family_id, AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
    )))
