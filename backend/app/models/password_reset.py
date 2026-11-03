from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.database.connection import Base


class PasswordResetToken(Base):
    """Enlace de recuperación de contraseña (ODON-54).

    Solo se guarda el hash SHA-256 del token que viaja en el enlace. Un token
    vale una sola vez: used_at se llena al usarlo o al quedar reemplazado por
    una solicitud nueva o por un cambio de contraseña."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
