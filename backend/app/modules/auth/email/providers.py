"""
Email Provider Abstraction.
"""

import abc
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailProvider(abc.ABC):
    """
    Common interface for all email delivery backends.
    """

    @abc.abstractmethod
    async def send_email(
        self, to_email: str, subject: str, html_content: str, text_content: str
    ) -> None:
        """Sends an email asynchronously."""
        pass


class ConsoleProvider(EmailProvider):
    """
    Console Email Provider for local development and testing.
    Prints email content to system log/stdout.
    """

    async def send_email(
        self, to_email: str, subject: str, html_content: str, text_content: str
    ) -> None:
        logger.info(
            "\n"
            "=========================================================\n"
            "                 [DEVELOPMENT EMAIL SINK]                \n"
            f"Sender: {settings.EMAIL_SENDER}\n"
            f"To: {to_email}\n"
            f"Subject: {subject}\n"
            "---------------------------TEXT--------------------------\n"
            f"{text_content}\n"
            "========================================================="
        )


class SMTPProvider(EmailProvider):
    """
    Production-grade SMTP Email Provider.
    Executes standard library smtplib in a threadpool to prevent event-loop blockage.
    """

    async def send_email(
        self, to_email: str, subject: str, html_content: str, text_content: str
    ) -> None:
        if not settings.SMTP_HOST:
            logger.warning("SMTP_HOST not configured. Falling back to Console delivery.")
            console = ConsoleProvider()
            await console.send_email(to_email, subject, html_content, text_content)
            return

        # Execute blocking SMTP delivery in an async thread pool
        await asyncio.to_thread(
            self._sync_send, to_email, subject, html_content, text_content
        )

    def _sync_send(
        self, to_email: str, subject: str, html_content: str, text_content: str
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_SENDER
        msg["To"] = to_email

        # Attach text and html parts
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            # Connect and send
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT or 587, timeout=10) as server:
                server.ehlo()
                if settings.SMTP_USER and settings.SMTP_PASS:
                    server.starttls()
                    server.ehlo()
                    server.login(settings.SMTP_USER, settings.SMTP_PASS)
                server.sendmail(settings.EMAIL_SENDER, to_email, msg.as_string())
            logger.info(f"SMTP: Verification email successfully sent to {to_email}")
        except Exception as exc:
            logger.error(f"SMTP delivery failed to {to_email}: {exc}")
            raise


class MockEmailProvider(EmailProvider):
    """
    Mock email provider for unit/integration testing assertions.
    """

    def __init__(self):
        self.sent_emails = []

    async def send_email(
        self, to_email: str, subject: str, html_content: str, text_content: str
    ) -> None:
        self.sent_emails.append(
            {
                "to_email": to_email,
                "subject": subject,
                "html_content": html_content,
                "text_content": text_content,
            }
        )


def get_email_provider() -> EmailProvider:
    """Factory function returning active email provider based on configuration."""
    prov_name = settings.EMAIL_PROVIDER.lower()
    if prov_name == "smtp":
        return SMTPProvider()
    elif prov_name == "mock":
        return MockEmailProvider()
    return ConsoleProvider()
