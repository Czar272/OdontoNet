"""Envío de correos (ODON-54).

Con SMTP_HOST configurado en backend/.env, el correo se envía por SMTP.
Sin SMTP_HOST (desarrollo y pruebas), el correo se escribe en el log
"odontonet.email" para poder seguir el enlace a mano. En producción
SMTP_HOST es obligatorio: el log no debe contener enlaces de recuperación.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("odontonet.email")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "si", "sí")


def send_email(to: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()

    if not host:
        logger.info("Correo no enviado (SMTP_HOST vacío). Para: %s | Asunto: %s\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = os.getenv("SMTP_FROM", "OdontoNet <no-reply@odontonet.local>")
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if _env_flag("SMTP_STARTTLS", True):
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        # Se envía en segundo plano: un fallo no debe revelar al cliente si la
        # cuenta existe. Se registra sin el cuerpo (contiene el enlace).
        logger.exception("No se pudo enviar el correo '%s'.", subject)
