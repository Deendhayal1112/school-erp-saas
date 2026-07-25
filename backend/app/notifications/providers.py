"""
Notification Provider Abstractions and Implementations.
"""

import abc
import logging
from typing import Any

logger = logging.getLogger(__name__)


class NotificationProvider(abc.ABC):
    """Abstract interface defining operations for notification backends."""

    @abc.abstractmethod
    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Sends a message to the target recipient."""
        pass


class EmailNotificationProvider(NotificationProvider):
    """Email delivery channel provider."""

    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        logger.info("EmailNotificationProvider: Sending email to %s, subject: %s", recipient, subject)
        # In a fully integrated environment, this delegates to SMTPProvider / aiosmtplib.
        return True


class SMSNotificationProvider(NotificationProvider):
    """SMS text delivery channel provider."""

    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        logger.info("SMSNotificationProvider: Sending SMS to %s, message: %s", recipient, body[:30])
        # Delegates to Twilio / alternative SMS carrier integration in production.
        return True


class PushNotificationProvider(NotificationProvider):
    """Firebase Cloud Messaging (FCM) push notification provider."""

    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        logger.info("PushNotificationProvider: Sending push to device %s, subject: %s", recipient, subject)
        # FCM HTTP v1 API invocation in production.
        return True


class InAppNotificationProvider(NotificationProvider):
    """In-App DB persisted message provider."""

    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        logger.info("InAppNotificationProvider: Saving in-app alert for user %s", recipient)
        # Inserts record into database-persisted notifications table in production.
        return True
