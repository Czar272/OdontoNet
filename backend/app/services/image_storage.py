"""Almacenamiento privado de imágenes clínicas (ODON-166).

Los archivos nunca se publican: no hay carpeta estática ni URL directa. Se leen
solo a través de la API, después de validar clínica y rol. La interfaz
ImageStorage permite cambiar el disco local por un almacenamiento
S3-compatible sin tocar la lógica de negocio.

Las claves son aleatorias y no contienen datos del paciente:
    <clinic_id>/<yyyy>/<mm>/<uuid hex>.<ext>
"""
import os
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_DIR = BACKEND_DIR / "storage" / "images"

KEY_PATTERN = re.compile(r"^[1-9]\d*/\d{4}/\d{2}/[0-9a-f]{32}\.(jpg|png|webp)$")


class StoredImageNotFound(Exception):
    """El registro existe pero su archivo no está en el almacenamiento."""


class InvalidStorageKey(ValueError):
    """Clave con formato inválido o que intenta salir de la carpeta raíz."""


class ImageStorage(ABC):
    @abstractmethod
    def save(self, clinic_id: int, data: bytes, extension: str) -> str:
        """Guarda los bytes y devuelve la clave generada."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Devuelve el contenido o lanza StoredImageNotFound."""

    @abstractmethod
    def discard(self, key: str) -> None:
        """Quita un archivo recién guardado cuyo registro no llegó a la base.

        Solo para deshacer una subida fallida, nunca para borrar imágenes
        registradas (no hay borrado de imágenes clínicas)."""

    @abstractmethod
    def keys(self) -> list[str]:
        """Todas las claves almacenadas (verificación de respaldos)."""


def new_key(clinic_id: int, extension: str) -> str:
    now = datetime.now(timezone.utc)
    key = f"{clinic_id}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}.{extension}"
    validate_key(key)
    return key


def validate_key(key: str) -> None:
    if not KEY_PATTERN.fullmatch(key):
        raise InvalidStorageKey(f"Clave de almacenamiento inválida: {key!r}")


class LocalImageStorage(ImageStorage):
    """Disco local fuera de Git y fuera de cualquier carpeta servida."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise InvalidStorageKey(f"Clave fuera del almacenamiento: {key!r}")
        return path

    def save(self, clinic_id: int, data: bytes, extension: str) -> str:
        key = new_key(clinic_id, extension)
        path = self._path(key)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Escritura atómica: un corte deja un .tmp, nunca una imagen a medias.
        tmp = path.with_name(f".{path.name}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return key

    def read(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StoredImageNotFound(key) from exc

    def discard(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def keys(self) -> list[str]:
        if not self.root.exists():
            return []
        found = []
        for path in self.root.rglob("*"):
            if path.is_file():
                key = path.relative_to(self.root).as_posix()
                if KEY_PATTERN.fullmatch(key):
                    found.append(key)
        return sorted(found)


@lru_cache
def get_image_storage() -> ImageStorage:
    """Dependencia de FastAPI. IMAGE_STORAGE_DIR define la carpeta raíz."""
    return LocalImageStorage(Path(os.getenv("IMAGE_STORAGE_DIR") or DEFAULT_STORAGE_DIR))
