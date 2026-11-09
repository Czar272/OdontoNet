from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from app.core.settings import get_settings

_settings = get_settings()
SECRET_KEY = _settings.secret_key
# PyJWT (ODON-263; antes python-jose, sin corrección para sus vulnerabilidades).
# Solo HMAC: la clave es un secreto compartido, nunca una clave asimétrica.
ALGORITHM = _settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = _settings.access_token_expire_minutes
# Duración de la sesión cuando el usuario marca "Recuérdame" (ODON-255).
REMEMBER_ME_EXPIRE_DAYS = _settings.remember_me_expire_days


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
