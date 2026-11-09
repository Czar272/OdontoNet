"""Límite de intentos de autenticación (ODON-230).

Inicio de sesión: 7 fallos por cuenta (decisión del desarrollador) o 30 por IP
en 15 minutos bloquean 15 minutos desde el último fallo. Los intentos con una
cuenta inexistente cuentan igual, para no revelar qué correos existen. Un
inicio de sesión correcto borra los fallos de la cuenta.

Recuperación: 10 solicitudes por IP en 15 minutos (el límite por cuenta de
ODON-38 sigue aparte) y 30 confirmaciones con enlace inválido por IP.

Se guarda en PostgreSQL (tabla auth_attempts), sin servicios extra. Contar y
luego insertar no es atómico: con peticiones simultáneas el límite puede
excederse por unas pocas; es aceptable para frenar ataques de fuerza bruta.
"""
import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.auth_attempt import AuthAttempt

audit_logger = logging.getLogger("odontonet.audit")

RETENTION = timedelta(days=1)


@dataclass(frozen=True)
class Limit:
    kind: str
    per_account: Optional[int]
    per_ip: int
    window: timedelta
    lock: timedelta


def login_limit() -> Limit:
    settings = get_settings()
    return Limit(
        kind="login",
        per_account=settings.login_max_failures_per_account,
        per_ip=settings.login_max_failures_per_ip,
        window=timedelta(minutes=settings.login_window_minutes),
        lock=timedelta(minutes=settings.login_lock_minutes),
    )


def reset_request_limit() -> Limit:
    return Limit("password_reset", None, get_settings().password_reset_max_per_ip,
                 timedelta(minutes=15), timedelta(minutes=15))


def reset_confirm_limit() -> Limit:
    return Limit("password_reset_confirm", None, get_settings().password_reset_confirm_max_failures_per_ip,
                 timedelta(minutes=15), timedelta(minutes=15))


def account_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def client_ip(request: Request) -> str:
    """IP del cliente. Por defecto, la del socket. Con TRUST_PROXY_HEADERS=true
    (un único proxy de confianza delante de la API, ODON-12) se usa la última
    entrada de X-Forwarded-For: la que agrega ese proxy. Las anteriores las
    controla el cliente y servirían para evadir el límite."""
    if get_settings().trust_proxy_headers:
        entries = [entry.strip() for entry in request.headers.get("x-forwarded-for", "").split(",") if entry.strip()]
        if entries:
            return entries[-1][:45]
    return (request.client.host if request.client else "desconocida")[:45]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _blocked_for(db: Session, limit: Limit, column, value: str, maximum: int, now: datetime) -> int:
    """Segundos de bloqueo restantes. Hay bloqueo si en algún tramo de `window`
    se juntaron `maximum` intentos; dura `lock` desde el intento que completó
    el tramo. Se revisan los intentos de los últimos window + lock, así el
    bloqueo dura lo indicado aunque los intentos viejos salgan de la ventana."""
    times = db.execute(
        select(AuthAttempt.attempted_at).where(
            AuthAttempt.kind == limit.kind, column == value,
            AuthAttempt.attempted_at > now - limit.window - limit.lock,
        ).order_by(AuthAttempt.attempted_at)
    ).scalars().all()
    locked_until = None
    for index in range(maximum - 1, len(times)):
        if times[index] - times[index - maximum + 1] <= limit.window:
            locked_until = times[index] + limit.lock
    if locked_until is None:
        return 0
    return max(0, math.ceil((locked_until - now).total_seconds()))


def ensure_allowed(db: Session, limit: Limit, ip: str, email: Optional[str] = None) -> None:
    """429 con Retry-After si la cuenta o la IP superaron el límite."""
    now = _now()
    seconds = _blocked_for(db, limit, AuthAttempt.ip, ip, limit.per_ip, now)
    scope = "ip"
    if email is not None and limit.per_account is not None:
        by_account = _blocked_for(db, limit, AuthAttempt.account_key, account_key(email), limit.per_account, now)
        if by_account > seconds:
            seconds, scope = by_account, "account"
    if seconds <= 0:
        return
    audit_logger.info("auth.throttled kind=%s scope=%s", limit.kind, scope)
    minutes = max(1, math.ceil(seconds / 60))
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Demasiados intentos. Espera {minutes} {'minuto' if minutes == 1 else 'minutos'} e intenta de nuevo.",
        headers={"Retry-After": str(seconds)},
    )


def record(db: Session, limit: Limit, ip: str, email: Optional[str] = None) -> None:
    """Guarda un intento que cuenta para el límite y depura los de más de un día."""
    now = _now()
    db.execute(delete(AuthAttempt).where(AuthAttempt.attempted_at < now - RETENTION))
    db.add(AuthAttempt(kind=limit.kind, ip=ip, account_key=account_key(email) if email else None, attempted_at=now))
    db.commit()


def clear_account(db: Session, limit: Limit, email: str) -> None:
    db.execute(delete(AuthAttempt).where(AuthAttempt.kind == limit.kind, AuthAttempt.account_key == account_key(email)))
    db.commit()
