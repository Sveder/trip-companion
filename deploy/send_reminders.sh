#!/bin/sh
# Cron runs this at 14:00 and 15:00 UTC. It sends only in the run that is 17:00 Israel time,
# so the send time stays 17:00 in summer (UTC+3) and in winter (UTC+2).
[ "$(TZ=Asia/Jerusalem date +%H)" = "17" ] || [ "$1" = "--now" ] || exit 0
cd /srv/www/trip-companion
exec venv/bin/python manage.py send_reminders
