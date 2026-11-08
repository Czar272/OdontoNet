"""Formato único de errores de la API.

Toda respuesta de error es JSON con la forma:

    {"detail": "<mensaje en español para mostrar al usuario>"}

Los errores de validación (422) agregan la lista de campos:

    {"detail": "Revisa los campos: email.",
     "errors": [{"field": "email", "message": "Correo electrónico inválido."}]}

Los errores 500 nunca exponen trazas ni detalles internos.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_core import PydanticCustomError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("odontonet.api")

# Mensajes por defecto de Starlette/FastAPI traducidos al español.
_DEFAULT_DETAILS = {
    "Not Found": "Recurso no encontrado.",
    "Method Not Allowed": "Método no permitido.",
    "Not authenticated": "No autenticado.",
}

_VALIDATION_MESSAGES = {
    "missing": "Campo obligatorio.",
    "date_parsing": "Fecha inválida.",
    "date_from_datetime_parsing": "Fecha inválida.",
    "date_from_datetime_inexact": "Fecha inválida.",
    "date_type": "Fecha inválida.",
    "int_parsing": "Debe ser un número entero.",
    "int_type": "Debe ser un número entero.",
    "int_from_float": "Debe ser un número entero.",
    "enum": "Valor no permitido.",
    "bool_parsing": "Debe ser verdadero o falso.",
    "bool_type": "Debe ser verdadero o falso.",
    "json_invalid": "El cuerpo de la petición no es JSON válido.",
}

# Pydantic antepone este prefijo al mensaje de los ValueError de los validadores propios.
_VALUE_ERROR_PREFIX = "Value error, "
_EMAIL_ERROR_PREFIX = "value is not a valid email address"

# Tipo de error de los validadores de modelo (validan varios campos a la vez).
# Se informan con el campo "__root__", como antes de Pydantic 2.
ROOT_ERROR_TYPE = "root_value_error"


def root_error(message: str) -> PydanticCustomError:
    """Error de un validador de modelo con su mensaje en español."""
    return PydanticCustomError(ROOT_ERROR_TYPE, message)


def _validation_message(error: dict) -> str:
    error_type = error.get("type", "")
    ctx = error.get("ctx") or {}

    # null en un campo que no lo admite.
    if error.get("input", ...) is None and error_type not in ("value_error", ROOT_ERROR_TYPE):
        return "Campo obligatorio."
    if error_type == "string_too_short":
        limit = ctx.get("min_length", 1)
        return "Campo obligatorio." if limit == 1 else f"Debe tener al menos {limit} caracteres."
    if error_type == "string_too_long":
        return f"Debe tener como máximo {ctx.get('max_length')} caracteres."
    if error_type == "greater_than_equal":
        return f"Debe ser mayor o igual a {ctx.get('ge')}."
    if error_type == "less_than_equal":
        return f"Debe ser menor o igual a {ctx.get('le')}."
    if error_type in _VALIDATION_MESSAGES:
        return _VALIDATION_MESSAGES[error_type]
    if error_type == "value_error":
        message = error.get("msg") or "Valor inválido."
        if message.startswith(_EMAIL_ERROR_PREFIX):
            return "Correo electrónico inválido."
        # Validadores propios: su mensaje ya está en español.
        return message.removeprefix(_VALUE_ERROR_PREFIX)
    if error_type == ROOT_ERROR_TYPE:
        return error.get("msg") or "Valor inválido."
    return "Valor inválido."


def _field_name(error: dict) -> str:
    loc = tuple(error.get("loc", ()))
    # JSON mal formado: el loc trae la posición del error, no un campo.
    if error.get("type") == "json_invalid":
        return "body"
    if error.get("type") == ROOT_ERROR_TYPE:
        loc += ("__root__",)
    parts = [str(part) for part in loc if part not in ("body", "query", "path", "header")]
    return ".".join(parts) or "body"


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, str):
        detail = _DEFAULT_DETAILS.get(detail, detail)
    content = {"detail": detail}
    # Datos adicionales opcionales para la interfaz (p. ej. la cita con la que
    # choca un horario, ODON-134). Nunca sustituyen a "detail".
    content.update(getattr(exc, "extra", None) or {})
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": _field_name(error), "message": _validation_message(error)}
        for error in exc.errors()
    ]
    fields = ", ".join(dict.fromkeys(error["field"] for error in errors))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": f"Revisa los campos: {fields}.", "errors": errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
