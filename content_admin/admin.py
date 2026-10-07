from django.contrib import admin

from .models import Activity, Module


class ActivityInline(admin.StackedInline):
    model = Activity
    extra = 0


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "country", "audience", "order", "ready")
    list_filter = ("country", "audience", "ready")
    inlines = [ActivityInline]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "type", "order")
    list_filter = ("type", "module")
