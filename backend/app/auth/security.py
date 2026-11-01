import os

from passlib.context import CryptContext

# Costo de bcrypt: 12 por defecto (seguro para producción). Las pruebas lo bajan
# a 4 con BCRYPT_ROUNDS para no gastar minutos en hashes; los hashes guardan su
# propio costo, así que se verifican igual con cualquier valor.
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

if BCRYPT_ROUNDS < 4 or BCRYPT_ROUNDS > 31:
    raise RuntimeError("BCRYPT_ROUNDS debe estar entre 4 y 31.")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)
