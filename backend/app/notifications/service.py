"""
Notification Delivery Service.
"""

import logging
from typing import Any

from app.common.enums import NotificationChannel
from app.core.config import settings
from app.notifications.providers import (
    EmailNotificationProvider,
    InAppNotificationProvider,
    NotificationProvider,
    PushNotificationProvider,
    SMSNotificationProvider,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Coordinates message broadcasts across Email, SMS, Push, and In-App channels."""

    def __init__(self) -> None:
        self.providers: dict[NotificationChannel, NotificationProvider] = {
            NotificationChannel.EMAIL: EmailNotificationProvider(),
            NotificationChannel.SMS: SMSNotificationProvider(),
            NotificationChannel.PUSH: PushNotificationProvider(),
            NotificationChannel.IN_APP: InAppNotificationProvider(),
        }

    async def send_notification(
        self,
        channel: NotificationChannel,
        recipient: str,
        body: str,
        subject: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Sends a notification payload over the specified channel."""
        if not settings.ENABLE_NOTIFICATIONS:
            logger.info("Notifications are globally disabled in settings.")
            return True

        provider = self.providers.get(channel)
        if not provider:
            logger.error("No notification provider registered for channel: %s", channel)
            return False

        try:
            logger.debug("Dispatching notification to %s via %s", recipient, channel)
            return await provider.send(
                recipient=recipient,
                body=body,
                subject=subject,
                metadata=metadata,
            )
        except Exception as exc:
            logger.exception("Failed to deliver notification over channel %s: %s", channel, exc)
            return False
