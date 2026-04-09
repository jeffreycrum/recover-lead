import hashlib

import structlog
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, From, Mail, To

from app.config import settings

from . import EmailMessage, EmailResult

logger = structlog.get_logger()


class SendGridProvider:
    """SendGrid email provider implementation."""

    def __init__(self, api_key: str, from_email: str) -> None:
        self._client = SendGridAPIClient(api_key=api_key)
        self._from_email = from_email

    def send(self, message: EmailMessage) -> EmailResult:
        mail = Mail(
            from_email=From(self._from_email, "RecoverLead"),
            to_emails=To(message.to_email),
            subject=message.subject,
            html_content=Content("text/html", message.html_content),
        )
        if message.text_content:
            mail.add_content(Content("text/plain", message.text_content))

        try:
            response = self._client.send(mail)
            message_id = response.headers.get("X-Message-Id", "")
            recipient_hash = hashlib.sha256(message.to_email.encode()).hexdigest()[:8]
            logger.info(
                "email_sent",
                recipient_hash=recipient_hash,
                subject=message.subject,
                status_code=response.status_code,
            )
            return EmailResult(success=True, message_id=message_id)
        except Exception as e:
            logger.error("email_send_failed", error=str(e))
            return EmailResult(success=False, error=str(e))


def get_email_provider() -> SendGridProvider:
    return SendGridProvider(
        api_key=settings.sendgrid_api_key,
        from_email=settings.sendgrid_from_email,
    )
