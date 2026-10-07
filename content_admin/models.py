from django.db import models

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
