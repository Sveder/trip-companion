from django.contrib import admin

from .models import Course, CourseItem


class CourseItemInline(admin.TabularInline):
    model = CourseItem
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("trip", "built_at")
    inlines = [CourseItemInline]
