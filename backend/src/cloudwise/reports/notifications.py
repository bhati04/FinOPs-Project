"""Scheduled report email notification boundary."""

from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from cloudwise.core.config import Settings
from cloudwise.reports.models import NotificationStatus


class NotificationProvider(Protocol):
    """Send a report-ready notification without attaching report data."""

    name: str

    def send(self, recipient: str, subject: str, body: str) -> NotificationStatus: ...


class DisabledNotificationProvider:
    """Explicit local provider that performs no external delivery."""

    name = "disabled"

    def send(self, recipient: str, subject: str, body: str) -> NotificationStatus:
        del recipient, subject, body
        return NotificationStatus.SKIPPED


class SESNotificationProvider:
    """Platform-role AWS SES email delivery."""

    name = "aws_ses"

    def __init__(self, region: str, sender: str) -> None:
        self._sender = sender
        self._client = boto3.client("sesv2", region_name=region)

    def send(self, recipient: str, subject: str, body: str) -> NotificationStatus:
        try:
            self._client.send_email(
                FromEmailAddress=self._sender,
                Destination={"ToAddresses": [recipient]},
                Content={
                    "Simple": {
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                    }
                },
            )
            return NotificationStatus.SENT
        except (ClientError, BotoCoreError):
            return NotificationStatus.FAILED


def build_notification_provider(settings: Settings) -> NotificationProvider:
    """Build the configured platform notification provider."""
    if settings.notification_provider == "ses":
        if not settings.notification_from_email:
            return DisabledNotificationProvider()
        return SESNotificationProvider(
            settings.notification_ses_region, settings.notification_from_email
        )
    return DisabledNotificationProvider()
