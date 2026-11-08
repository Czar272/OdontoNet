"""Recuperación y cambio de contraseña (ODON-54).

- La solicitud de recuperación responde siempre lo mismo, exista o no la
  cuenta, y el correo se envía en segundo plano.
- El enlace lleva un token aleatorio de un solo uso que expira; en la base
  solo se guarda su hash.
- Cambiar o restablecer la contraseña fija users.password_changed_at: los
  tokens de sesión emitidos antes dejan de valer (ver get_current_user).
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services import audit_service

audit_logger = logging.getLogger("odontonet.audit")

INVALID_LINK = "El enlace no es válido o ya expiró. Solicita uno nuevo."


def reset_expire_minutes() -> int:
    return int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))


def reset_max_per_hour() -> int:
    return int(os.getenv("PASSWORD_RESET_MAX_PER_HOUR", "3"))


def frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _invalidate_open_tokens(db: Session, user_id: int, now: datetime) -> None:
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)


def _mark_password_changed(user: User, new_password: str, now: datetime) -> None:
    user.hashed_password = hash_password(new_password)
    user.password_changed_at = now


def request_reset(db: Session, email: str) -> Optional[tuple[str, str]]:
    """Crea un enlace de recuperación si corresponde.

    Devuelve (correo, enlace) para enviarlo, o None si la cuenta no existe,
    está inactiva o superó el límite de solicitudes por hora. El llamador
    responde lo mismo en todos los casos."""
    user = db.query(User).filter(User.email == email).first()
    if user is None or user.is_active is False:
        audit_logger.info("auth.password_reset_requested user_id=- result=ignored")
        return None

    now = _now()
    recent = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at > now - timedelta(hours=1),
        )
        .count()
    )
    if recent >= reset_max_per_hour():
        audit_logger.info("auth.password_reset_requested user_id=%s result=throttled", user.id)
        return None

    # Solo vale el último enlace solicitado.
    _invalidate_open_tokens(db, user.id, now)

    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(token),
            expires_at=now + timedelta(minutes=reset_expire_minutes()),
        )
    )
    db.commit()
    audit_logger.info("auth.password_reset_requested user_id=%s result=sent", user.id)

    return user.email, f"{frontend_url()}/reset-password?token={token}"


def reset_email_body(link: str) -> str:
    return (
        "Hola:\n\n"
        "Recibimos una solicitud para restablecer tu contraseña de OdontoNet.\n"
        f"Abre este enlace para elegir una nueva (vence en {reset_expire_minutes()} minutos "
        "y solo funciona una vez):\n\n"
        f"{link}\n\n"
        "Si no lo solicitaste, ignora este correo: tu contraseña no cambia.\n"
    )


def confirm_reset(db: Session, token: str, new_password: str) -> User:
    now = _now()
    reset = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_reset_token(token))
        .with_for_update()
        .first()
    )
    if reset is None or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_LINK)

    user = db.query(User).filter(User.id == reset.user_id).with_for_update().first()
    if user is None or user.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_LINK)

    _mark_password_changed(user, new_password, now)
    _invalidate_open_tokens(db, user.id, now)
    # El actor es el propio usuario (no hay sesión): su clínica (ODON-222).
    audit_service.record(
        db, user, "auth.password_reset_completed", "user", user.id, fields=["password"], clinic_id=user.clinic_id,
    )
    db.commit()
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> User:
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta.")
    if verify_password(new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser distinta de la actual.",
        )

    now = _now()
    _mark_password_changed(user, new_password, now)
    _invalidate_open_tokens(db, user.id, now)
    audit_service.record(db, user, "auth.password_changed", "user", user.id, fields=["password"])
    db.commit()
    db.refresh(user)
    return user


def set_password_by_admin(db: Session, user: User, new_password: str) -> None:
    """Restablecimiento por administración (PATCH /users): cierra las sesiones
    del usuario y anula sus enlaces pendientes. No hace commit."""
    now = _now()
    _mark_password_changed(user, new_password, now)
    _invalidate_open_tokens(db, user.id, now)
