import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
import jwt
from jwt import InvalidTokenError

# Ruta absoluta al directorio backend/ (no depende del directorio de ejecución)
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
# PyJWT (ODON-263; antes python-jose, sin corrección para sus vulnerabilidades).
# Solo HMAC: la clave es un secreto compartido, nunca una clave asimétrica.
ALGORITHM = os.getenv("ALGORITHM", "HS256")
if ALGORITHM not in ("HS256", "HS384", "HS512"):
    raise RuntimeError("ALGORITHM debe ser HS256, HS384 o HS512.")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
# Duración de la sesión cuando el usuario marca "Recuérdame" (ODON-255).
REMEMBER_ME_EXPIRE_DAYS = int(os.getenv("REMEMBER_ME_EXPIRE_DAYS", "7"))

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está configurada. Revisa backend/.env")
# HS256 necesita una clave de al menos 32 bytes (RFC 7518, sección 3.2).
if len(SECRET_KEY.encode("utf-8")) < 32:
    raise RuntimeError(
        "SECRET_KEY debe tener al menos 32 bytes. Genera una con: "
        "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        return payload

    except InvalidTokenError:
        return None


def token_lifetime(remember_me: bool = False) -> timedelta:
    if remember_me:
        return timedelta(days=REMEMBER_ME_EXPIRE_DAYS)
    return timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)


def create_access_token(data: dict, remember_me: bool = False):

    to_encode = data.copy()

    now = datetime.now(timezone.utc)
    expire = now + token_lifetime(remember_me)

    # iat con fracción de segundo (NumericDate lo admite) permite invalidar las
    # sesiones previas a un cambio de contraseña, aunque ocurran en el mismo
    # segundo (User.password_changed_at, ODON-54).
    to_encode.update({"exp": expire, "iat": now.timestamp()})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
