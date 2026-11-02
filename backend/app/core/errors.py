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
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("odontonet.api")

# Mensajes por defecto de Starlette/FastAPI traducidos al español.
_DEFAULT_DETAILS = {
    "Not Found": "Recurso no encontrado.",
    "Method Not Allowed": "Método no permitido.",
    "Not authenticated": "No autenticado.",
}

_VALIDATION_MESSAGES = {
    "value_error.missing": "Campo obligatorio.",
    "value_error.email": "Correo electrónico inválido.",
    "value_error.date": "Fecha inválida.",
    "type_error.date": "Fecha inválida.",
    "type_error.integer": "Debe ser un número entero.",
    "type_error.enum": "Valor no permitido.",
    "type_error.bool": "Debe ser verdadero o falso.",
    "type_error.none.not_allowed": "Campo obligatorio.",
    "value_error.jsondecode": "El cuerpo de la petición no es JSON válido.",
}


def _validation_message(error: dict) -> str:
    error_type = error.get("type", "")
    ctx = error.get("ctx") or {}

    if error_type == "value_error.any_str.min_length":
        limit = ctx.get("limit_value", 1)
        return "Campo obligatorio." if limit == 1 else f"Debe tener al menos {limit} caracteres."
    if error_type == "value_error.any_str.max_length":
        return f"Debe tener como máximo {ctx.get('limit_value')} caracteres."
    if error_type == "value_error.number.not_ge":
        return f"Debe ser mayor o igual a {ctx.get('limit_value')}."
    if error_type == "value_error.number.not_le":
        return f"Debe ser menor o igual a {ctx.get('limit_value')}."
    if error_type in _VALIDATION_MESSAGES:
        return _VALIDATION_MESSAGES[error_type]
    if error_type == "value_error":
        # Validadores propios: su mensaje ya está en español.
        return error.get("msg", "Valor inválido.")
    return "Valor inválido."


def _field_name(loc) -> str:
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
        {"field": _field_name(error.get("loc", ())), "message": _validation_message(error)}
        for error in exc.errors()
    ]
    fields = ", ".join(dict.fromkeys(error["field"] for error in errors))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
