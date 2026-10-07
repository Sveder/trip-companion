#!/bin/sh
# Run on the server after the code is pushed: bash deploy/deploy.sh
set -e
cd /srv/www/trip-companion
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q -r requirements.txt
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py load_content japan
venv/bin/python manage.py collectstatic --noinput -v0
sudo systemctl restart trip
