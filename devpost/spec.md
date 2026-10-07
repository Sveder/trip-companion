---
doc: spec
status: draft
---

# Trip Companion (working title) — Technical Spec

## How This Works, In Plain Language
One website, made with Django, runs on the sveder.com server at https://trip.sveder.com. The same website works on a phone,
a laptop and the TV's web browser; on the TV it shows big cards that the remote's arrow keys move between.

All the travel content — Japanese foods, words, do and don't, emergency numbers, transport, the Street View hunt, the
chopsticks activity, the buy-in-advance list — lives in plain content files in the repo, one file per module. Changing a
fact means editing a text file, not code.

When a parent signs in and describes the trip (Japan, family size, ages), the website picks the modules that fit the family,
lets the parent add or remove modules, and saves the result as the family's course: an ordered list of activities. The site
remembers which activities are done and which words the family knows, so every visit opens the next activity, and quizzes
bring back words that need practice. Every two days, a short email invites the family back.

Why this shape: it reuses tools that already run on Michael's servers (Django, the droplet, Amazon SES for email) and needs no
paid service. Accepted tradeoff: server-rendered pages feel a little less "app-like" than a full JavaScript app; CSS and small
scripts give the Matific-style motion.

## The Core Journey Through the System
PRD ref: `prd.md > The Core Journey`.

