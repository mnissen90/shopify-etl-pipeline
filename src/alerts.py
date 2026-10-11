"""Alerts: email notifications for pipeline failures and data issues."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from ..config import AlertConfig

logger = logging.getLogger(__name__)


def send_alert(config: AlertConfig, subject: str, body: str) -> None:
    """Send a plain-text alert email to all configured recipients."""
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)

    with smtplib.SMTP(config.smtp_host, config.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(config.smtp_user, config.smtp_password)
        smtp.sendmail(config.sender, config.recipients, message.as_string())

    logger.info("Alert sent: %s", subject)
