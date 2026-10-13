import datetime

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _, ngettext

CHILD_MAX_AGE = 12

# Feedback T53 made the family age groups, not exact ages. Feedback T264 cut them to two: no lesson is
# for one age of child only, so 'little ones' and 'big kids' are all 'kids'. Each group stores one typical
# age, so "is this a child" and everything built on it keep working. Old trips with ages 2 or 10 read as kids.
GROUPS = [
    # (id, typical age, top age of the group, label, emoji)
    ("kid", 6, 12, _("Kids"), "🧒"),
    ("grownup", 35, 200, _("Grown-ups"), "🧑"),
]
GROUP_IDS = [g[0] for g in GROUPS]
GROUP_AGES = {g[0]: g[1] for g in GROUPS}


def group_of_age(age):
    for gid, _typical, top, _label, _emoji in GROUPS:
        if age <= top:
            return gid
    return "grownup"


def family_line(counts):
    """"2 grown-ups, 1 kid" for {"grownup": 2, "kid": 1}, in the page language."""
    words = {
        "kid": lambda n: ngettext("%(n)d kid", "%(n)d kids", n),
        "grownup": lambda n: ngettext("%(n)d grown-up", "%(n)d grown-ups", n),
    }
    order = ["grownup", "kid"]
    return ", ".join(words[g](counts[g]) % {"n": counts[g]} for g in order if counts.get(g))


# T110: a family that gives no trip length gets a 14-day trip (a common family trip to Japan).
DEFAULT_TRIP_DAYS = 14


class Trip(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trips")
    destination = models.CharField(max_length=40, default="japan")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    # Feedback T54: the family gives the trip length, not a return date. With a start date, end_date = start + length - 1.
    length_days = models.PositiveSmallIntegerField(null=True, blank=True)
    # T110: the day the family tapped "We are home!". From that day the app shows the after-trip page.
    home_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.destination}"

    def set_dates(self, start, length):
        self.start_date, self.length_days = start, length
        self.end_date = start + datetime.timedelta(days=length - 1) if start and length else None
        self.home_on = None

    @property
    def last_day(self):
        """The last day in Japan. A trip with a start but no length lasts DEFAULT_TRIP_DAYS (T110)."""
        if self.end_date:
            return self.end_date
        if self.start_date:
            return self.start_date + datetime.timedelta(days=DEFAULT_TRIP_DAYS - 1)
        return None

    @property
    def ages(self):
        return [t.age for t in self.travellers.all()]

    @property
    def group_counts(self):
        counts = dict.fromkeys(GROUP_IDS, 0)
        for t in self.travellers.all():
            counts[group_of_age(t.age)] += 1
        return counts

    @property
    def family(self):
        return family_line(self.group_counts)

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
    return Trip.objects.filter(user=user).order_by("-created_at", "-id").prefetch_related("travellers").first()