1. **Log in** → the parent enters an email → the site sends a sign-in link by SES → the link logs them in. (Or: "Sign in with
   Google" → Google → back to the site.) → **Accounts**.
2. **Trip setup** → a form: destination, family size, each traveller's age → saved as a `Trip` with `Traveller` rows → **Trips**.
3. **Suggested course** → **Course builder** reads every module file for Japan, keeps the ones whose audience fits the
   travellers (adult / child), and shows all modules with the suggested ones switched on.
4. **Customise** → the parent switches modules on and off.
5. **Build** → the builder writes a `Course` with ordered `CourseItem` rows (one per activity).
6. **Next activity** → the home page finds the first `CourseItem` not done and opens it → **Activity player**.
7. **Practise** → the quiz asks words and facts that are due → **Practice (repetition)** updates each item's box.
8. **Come back** → a daily job checks each family; if two days passed since the last reminder and activities wait, it sends
   an email → **Reminders**.
9. **After the trip** → once the trip's end date has passed, the home page shows **Highlights** instead of the next activity.

## Stack
Accepted by Michael, 2026-10-07 ("The stack looks good").
- Python 3.12, **Django 5.x** — server-rendered pages. https://docs.djangoproject.com/
- **django-allauth** — email sign-in links ("login by code/link") and Google sign-in. https://docs.allauth.org/
- **SQLite** — one file database; enough for a family-scale POC. https://www.sqlite.org/
- **PyYAML** — reads the content files. https://pyyaml.org/
- **boto3 / Amazon SES** — sign-in and reminder emails, from the existing SES setup. https://docs.aws.amazon.com/ses/
- Plain CSS and small vanilla JavaScript (no build step) for animation, TV arrow-key navigation, video recording.
- gunicorn + nginx + certbot on the existing sveder.com droplet.
- To verify early: the exact allauth setting for login-by-link in the current release.

## Where It Runs and How Someone Tries It
- **Local:** `python -m venv venv && venv/bin/pip install -r requirements.txt && venv/bin/python manage.py migrate &&
  venv/bin/python manage.py runserver` → open http://127.0.0.1:8000/
  Emails print to the console locally (`EMAIL_BACKEND` console), so no keys are needed to try it.
- **Production (chosen):** https://trip.sveder.com on the sveder.com droplet: an A record at Namecheap, an nginx site,
  `certbot --nginx`, a gunicorn systemd unit. Secrets in `.env` on the server only (SES keys, Google client id/secret, Django
  secret key). Public pages get the Sveder corner badge (`/sveder-badge.js`) and "Made by Sveder".
- **TV:** open https://trip.sveder.com in the LG TV web browser; the layout switches to TV mode for wide screens or `?tv=1`.
- **Demo video:** record on the TV and a phone, following `scope.md > What "Working" Looks Like`.
- **Repository:** public GitHub repo, open-source licence (MIT), with this `devpost/` folder (minus `learner-profile.md`).

## Look and Feel
From `prd.md > Look and Feel` and `scope.md > Inspiration & Identity`.
- Bright, game-like, kid-first, like Matific: rounded cards, big friendly buttons, generous spacing, playful motion on success.
- Place facts with the energy of Geography Now: short, punchy, one fact per card.
- Copy tone: excited and simple; a 4-year-old must understand the kids' screens when a parent reads them aloud.
- TV mode: very large type, high contrast, one focused card at a time, clear focus ring for the remote.
- **Pending:** guide animal, main colour and the finish celebration (our 4-year-old, asked 2026-10-07 18:00), and Michael's own direction.
  Until then the build uses neutral placeholders that are easy to swap (CSS variables, one mascot image slot).

## Components

### Accounts
Email sign-in link and Google sign-in (django-allauth). After the first login → trip setup; after that → home.
PRD ref: `prd.md > Login`.

### Trips
`Trip` (destination, start and end dates) and `Traveller` (age; adult or child is derived from age). One active trip per account.
PRD ref: `prd.md > Trip setup and course builder`.

### Content library
YAML files under `content/japan/`, one per module. Each module has: id, title, audience (`all`, `adult`, `child`), order, and a
list of activities. An activity has a type and its data:
- `cards` — fact cards (food, do and don't, safety, transport); a card can hold an image and a short text.
- `words` — word list (Japanese, reading, Hebrew/English meaning, optional audio file) → feeds Practice.
- `video` — a YouTube id, `approved: true|false`; unapproved videos never show.
- `streetview` — a Google Maps embed URL and a list of "things to spot".
- `steps` — a guided real-world activity (chopsticks): ordered steps, each text / video / link / record.
- `links` — buy-in-advance items with referral URLs, each with `audience`.
Quiz items are derived from `words` and from cards marked `quiz: true`.
`content/previews.yaml` lists the "coming soon" countries (Uzbekistan first) with a picture and one line.
PRD ref: `prd.md > Modules (Japan)`.

### Course builder
Reads the content library, suggests modules whose audience fits the travellers (adults-only → no `child` modules switched on,
but they stay listed), lets the parent toggle, and on "Build" writes the course in module order.
PRD ref: `prd.md > Trip setup and course builder`.

### Activity player
One template per activity type (cards, words, video, streetview, steps, links). "Done" marks the `CourseItem` done and opens
the next one. TV mode: arrow keys move focus, OK presses.
PRD ref: `prd.md > Chopsticks activity`, `prd.md > Street View tour`, `prd.md > Buy in advance`.

### Chopsticks activity (steps)
Step 1 shows the children's-chopsticks referral link only if the trip has a child. Step 2 plays the approved YouTube video.
Step 3 is practice. Step 4 records a short clip with the phone camera in the browser (MediaRecorder) and offers "Share" through
the phone's share sheet (Web Share API), so it can go to Instagram. On a device without a camera (the TV) step 4 says
"do this on your phone" and still lets the family mark it done.
PRD ref: `prd.md > Chopsticks activity`.

### Street View hunt
A Google Maps embed (no API key) inside the activity, with the "things to spot" list beside it. The family taps an item when
they find it (the embed cannot report what is on screen, so ticking is by hand). All ticked → done, with the celebration.
PRD ref: `prd.md > Street View tour`.

### Practice (repetition)
Leitner boxes: each word or quiz fact has a box 1–5 per family. Right → box +1 and due later (1, 2, 4, 7, 14 days); wrong →
box 1, due next visit. A quiz takes up to 8 due items, earliest due first. When the course is finished, practice keeps
offering due items until the trip.
PRD ref: `prd.md > Quiz and repetition`.

### Reminders
A management command `send_reminders`, run once a day by cron on the server at 17:00 Israel time. It emails a family when
its last reminder or visit is at least two days old, activities wait, and the trip has not started. Each email has a link
straight to the next activity and an unsubscribe link.
PRD ref: `prd.md > Reminders`.

### Highlights (after the trip)
After the trip end date, home shows highlights: the activities the family completed and their own chopsticks clips that they
chose to save, plus a "words we learned" list. Assumption, see Decisions: no photo upload in the POC.
PRD ref: `prd.md > After the trip`.

### TV mode
A CSS layout for wide screens and `?tv=1`; JavaScript moves focus between cards with the arrow keys; video plays full width.
PRD ref: `prd.md > Screens and Layout`.

## Data Model
All in SQLite on the server; it survives restarts and returns.
- `User` (allauth) — email; Google account link if used.
- `Trip` — user, destination (`japan`), start_date, end_date.
- `Traveller` — trip, age.
- `Course` — trip, built_at, chosen module ids (JSON).
- `CourseItem` — course, order, module id, activity id, done_at (null until done).
- `PracticeItem` — trip, item key (module/activity/item), box (1–5), due_on, last_result.
- `Clip` — trip, file (chopsticks recording the family saved), created_at. Stored under `media/` on the server.
- `ReminderLog` — trip, sent_at.
Content is not in the database; it is read from `content/` at runtime, so content edits need no migration.

## File Structure
```
trip-companion/
├── manage.py
├── requirements.txt
├── LICENSE                      # MIT
├── README.md                    # what it is, how to run, link to the live site
├── .env.example                 # names of the secrets, no values
├── tripapp/                     # Django project settings and urls
│   ├── settings.py
│   └── urls.py
├── accounts/                    # sign-in pages around django-allauth
├── trips/                       # Trip, Traveller, trip setup form
├── courses/                     # Course, CourseItem, builder, home ("next activity")
│   └── builder.py               # module suggestion and course building
├── activities/                  # activity player views + one template per activity type
├── practice/                    # PracticeItem, Leitner logic, quiz pages
├── reminders/                   # ReminderLog, send_reminders management command
├── highlights/                  # after-the-trip page
├── content/
│   ├── japan/                   # food.yaml, words.yaml, dos_donts.yaml, safety.yaml, transport.yaml,
│   │                            # streetview.yaml, chopsticks.yaml, buy_in_advance.yaml
│   ├── previews.yaml            # coming-soon countries
│   └── media/                   # images and audio used by the content
├── templates/                   # base layout, TV mode, shared components
├── static/                      # css (theme variables), js (tv-nav, recorder, celebrate)
├── deploy/                      # nginx site, gunicorn systemd unit, cron line
└── devpost/                     # Devpost learning workspace (scope, prd, spec, checklist)
```

## External Services and Dependencies
- **Amazon SES** (existing account, eu-central-1, sender m@sveder.com) — sign-in links and reminders; `send_email` via boto3.
  Cost: cents per thousand emails. Keys in server `.env`.
- **Google sign-in** — an OAuth client with redirect `https://trip.sveder.com/accounts/google/login/callback/`. Needs a
  client id and secret created in Google Cloud Console. Free. Until it exists, email sign-in works alone.
  https://docs.allauth.org/en/latest/socialaccount/providers/google.html
- **Google Maps embed** — iframe URLs from Google Maps "Share → Embed a map", Street View included. No key, no billing.
- **YouTube embed** — `https://www.youtube-nocookie.com/embed/<id>`. Free. Every id needs Michael's approval in the content file.
- **Referral links** — plain outbound links (AliExpress children's chopsticks; a Japan snack box service). Real affiliate ids
  are added when the accounts exist; until then the links work without them.
- **Hosting** — sveder.com droplet (existing), Namecheap DNS (existing), Let's Encrypt certificate (free).

## Important Failure Modes
- **A YouTube video is removed or blocked from embedding** → the activity shows the card text and a "watch on YouTube" link, and
  can still be marked done.
- **The browser cannot record video (TV, old phone, no permission)** → step 4 says "do this on your phone" and offers "done".
- **A sign-in email is slow or lands in spam** → the sign-in page says to check spam and offers Google sign-in.

## What Was Simplified and Why
- **Content files** instead of an admin editor — the content changes rarely in the POC; text files are reviewable in Git.
- **Ticking found items by hand** in the Street View hunt instead of automatic detection — an embed cannot report what is visible.
- **Email reminders** instead of phone push — agreed with Michael; push does not reach the TV browser.
- **Highlights from the family's own app history** (completed activities, saved clips, learned words) instead of photo uploads
  from the trip — keeps the POC without a photo-storage feature.
- **SQLite** instead of PostgreSQL — family scale.

## Decisions and Open Issues
Learner decisions (Michael, 2026-10-07):
- Stack: Django, server-rendered, content files, SQLite — accepted.
- Hosting: public at trip.sveder.com — accepted "for now".
- Reminders: email — accepted.
Implementation details derived by the agent (not Michael's choices): Leitner intervals 1/2/4/7/14 days; 8 items per quiz;
reminder time 17:00; TV mode by width or `?tv=1`; MIT licence.

Open:
- **Look and Feel** waits for our 4-year-old's answers and Michael's direction (asked 2026-10-07 18:00).
- **Highlights** content (assumption above): confirm or change.
- **Google OAuth client:** needs a client id/secret; until then, email sign-in only.
- **One useful unknown:** not yet discussed — asked in the review.
