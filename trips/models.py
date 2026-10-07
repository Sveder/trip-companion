from django.conf import settings
from django.db import models

CHILD_MAX_AGE = 12


class Trip(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trips")
    destination = models.CharField(max_length=40, default="japan")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.destination}"

    @property
    def ages(self):
        return [t.age for t in self.travellers.all()]

    @property
    def has_child(self):
        return any(t.is_child for t in self.travellers.all())

    @property
    def has_adult(self):
        return any(not t.is_child for t in self.travellers.all())


class Traveller(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="travellers")
    age = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["-age"]

    @property
    def is_child(self):
        return self.age <= CHILD_MAX_AGE


def active_trip(user):
    """One active trip per account: the newest one."""
    return Trip.objects.filter(user=user).prefetch_related("travellers").first()
