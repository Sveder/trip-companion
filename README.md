# Trip Companion

A web app that gets a family ready and excited for a trip to Japan: short activities for kids and grown-ups,
picked for the family, one at a time. Works on a phone, a laptop and a TV browser.

![The 'Tap the plate' page of the sushi lesson](docs/readme/sushi-tap-the-plate.png)

Live: https://trip.sveder.com

## For judges

Try these in about 3 minutes on https://trip.sveder.com:

1. Sign in with your email. A one-time code arrives by email. There is no password.
2. Put the family on the plane: drag (or tap) each person into the plane.
3. Build the course. The app picks the activities for this family.
4. Open "All about sushi" and swipe through the pages.
5. On "Tap the plate", tap each dot on the sushi plate.
6. Open a Street View hunt and find the things on a real Japanese street.
7. Add `?lang=he` to any page for Hebrew (right to left). The header link switches back.
8. Add `?tv=1` to any page for the TV mode: big cards for a remote control.

## How it was built

- The plan came first, with the Devpost plan-first skill pack:
  [scope](devpost/scope.md), [PRD](devpost/prd.md), [spec](devpost/spec.md) and [checklist](devpost/checklist.md).
- The checklist splits the build into slices. Each slice has a build line, a verify line and a commit.
- A factory of agent runs built the slices one at a time, from the checklist, and wrote each change to the plan
  under "Revisions".
- Django on the server. Plain CSS and plain JavaScript in the browser, with no build step.
- The pictures are SVG files drawn for this app. The content of each module is one YAML file in `content/japan/`.

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

A superuser edits the content at `/admin/` (`manage.py make_superuser <email>`; the admin uses the same email-code
sign-in, no password). A module changed in the admin is marked `edited`, and `load_content` leaves it alone until
`manage.py export_content japan` writes it back to its YAML file. The export changes only the values that differ and
keeps the comments in the files.

## Deploy

`deploy/` holds the nginx site, the gunicorn systemd unit and `deploy.sh`. Secrets live in `.env` on the server only;
`.env.example` lists the names.

Made by [Sveder](https://sveder.com). MIT licence.
