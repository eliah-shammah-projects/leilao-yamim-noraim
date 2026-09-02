"""Outgoing email.

Sending is best effort by design. A bid that is already committed must never be
lost or rolled back because the mail server was slow or misconfigured, so every
failure here is logged and swallowed. The caller is told whether the message
went out, not asked to react to it.
"""

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 15


def is_configured(config):
    """True when there are enough settings to attempt a send."""
    return all(
        config.get(key)
        for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM", "ADMIN_EMAIL")
    )


def _send(config, subject, body):
    if not is_configured(config):
        logger.warning("SMTP not configured, email not sent. Subject: %s", subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["MAIL_FROM"]
    message["To"] = config["ADMIN_EMAIL"]
    message.set_content(body)

    try:
        with smtplib.SMTP(
            config["SMTP_HOST"], config["SMTP_PORT"], timeout=SMTP_TIMEOUT_SECONDS
        ) as smtp:
            smtp.starttls()
            smtp.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            smtp.send_message(message)
    except Exception:
        logger.exception("Failed to send email. Subject: %s", subject)
        return False

    logger.info("Email sent. Subject: %s", subject)
    return True


def send_bid_notification(config, occasion, aliyah, bid, amount_text):
    """Notify the admin of one accepted bid.

    Plain text for now. The branded HTML version with the community logo is a
    phase 6 item.
    """
    subject = f"Novo lance: {aliyah.label} - {amount_text}"
    body = "\n".join(
        [
            "Novo lance recebido.",
            "",
            f"Ocasiao: {occasion.name}",
            f"Aliyah: {aliyah.label} ({aliyah.moment_group})",
            f"Valor: {amount_text}",
            "",
            f"Nome: {bid.full_name}",
            f"E-mail: {bid.email}",
            f"Telefone: {bid.phone}",
            "",
            f"Recebido em: {bid.created_at:%d/%m/%Y %H:%M} UTC",
        ]
    )
    return _send(config, subject, body)
