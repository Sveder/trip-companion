from django.conf import settings
from django.db import models


class Contact(models.Model):
    """When the family last opened the site, and if they stopped the reminders."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contact")
    last_seen = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Contact {self.user}"


class ReminderLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminders")
    sent_at = models.DateTimeField()
    item = models.ForeignKey("courses.CourseItem", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Reminder to {self.user} at {self.sent_at:%Y-%m-%d %H:%M}"
