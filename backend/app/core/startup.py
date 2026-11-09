"""Comprobaciones al arrancar en producción (ODON-234)."""
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection, Engine

from app.core.settings import BACKEND_DIR


def expected_revision() -> str | None:
    """Última migración incluida en el código."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def current_revision(connection: Connection) -> str | None:
    """Última migración aplicada a la base."""
    return MigrationContext.configure(connection).get_current_revision()


def ensure_schema_current(engine: Engine) -> None:
    """Las migraciones se aplican solo con el procedimiento de despliegue, que
    respalda antes. La API nunca migra sola: si la base no está al día, no arranca."""
    expected = expected_revision()
    with engine.connect() as connection:
        current = current_revision(connection)
    if current != expected:
        raise RuntimeError(
            f"La base está en la migración {current} y el código espera {expected}. "
            "Aplica el procedimiento de despliegue (docs/DEPLOYMENT.md)."
        )
