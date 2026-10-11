from django.conf import settings
from django.db import models


class Contact(models.Model):
    """When the family last opened the site, in which language, and if they stopped the reminders."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contact")
    last_seen = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    # The site language the family last used. A reminder is sent by cron, with no request, so it reads this.
    language = models.CharField(max_length=8, default="en")
    # "Continue on another device" (T145): one magic link per family, made once and never rotated.
    link_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    link_sent_at = models.DateTimeField(null=True, blank=True)
    # The address typed on /continue/. It becomes user.email only when the link is opened, so a typo or a
    # stranger's address never starts reminders to that address.
    link_email = models.EmailField(blank=True)

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
