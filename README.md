# Trip Companion

A web app that gets a family ready and excited for a trip to Japan: short activities for kids and grown-ups,
picked for the family, one at a time. Works on a phone, a laptop and a TV browser.

Live: https://trip.sveder.com

## Run it locally

    python3 -m venv venv
    venv/bin/pip install -r requirements.txt
    venv/bin/python manage.py migrate
    venv/bin/python manage.py load_content japan
    venv/bin/python manage.py runserver

Open http://127.0.0.1:8000/. Sign-in codes print in the terminal (console email backend), so no keys are needed.

## Tests

    venv/bin/python manage.py test

## Content

Each Japan module is one YAML file in `content/japan/`. `manage.py load_content japan` loads them into the database.

## Deploy

`deploy/` holds the nginx site, the gunicorn systemd unit and `deploy.sh`. Secrets live in `.env` on the server only;
`.env.example` lists the names.

Made by [Sveder](https://sveder.com). MIT licence.
