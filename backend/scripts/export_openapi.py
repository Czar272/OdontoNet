"""Exporta la especificación de la API a docs/openapi.json (ODON-242).

En producción /docs está apagado: este archivo documenta los endpoints. Una
prueba falla si queda desactualizado.

Uso, desde backend/ con odonto_venv activo:

    python -m scripts.export_openapi
"""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

OUTPUT = BACKEND_DIR.parent / "docs" / "openapi.json"


def render() -> str:
    from app.main import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8", newline="\n")
    print(f"Escrito {OUTPUT}")
