"""Periodontograma manual (ODON-9).

Un examen periodontal (periodontal_exams) se registra en una fecha y nace como
borrador; al finalizarlo queda inmutable. Sus mediciones se guardan
normalizadas: una fila por pieza (periodontal_teeth) y una por sitio
(periodontal_sites), siempre las 32 piezas permanentes y 6 sitios por pieza.
Cada guardado copia el examen completo en periodontal_exam_revisions.

Convención del margen gingival (la de la herramienta de referencia): distancia
del margen a la unión amelocementaria, negativa si hay recesión y positiva si
hay agrandamiento. El nivel de inserción clínica no se guarda: se calcula como
profundidad de sondaje − margen gingival.

Cada medición lleva source = 'manual'. Cuando exista el servicio de IA, sus
sugerencias se distinguirán por este campo y nunca reemplazarán una medición
clínica sin revisión profesional.
"""
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database.connection import Base

# Dentición permanente FDI, en el orden en que se dibuja: superior de 18 a 28,
# inferior de 48 a 38 (vista del clínico frente al paciente).
UPPER_TEETH = (18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28)
LOWER_TEETH = (48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38)
PERMANENT_TEETH = UPPER_TEETH + LOWER_TEETH

# Sitios: mesio/centro/disto, por vestibular (b) y por palatino o lingual (l).
SITES = ("mb", "b", "db", "ml", "l", "dl")

# Entradas de furcación por molar: superiores vestibular, mesiopalatina y
# distopalatina; inferiores vestibular y lingual.
UPPER_MOLARS = (16, 17, 18, 26, 27, 28)
LOWER_MOLARS = (36, 37, 38, 46, 47, 48)
FURCATION_ENTRANCES = {
    **{tooth: ("b", "mp", "dp") for tooth in UPPER_MOLARS},
    **{tooth: ("b", "l") for tooth in LOWER_MOLARS},
}

PROBING_DEPTH_RANGE = (0, 15)
GINGIVAL_MARGIN_RANGE = (-15, 5)
MOBILITY_RANGE = (0, 3)
FURCATION_RANGE = (1, 3)

EXAM_STATUSES = ("draft", "final")
SOURCES = ("manual",)

_TEETH_SQL = ", ".join(str(tooth) for tooth in PERMANENT_TEETH)
_SITES_SQL = ", ".join(f"'{site}'" for site in SITES)
_UPPER_MOLARS_SQL = ", ".join(str(tooth) for tooth in UPPER_MOLARS)
_LOWER_MOLARS_SQL = ", ".join(str(tooth) for tooth in LOWER_MOLARS)
_SOURCES_SQL = ", ".join(f"'{source}'" for source in SOURCES)


def _between(column: str, bounds: tuple[int, int]) -> str:
    return f"{column} IS NULL OR {column} BETWEEN {bounds[0]} AND {bounds[1]}"


