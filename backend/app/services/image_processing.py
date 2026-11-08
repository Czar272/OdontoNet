"""Validación y saneamiento de fotografías clínicas (ODON-170).

El tipo se determina por el contenido del archivo, no por lo que declare el
navegador. Toda imagen aceptada se recodifica con Pillow: se aplica la
orientación EXIF y se guarda sin metadatos (EXIF con GPS y dispositivo, XMP,
comentarios) ni contenido oculto tras la imagen. Se conserva el perfil de
color. JPEG con calidad 95 y sin submuestreo de color; PNG sin pérdida.

Que una foto no tenga metadatos ni nombre no la hace anónima: el rostro o un
detalle de la boca pueden identificar al paciente.
"""
import io
import warnings
from dataclasses import dataclass
from pathlib import PurePath

from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

# Formato de Pillow → tipo MIME y extensiones aceptadas.
FORMATS = {
    "JPEG": ("image/jpeg", {".jpg", ".jpeg"}),
    "PNG": ("image/png", {".png"}),
    "WEBP": ("image/webp", {".webp"}),
}
# Tope de píxeles para frenar «bombas de descompresión» (archivos pequeños
# que se expanden a gigas en memoria). 50 MP cubre cámaras intraorales y
# celulares actuales.
MAX_PIXELS = 50_000_000

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    content_type: str
    width: int
    height: int


def _unsupported(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail)


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _detect(data: bytes, filename: str) -> str:
    """Formato real del archivo, comprobando que coincida con la extensión."""
    extension = PurePath(filename or "").suffix.lower()
    if not any(extension in exts for _, exts in FORMATS.values()):
        raise _unsupported("Tipo de imagen no permitido. Usa JPEG, PNG o WebP.")
    try:
        # El tope de píxeles se controla abajo con un 422; el aviso de Pillow sobra.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(data))
        with probe:
            fmt = probe.format
            width, height = probe.size
            frames = getattr(probe, "n_frames", 1)
            probe.verify()
    except Image.DecompressionBombError:
        raise _invalid("La imagen tiene demasiados píxeles (máximo 50 megapíxeles).")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise _unsupported("El archivo no es una imagen válida o está dañado.")

    if fmt not in FORMATS:
        raise _unsupported("Tipo de imagen no permitido. Usa JPEG, PNG o WebP.")
    if extension not in FORMATS[fmt][1]:
        raise _unsupported("La extensión del archivo no coincide con su contenido.")
    if frames > 1:
        raise _unsupported("No se aceptan imágenes animadas.")
    if width * height > MAX_PIXELS:
        raise _invalid("La imagen tiene demasiados píxeles (máximo 50 megapíxeles).")
    return fmt


def sanitize_image(data: bytes, filename: str) -> ProcessedImage:
    fmt = _detect(data, filename)
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            icc_profile = source.info.get("icc_profile")
            image = ImageOps.exif_transpose(source)
    except Image.DecompressionBombError:
        raise _invalid("La imagen tiene demasiados píxeles (máximo 50 megapíxeles).")
    except (OSError, SyntaxError, ValueError):
        raise _unsupported("El archivo no es una imagen válida o está dañado.")

    options = {"icc_profile": icc_profile} if icc_profile else {}
    if fmt == "JPEG":
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        options.update(quality=95, subsampling=0, optimize=True)
    elif fmt == "WEBP":
        options.update(quality=95, method=4)

    # Se vacía lo que la imagen trae en memoria (EXIF, XMP, textos PNG) para
    # que ningún metadato del original llegue al archivo guardado.
    image.info = {}
    output = io.BytesIO()
    image.save(output, format=fmt, **options)
    return ProcessedImage(
        data=output.getvalue(),
        content_type=FORMATS[fmt][0],
        width=image.width,
        height=image.height,
    )


# Lado mayor de la miniatura de la galería (ODON-174).
THUMBNAIL_SIZE = 320


def make_thumbnail(data: bytes) -> bytes:
    """Miniatura JPEG de una imagen ya saneada, sin metadatos.

    Las transparencias se aplanan sobre blanco."""
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        image = source.copy()
    image.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        image = background
    elif image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.info = {}
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=80, optimize=True)
    return output.getvalue()
