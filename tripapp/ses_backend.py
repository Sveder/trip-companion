"""Send Django email through Amazon SES (sesv2, raw message)."""
import boto3
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class SESBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        client = boto3.client("sesv2", region_name=settings.AWS_SES_REGION)
        sent = 0
        for message in email_messages:
            try:
                client.send_email(
                    FromEmailAddress=message.from_email,
                    Destination={"ToAddresses": message.recipients()},
                    Content={"Raw": {"Data": message.message().as_bytes()}},
                )
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