class PeriodontalExam(Base):
    __tablename__ = "periodontal_exams"
    __table_args__ = (
        UniqueConstraint("id", "clinic_id", name="uq_periodontal_exams_id_clinic"),
        ForeignKeyConstraint(
            ["patient_id", "clinic_id"], ["patients.id", "patients.clinic_id"],
            name="fk_periodontal_exams_patient_clinic",
        ),
        ForeignKeyConstraint(
            ["clinical_visit_id", "clinic_id"], ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_periodontal_exams_visit_clinic",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_periodontal_exams_author_clinic",
        ),
        ForeignKeyConstraint(
            ["finalized_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_periodontal_exams_finalizer_clinic",
        ),
        ForeignKeyConstraint(
            ["voided_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_periodontal_exams_voider_clinic",
        ),
        CheckConstraint("status IN ('draft', 'final')", name="ck_periodontal_exams_status"),
        CheckConstraint("revision >= 1", name="ck_periodontal_exams_revision"),
        # Finalizado: estado, fecha y autor van juntos.
        CheckConstraint(
            "(status = 'draft' AND finalized_at IS NULL AND finalized_by_user_id IS NULL) OR "
            "(status = 'final' AND finalized_at IS NOT NULL AND finalized_by_user_id IS NOT NULL)",
            name="ck_periodontal_exams_final",
        ),
        CheckConstraint(
            "(voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR "
            "(voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_periodontal_exams_void",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    clinical_visit_id = Column(Integer, ForeignKey("clinical_visits.id"))
    exam_date = Column(Date, nullable=False)
    notes = Column(Text)

    status = Column(String(10), nullable=False, server_default="draft")
    revision = Column(Integer, nullable=False, server_default="1")
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finalized_at = Column(DateTime(timezone=True))
    finalized_by_user_id = Column(Integer, ForeignKey("users.id"))
    voided_at = Column(DateTime(timezone=True))
    voided_by_user_id = Column(Integer, ForeignKey("users.id"))
    void_reason = Column(Text)

    clinical_visit = relationship("ClinicalVisit", foreign_keys=[clinical_visit_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    finalized_by = relationship("User", foreign_keys=[finalized_by_user_id])
    voided_by = relationship("User", foreign_keys=[voided_by_user_id])
    teeth = relationship(
        "PeriodontalTooth", foreign_keys="PeriodontalTooth.exam_id", order_by="PeriodontalTooth.tooth",
        passive_deletes="all",
    )
    sites = relationship(
        "PeriodontalSite", foreign_keys="PeriodontalSite.exam_id",
        passive_deletes="all",
    )


class PeriodontalTooth(Base):
    __tablename__ = "periodontal_teeth"
    __table_args__ = (
        UniqueConstraint("exam_id", "tooth", name="uq_periodontal_teeth_exam_tooth"),
        ForeignKeyConstraint(
            ["exam_id", "clinic_id"], ["periodontal_exams.id", "periodontal_exams.clinic_id"],
            name="fk_periodontal_teeth_exam_clinic",
        ),
        CheckConstraint(f"tooth IN ({_TEETH_SQL})", name="ck_periodontal_teeth_tooth"),
        CheckConstraint("NOT (missing AND implant)", name="ck_periodontal_teeth_missing_implant"),
        # Una pieza ausente no lleva movilidad ni furcación; un implante, furcación.
        # (Que una pieza ausente no tenga mediciones por sitio abarca dos tablas:
        # lo valida el servicio.)
        CheckConstraint(
            "NOT missing OR (mobility IS NULL AND furcation_b IS NULL AND furcation_mp IS NULL AND furcation_dp IS NULL AND furcation_l IS NULL)",
            name="ck_periodontal_teeth_missing_values",
        ),
        CheckConstraint(
            "NOT implant OR (furcation_b IS NULL AND furcation_mp IS NULL AND furcation_dp IS NULL AND furcation_l IS NULL)",
            name="ck_periodontal_teeth_implant_furcation",
        ),
        CheckConstraint(_between("mobility", MOBILITY_RANGE), name="ck_periodontal_teeth_mobility"),
        # Furcación solo en las entradas que existen en cada molar.
        CheckConstraint(
            f"{_between('furcation_b', FURCATION_RANGE)}", name="ck_periodontal_teeth_furcation_b_range"
        ),
        CheckConstraint(
            f"furcation_b IS NULL OR tooth IN ({_UPPER_MOLARS_SQL}, {_LOWER_MOLARS_SQL})",
            name="ck_periodontal_teeth_furcation_b_tooth",
        ),
        CheckConstraint(
            f"({_between('furcation_mp', FURCATION_RANGE)}) AND "
            f"(furcation_mp IS NULL OR tooth IN ({_UPPER_MOLARS_SQL}))",
            name="ck_periodontal_teeth_furcation_mp",
        ),
        CheckConstraint(
            f"({_between('furcation_dp', FURCATION_RANGE)}) AND "
            f"(furcation_dp IS NULL OR tooth IN ({_UPPER_MOLARS_SQL}))",
            name="ck_periodontal_teeth_furcation_dp",
        ),
        CheckConstraint(
            f"({_between('furcation_l', FURCATION_RANGE)}) AND "
            f"(furcation_l IS NULL OR tooth IN ({_LOWER_MOLARS_SQL}))",
            name="ck_periodontal_teeth_furcation_l",
        ),
        CheckConstraint(f"source IN ({_SOURCES_SQL})", name="ck_periodontal_teeth_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("periodontal_exams.id"), nullable=False, index=True)
    tooth = Column(SmallInteger, nullable=False)
    missing = Column(Boolean, nullable=False, server_default="false")
    implant = Column(Boolean, nullable=False, server_default="false")
    mobility = Column(SmallInteger)
    furcation_b = Column(SmallInteger)
    furcation_mp = Column(SmallInteger)
    furcation_dp = Column(SmallInteger)
    furcation_l = Column(SmallInteger)
    note = Column(Text)
    source = Column(String(10), nullable=False, server_default="manual")


class PeriodontalSite(Base):
    __tablename__ = "periodontal_sites"
    __table_args__ = (
        UniqueConstraint("exam_id", "tooth", "site", name="uq_periodontal_sites_exam_tooth_site"),
        ForeignKeyConstraint(
            ["exam_id", "clinic_id"], ["periodontal_exams.id", "periodontal_exams.clinic_id"],
            name="fk_periodontal_sites_exam_clinic",
        ),
        CheckConstraint(f"tooth IN ({_TEETH_SQL})", name="ck_periodontal_sites_tooth"),
        CheckConstraint(f"site IN ({_SITES_SQL})", name="ck_periodontal_sites_site"),
        CheckConstraint(_between("probing_depth", PROBING_DEPTH_RANGE), name="ck_periodontal_sites_probing_depth"),
        CheckConstraint(
            _between("gingival_margin", GINGIVAL_MARGIN_RANGE), name="ck_periodontal_sites_gingival_margin"
        ),
        CheckConstraint(f"source IN ({_SOURCES_SQL})", name="ck_periodontal_sites_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("periodontal_exams.id"), nullable=False, index=True)
    tooth = Column(SmallInteger, nullable=False)
    site = Column(String(2), nullable=False)
    probing_depth = Column(SmallInteger)
    gingival_margin = Column(SmallInteger)
    bleeding = Column(Boolean, nullable=False, server_default="false")
    suppuration = Column(Boolean, nullable=False, server_default="false")
    plaque = Column(Boolean, nullable=False, server_default="false")
    source = Column(String(10), nullable=False, server_default="manual")


class PeriodontalExamRevision(Base):
    """Copia completa del examen (cabecera y mediciones) en cada guardado."""

    __tablename__ = "periodontal_exam_revisions"
    __table_args__ = (
        UniqueConstraint("exam_id", "revision", name="uq_periodontal_revisions_exam_revision"),
        ForeignKeyConstraint(
            ["exam_id", "clinic_id"], ["periodontal_exams.id", "periodontal_exams.clinic_id"],
            name="fk_periodontal_revisions_exam_clinic",
        ),
        ForeignKeyConstraint(
            ["edited_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_periodontal_revisions_editor_clinic",
        ),
        CheckConstraint("revision >= 1", name="ck_periodontal_revisions_revision"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("periodontal_exams.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    data = Column(JSONB, nullable=False)
    edited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    edited_by = relationship("User", foreign_keys=[edited_by_user_id])
