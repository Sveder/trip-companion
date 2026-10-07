from django.contrib import admin

from .models import Contact, ReminderLog

admin.site.register(Contact)
admin.site.register(ReminderLog)
