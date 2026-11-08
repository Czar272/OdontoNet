"""Tipos compartidos por los esquemas."""
from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema

# Fecha y hora en JSON con datetime.isoformat(): UTC sale como "+00:00", el
# formato que la API ha devuelto siempre (Pydantic 2 usaría "Z").
# WithJsonSchema conserva "format: date-time" en el OpenAPI de las respuestas.
DateTime = Annotated[
    datetime,
    PlainSerializer(lambda value: value.isoformat(), return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time"}, mode="serialization"),
]
