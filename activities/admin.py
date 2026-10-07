from django.contrib import admin

from .models import Clip


@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ("id", "trip", "item", "content_type", "size", "created_at")
    list_select_related = ("trip",)
