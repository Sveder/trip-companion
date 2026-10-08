from django.contrib import admin

from .models import Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "trip", "thing", "content_type", "size", "created_at")
    list_filter = ("thing",)
    list_select_related = ("trip",)
