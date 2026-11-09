from sqlalchemy import Boolean, Column, DateTime, ForeignKeyConstraint, Index, Integer, String, func

from app.database.connection import Base


class AuthSession(Base):
    """Refresh token de una sesión (ODON-265).

    Cada renovación crea una fila nueva de la misma familia y marca `used_at` en
    la anterior. Una familia es un inicio de sesión. Solo se guarda el SHA-256
    del token, nunca el token. Dato operativo, no clínico: las filas vencidas se
    depuran solas.
    """

    __tablename__ = "auth_sessions"
    __table_args__ = (
        # El usuario y la clínica de la sesión siempre coinciden.
        ForeignKeyConstraint(
            ["user_id", "clinic_id"], ["users.id", "users.clinic_id"], name="fk_auth_sessions_user_clinic"
        ),
        Index("ix_auth_sessions_family_id", "family_id"),
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    clinic_id = Column(Integer, nullable=False)
    family_id = Column(String(36), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    remember_me = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # Vencimiento absoluto de toda la familia: renovar no alarga la sesión.
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
