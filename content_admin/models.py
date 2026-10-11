from django.db import models

from .i18n import is_hebrew

AUDIENCES = [("all", "Everyone"), ("adult", "Grown-ups"), ("child", "Kids")]
ACTIVITY_TYPES = [
    ("cards", "Cards"),
    ("words", "Words"),
    ("video", "Video"),
    ("streetview", "Street View hunt"),
    ("steps", "Guided steps"),
    ("links", "Links"),
]


class Module(models.Model):
    country = models.CharField(max_length=40, default="japan")
    slug = models.SlugField(max_length=60)
    title = models.CharField(max_length=120)
    summary = models.CharField(max_length=300, blank=True)
    title_he = models.CharField("title (Hebrew)", max_length=120, blank=True)
    summary_he = models.CharField("summary (Hebrew)", max_length=300, blank=True)
    emoji = models.CharField(max_length=8, blank=True)
    audience = models.CharField(max_length=10, choices=AUDIENCES, default="all")
    order = models.PositiveIntegerField(default=0)
    ready = models.BooleanField(default=True, help_text="False while the module is only a stub.")
    edited = models.BooleanField(default=False, help_text=(
        "True after a change in the admin. load_content then leaves this module alone until "
        "export_content writes it back to its YAML file."))

    class Meta:
        ordering = ["country", "order", "slug"]
        constraints = [models.UniqueConstraint(fields=["country", "slug"], name="unique_module_slug")]

    def __str__(self):
        return f"{self.country}/{self.slug}"

    @property
    def local_title(self):
        return self.title_he if is_hebrew() and self.title_he else self.title

    @property
    def local_summary(self):
        return self.summary_he if is_hebrew() and self.summary_he else self.summary


class Activity(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="activities")
    slug = models.SlugField(max_length=60)
    title = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    order = models.PositiveIntegerField(default=0)
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["module__order", "order", "slug"]
        verbose_name_plural = "activities"
        constraints = [models.UniqueConstraint(fields=["module", "slug"], name="unique_activity_slug")]

    def __str__(self):
        return f"{self.module}/{self.slug}"

    @property
    def local_title(self):
        """The title in the active language. The Hebrew title sits in the data as ``title_he``."""
        return (self.data or {}).get("title_he") or self.title if is_hebrew() else self.title

    @property
    def emoji(self):
        """The activity's own icon (``emoji`` in the data), else its module's icon.

        Two lessons of one module side by side on the course page need different icons (T179).
        """
        return (self.data or {}).get("emoji") or self.module.emoji
