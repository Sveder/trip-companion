#!/bin/sh
# Run on the server after the code is pushed: bash deploy/deploy.sh
set -e
cd /srv/www/trip-companion
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q -r requirements.txt
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py load_content japan uzbekistan
venv/bin/python manage.py collectstatic --noinput  # T229: prints the copied and post-processed (hashed) counts
# Only our own files: a root-owned file (a hand-made test page) must not stop the restart below.
find staticfiles -user "$(id -u)" -exec chmod a+rX {} +
sudo install -m 644 deploy/trip-reminders.cron /etc/cron.d/trip-reminders
# The unit (T191: the gunicorn log hides link tokens). Reload systemd only when the file changed.
if ! cmp -s deploy/trip.service /etc/systemd/system/trip.service; then
    sudo install -m 644 deploy/trip.service /etc/systemd/system/trip.service
    sudo systemctl daemon-reload
fi
sudo systemctl restart trip
