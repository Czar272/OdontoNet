from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String, func

from app.database.connection import Base

KINDS = ("login", "password_reset", "password_reset_confirm")


class AuthAttempt(Base):
    """Intento de autenticación para limitar la tasa (ODON-230).

    Solo se guardan los intentos que cuentan para el límite: inicios de sesión
    fallidos, solicitudes de recuperación y confirmaciones con enlace inválido.
    La cuenta se identifica por el SHA-256 del correo normalizado, nunca por el
    correo. No pertenece a una clínica: ocurre antes de autenticar. Es un dato
    operativo, no clínico: las filas viejas se depuran solas (un día).
    """

    __tablename__ = "auth_attempts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('login', 'password_reset', 'password_reset_confirm')", name="ck_auth_attempts_kind"
        ),
        Index("ix_auth_attempts_account", "kind", "account_key", "attempted_at"),
        Index("ix_auth_attempts_ip", "kind", "ip", "attempted_at"),
    )

    id = Column(Integer, primary_key=True)
    kind = Column(String(30), nullable=False)
    account_key = Column(String(64))
    ip = Column(String(45), nullable=False)
    attempted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
