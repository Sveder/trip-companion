import json

from django import forms
from django.contrib import admin
from django.utils.html import format_html_join

from .models import Activity, Module


class PrettyJSONField(forms.JSONField):
    """The activity data as indented JSON, so a long card list is readable in the admin."""

    def prepare_value(self, value):
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2)


class ActivityForm(forms.ModelForm):
    data = PrettyJSONField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 30, "cols": 110, "style": "font-family: monospace"}),
        help_text="Cards, steps, words, places, links. A video shows only when its \"approved\" is true.",
    )

    class Meta:
        model = Activity
        fields = "__all__"


def videos(data):
    """Every (youtube id, approved) pair in an activity's data."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("youtube"):
                found.append((node["youtube"], bool(node.get("approved"))))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return found


class ActivityInline(admin.StackedInline):
    model = Activity
    form = ActivityForm
    extra = 0


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "country", "audience", "order", "ready", "edited")
    list_filter = ("country", "audience", "ready", "edited")
    search_fields = ("slug", "title")
    readonly_fields = ("edited",)
    inlines = [ActivityInline]

    def save_model(self, request, obj, form, change):
        obj.edited = True
        super().save_model(request, obj, form, change)
        if change and obj.ready and "ready" in form.changed_data:
            # A stub became real: a family that pressed past the old stub must see it now.
            from courses.models import CourseItem

            CourseItem.objects.filter(activity__module=obj).update(done_at=None)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    form = ActivityForm
    list_display = ("title", "module", "type", "order", "video_list")
    list_filter = ("type", "module")
    search_fields = ("slug", "title")

    @admin.display(description="Videos")
    def video_list(self, obj):
        return format_html_join(", ", "{} ({})", ((vid, "approved" if ok else "not approved") for vid, ok in videos(obj.data)))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        Module.objects.filter(pk=obj.module_id).update(edited=True)

    def delete_model(self, request, obj):
        Module.objects.filter(pk=obj.module_id).update(edited=True)
        super().delete_model(request, obj)
