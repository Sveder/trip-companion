from django.contrib import admin

from .models import Traveller, Trip


class TravellerInline(admin.TabularInline):
    model = Traveller
    extra = 0


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("user", "destination", "start_date", "length_days", "end_date", "created_at")
    search_fields = ("user__email",)
    inlines = [TravellerInline]
