from passlib.context import CryptContext

from app.core.settings import get_settings

# Costo de bcrypt: 12 por defecto (seguro para producción). Las pruebas lo bajan
# a 4 con BCRYPT_ROUNDS para no gastar minutos en hashes; los hashes guardan su
# propio costo, así que se verifican igual con cualquier valor.
BCRYPT_ROUNDS = get_settings().bcrypt_rounds

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)
