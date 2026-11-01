import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from jose import JWTError, jwt

# Ruta absoluta al directorio backend/ (no depende del directorio de ejecución)
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
# Duración de la sesión cuando el usuario marca "Recuérdame" (ODON-255).
REMEMBER_ME_EXPIRE_DAYS = int(os.getenv("REMEMBER_ME_EXPIRE_DAYS", "7"))

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está configurada. Revisa backend/.env")


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        return payload

    except JWTError:
        return None


def token_lifetime(remember_me: bool = False) -> timedelta:
    if remember_me:
        return timedelta(days=REMEMBER_ME_EXPIRE_DAYS)
    return timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)


def create_access_token(data: dict, remember_me: bool = False):

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + token_lifetime(remember_me)

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
