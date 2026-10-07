from django.contrib import admin

from .models import Clip, ReferralClick


@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ("id", "trip", "item", "content_type", "size", "created_at")
    list_select_related = ("trip",)


@admin.register(ReferralClick)
class ReferralClickAdmin(admin.ModelAdmin):
    list_display = ("link_id", "trip", "activity", "clicked_at")
    list_filter = ("link_id",)
