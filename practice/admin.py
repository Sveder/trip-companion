from django.contrib import admin

from .models import PracticeItem


@admin.register(PracticeItem)
class PracticeItemAdmin(admin.ModelAdmin):
    list_display = ("key", "trip", "box", "due_on", "last_result")
    list_filter = ("box",)
    search_fields = ("key",)
