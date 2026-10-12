#!/bin/sh
# Cron runs this daily at 04:10 UTC (T232).
cd /srv/www/trip-companion
exec venv/bin/python manage.py delete_empty_guests
