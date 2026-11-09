"""Envío de correos (ODON-54).

Con SMTP_HOST configurado en backend/.env, el correo se envía por SMTP.
Sin SMTP_HOST, en desarrollo y pruebas el correo se escribe en el log
"odontonet.email" para poder seguir el enlace a mano. En producción el correo
es opcional (la clínica puede no tener internet): sin SMTP no se envía y el
log nunca lleva el cuerpo, porque contiene enlaces de recuperación.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.settings import get_settings

logger = logging.getLogger("odontonet.email")


def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    host = settings.smtp_host.strip()

    if not host:
        if settings.is_production:
            logger.warning("Correo no enviado: SMTP no está configurado. Asunto: %s", subject)
            return
        logger.info("Correo no enviado (SMTP_HOST vacío). Para: %s | Asunto: %s\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        # Se envía en segundo plano: un fallo no debe revelar al cliente si la
        # cuenta existe. Se registra sin el cuerpo (contiene el enlace).
        logger.exception("No se pudo enviar el correo '%s'.", subject)
