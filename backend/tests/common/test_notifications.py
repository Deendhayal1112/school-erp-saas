"""
Tests for Notification Service.
"""

import pytest

from app.common.enums import NotificationChannel
from app.notifications.service import NotificationService


@pytest.mark.asyncio
async def test_notification_delivery_coordination():
    service = NotificationService()

    # 1. Email notification
    email_success = await service.send_notification(
        channel=NotificationChannel.EMAIL,
        recipient="test@schoolerpsaas.com",
        body="Hello World!",
        subject="Test alert",
    )
    assert email_success is True

    # 2. SMS notification
    sms_success = await service.send_notification(
        channel=NotificationChannel.SMS,
        recipient="+1234567890",
        body="Test SMS message",
    )
    assert sms_success is True

    # 3. Push notification
    push_success = await service.send_notification(
        channel=NotificationChannel.PUSH,
        recipient="device_token_abc123",
        body="Test push alert",
        subject="Important Announcement",
    )
    assert push_success is True
