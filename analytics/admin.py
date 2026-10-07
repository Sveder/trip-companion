from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "trip", "at")
    list_filter = ("name",)
    date_hierarchy = "at"
