#!/bin/sh
# Run on the server after the code is pushed: bash deploy/deploy.sh
set -e
cd /srv/www/trip-companion
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q -r requirements.txt
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py load_content japan uzbekistan
venv/bin/python manage.py collectstatic --noinput -v0
# Only our own files: a root-owned file (a hand-made test page) must not stop the restart below.
find staticfiles -user "$(id -u)" -exec chmod a+rX {} +
sudo install -m 644 deploy/trip-reminders.cron /etc/cron.d/trip-reminders
sudo systemctl restart trip
