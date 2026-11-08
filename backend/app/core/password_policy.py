"""Política de contraseñas (ODON-230).

Siguiendo NIST SP 800-63B: longitud mínima de 10 caracteres, rechazo de
contraseñas conocidas por filtraciones y sin reglas de composición
(mayúsculas, símbolos) ni caducidad periódica. Se aplica al crear una
contraseña nueva; las existentes siguen sirviendo hasta su próximo cambio.
"""
from functools import lru_cache
from pathlib import Path

MIN_LENGTH = 10
MAX_LENGTH = 128

_COMMON_FILE = Path(__file__).with_name("common_passwords.txt")


@lru_cache(maxsize=1)
def common_passwords() -> frozenset[str]:
    lines = _COMMON_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line for line in lines if line and not line.startswith("#"))


def check_new_password(password: str) -> str:
    """Valida una contraseña nueva (validador de Pydantic). La longitud la
    revisa el tipo del campo; aquí, las contraseñas comunes."""
    if password.strip().lower() in common_passwords():
        raise ValueError("Esa contraseña aparece en listas de contraseñas filtradas. Elige otra.")
    return password
