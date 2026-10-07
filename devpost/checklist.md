---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast (Michael, 2026-10-07)
Run rule (Michael, 2026-10-07): "just run with it even if you don't get my feedback for the slices." Hands-on checkpoints do not block the build; feedback that arrives later becomes a task.
Builder: Michael's factory (`tools/factory/`), one slice per developer run, progress emailed every 4 hours.

## Slices

- [x] **1. Sign in, describe the trip, get a built course — live on trip.sveder.com**
  Becomes usable: At https://trip.sveder.com a parent signs in with an email link, sets Japan, family size and ages, sees the suggested modules (kids' items off for adults-only), toggles modules, presses Build, and lands on the first activity — the Japan food cards; each visit opens the next activity.
  Why now: Michael's order (2026-10-07): "Start with the main flow". This is the kernel — many good parts made into one personal package. It also bootstraps everything: Django project, content files loaded into the database, the public deploy.
  PRD ref: `prd.md > The Core Journey` (steps 1–6), `prd.md > Login`, `prd.md > Trip setup and course builder`, `prd.md > Modules (Japan)` (Food)
  Spec ref: `spec.md > Accounts`, `spec.md > Trips`, `spec.md > Course builder`, `spec.md > Content library`, `spec.md > Activity player`, `spec.md > Data Model`, `spec.md > File Structure`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Scaffold the Django project per the file structure; Module/Activity models and `load_content`; `content/japan/food.yaml` plus stubs for every other Japan module so the builder has the full list; the cards activity template; django-allauth email-link login (SES); Trip and Traveller with the setup form; builder.py suggestion rules by audience; Course and CourseItem; home "next activity"; country picker with Uzbekistan as a "coming soon" card; DNS A record, nginx site, certbot, gunicorn unit on the droplet; Sveder badge and "Made by Sveder".
  Verify (mechanical): Django tests: adults-only → no child modules switched on but listed; a family with a 4-year-old → child modules on; Build creates ordered items; marking one done makes home open the next. `manage.py check --deploy` passes on the server; `curl -I https://trip.sveder.com/` returns 200; a sign-in email arrives through SES.
  Learner check: Sign in on your phone, set up Japan with two adults and two kids (4 and 2), add "buy a snack box", build, and see the first activity (the food cards).
  Commit: `Main flow: sign-in, trip setup, course builder, food cards, live on trip.sveder.com`

- [x] **2. TV mode, checked on the real TV**
  Becomes usable: On the LG TV browser the site switches to TV mode: very large cards, one in focus, the remote's arrows move between cards and OK opens them.
  Why now: Michael's one unknown is the TV; right after the main flow exists, it gets proved on the real TV before more screens are built.
  PRD ref: `prd.md > Screens and Layout`
  Spec ref: `spec.md > TV mode`, `spec.md > Decisions and Open Issues`
  Build: TV mode CSS for wide screens and `?tv=1`; arrow-key focus navigation; check on the real TV (model and webOS version via `lgtv/find_tv.py` when the TV is on).
  Verify (mechanical): A headless browser at 1920×1080 presses ArrowRight and the focused card changes, Enter opens it; the TV's model/webOS version and a screen photo are recorded below under Revisions when the TV is reachable.
  Learner check: Open https://trip.sveder.com on the LG TV, move through the food cards with the remote, and say if it reads well from the couch.
  Commit: `TV mode with remote navigation`

- [x] **3. Look and feel from our 4-year-old and Michael**
  Becomes usable: The whole site wears the chosen colours, guide animal and finish celebration, Matific-style.
  Why now: Every later slice builds screens; setting the look once now saves restyling them all later. Waits for the answers asked on 2026-10-07 at 18:00.
  PRD ref: `prd.md > Look and Feel`
  Spec ref: `spec.md > Look and Feel`
  Build: Theme CSS variables, font, mascot image, celebration animation and sound; apply to existing screens.
  Verify (mechanical): Screenshots of home, builder and a card page at phone and TV sizes; no contrast below WCAG AA on text.
  Learner check: Show our 4-year-old the home screen and the celebration, and tell me what he says.
  Commit: `Theme: our 4-year-old's colours, guide and celebration`

- [x] **4. Words with repetition, and the quiz**
  Becomes usable: A words activity teaches a few Japanese words (with sound where available); a quiz asks due words and facts; right answers come back later, wrong ones sooner.
  Why now: Repetition is what makes the app teach, not just show; the quiz also gives every later module a place to send its facts.
  PRD ref: `prd.md > Quiz and repetition`, `prd.md > Modules (Japan)` (Language)
  Spec ref: `spec.md > Practice (repetition)`, `spec.md > Content library`
  Build: words.yaml, the words activity, PracticeItem with Leitner boxes, the quiz page, quiz facts from cards marked `quiz: true`.
  Verify (mechanical): Tests for box moves and due dates (right → later, wrong → box 1); a quiz holds at most 8 due items, earliest first.
  Learner check: Do the words activity with our 4-year-old, take the quiz, get one wrong on purpose, and see it come back next time.
  Commit: `Words, quiz and repetition`

- [x] **5. The chopsticks activity**
  Becomes usable: The guided chopsticks activity: children's chopsticks referral link (only with kids), the approved video, practice, then record a clip on the phone and share it.
  Why now: The demo's centre moment (real chopsticks, guided by the app); it also proves the video and the camera parts.
  PRD ref: `prd.md > Chopsticks activity`
  Spec ref: `spec.md > Chopsticks activity (steps)`, `spec.md > Activity player`
  Build: The steps activity type; chopsticks.yaml; YouTube embed with the approval flag and fallback; MediaRecorder capture; Web Share; Clip save; TV fallback text.
  Verify (mechanical): The referral step is absent for an adults-only trip; an unapproved video id never renders; on a camera-less browser step 4 shows the fallback; a saved clip appears in the database.
  Learner check: Do the chopsticks activity on your phone with real chopsticks, record a clip, and press Share.
  Commit: `Chopsticks activity with video, recording and share`

- [x] **6. The Street View hunt**
  Becomes usable: A Street View inside a Japanese place (e.g. the fish market or a museum) with a "things to spot" list; tick each find; all found → celebration.
  Why now: A second showpiece for the demo; it depends only on the activity player.
  PRD ref: `prd.md > Street View tour`
  Spec ref: `spec.md > Street View hunt`
  Build: The streetview activity type; streetview.yaml with 2–3 places and their spot lists.
  Verify (mechanical): The Maps embed URL loads (HTTP 200) and the page renders; ticking all items marks the item done.
  Learner check: Play the hunt with our 4-year-old on the TV or a laptop and say if the things to spot were findable.
  Commit: `Street View hunt`

- [x] **7. The rest of Japan, and buy-in-advance**
  Becomes usable: Do and don't in public, safety (emergency numbers), transport, and the buy-in-advance list with referral links (snack box, children's chopsticks).
  Why now: Fills the package after the activity types exist; content-only, low risk.
  PRD ref: `prd.md > Modules (Japan)`, `prd.md > Buy in advance`
  Spec ref: `spec.md > Content library`
  Build: dos_donts.yaml, safety.yaml, transport.yaml, buy_in_advance.yaml (links activity type); quiz facts marked; referral links with click tracking hook.
  Verify (mechanical): `load_content` loads every file without errors; each module page renders; every external link answers 200 or 3xx.
  Learner check: Read the do and don't cards and the emergency numbers, and check the buy-in-advance links open the right products.
  Commit: `Japan content: do and don't, safety, transport, buy in advance`

- [x] **8. Reminders every two days**
  Becomes usable: A family with waiting activities gets a short email every two days, with a link straight to the next activity, and can unsubscribe.
  Why now: Brings people back; needs the course and next-activity logic from slice 2.
  PRD ref: `prd.md > Reminders`
  Spec ref: `spec.md > Reminders`
  Build: ReminderLog, `send_reminders` command, email template, unsubscribe, cron line on the server.
  Verify (mechanical): Tests: no email before two days, one email after, none when finished or the trip started; a dry run on the server lists who would get one.
  Learner check: Get a reminder email in your inbox and tap its link.
  Commit: `Reminder emails every two days`

- [x] **9. After the trip**
  Becomes usable: After the trip dates, home shows the highlights: activities done, saved chopsticks clips, words learned. Before the trip, a finished course keeps offering quizzes.
  Why now: Closes the journey end to end; needs data from slices 2, 4 and 5.
  PRD ref: `prd.md > After the trip`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > Highlights (after the trip)`
  Build: highlights page; home switch by date; finished-course state.
  Verify (mechanical): Tests with dates set before, during and after the trip show the right home screen.
  Learner check: Set a test trip in the past and look at the highlights page.
  Commit: `After-the-trip highlights`

- [x] **10. Super user: edit the demo**
  Becomes usable: Michael edits any module, activity, video approval, Street View link, spot list or referral link in an admin page; the site shows the change at once; export writes it back to the content files.
  Why now: Michael tunes the demo content before recording; everything it edits exists by now.
  PRD ref: `prd.md > Super user and analytics`
  Spec ref: `spec.md > Super-user admin`
  Build: Django admin for content, trips and travellers; `export_content`; Michael's superuser account.
  Verify (mechanical): An admin edit changes the rendered page; `export_content` round-trips (export → load → same content).
  Learner check: Sign in to the admin, change one food card's text, and see it on the site.
  Commit: `Super-user content admin and export`

- [x] **11. Analytics**
  Becomes usable: A staff-only `/stats/` page with daily totals and the funnel (signed up → trip set up → course built → first activity → 3 activities).
  Why now: Events can only be counted once all the actions exist.
  PRD ref: `prd.md > Super user and analytics`
  Spec ref: `spec.md > Analytics`
  Build: Event model, `track()` calls in every action, `/stats/` page, staff-only.
  Verify (mechanical): Tests: each action writes one event; a non-staff user gets 403 on `/stats/`.
  Learner check: Open `/stats/` and see your own test family in the funnel.
  Commit: `Analytics events and stats page`

- [ ] **12. Professional basics**
  Becomes usable: Sentry error reports, styled 404/500 pages, a privacy page, share previews, Google sign-in, nightly backup to B2, uptime alert on Telegram.
  Why now: Hardening comes after the features exist and before the demo is recorded.
  PRD ref: `prd.md > Super user and analytics`
  Spec ref: `spec.md > Monitoring and professional basics`, `spec.md > External Services and Dependencies`
  Build: sentry-sdk and JS loader (Sentry account on Kurt's email); error and privacy pages; Open Graph tags and favicon; Google provider in allauth (OAuth client); backup cron; uptime check.
  Verify (mechanical): A test exception appears in Sentry; `/does-not-exist` shows the styled 404; a shared link shows the preview (Open Graph tags present); the backup file lands in B2; stopping gunicorn triggers one Telegram alert.
  Learner check: Sign in with Google, and share the site link in a chat to see the preview.
  Commit: `Sentry, error pages, privacy, Google sign-in, backups, uptime`

## Hands-on Checkpoints

- [ ] Early usable behavior explored — after slice 2 (main flow on the phone, then the TV check, Michael's unknown); non-blocking
- [ ] Core journey explored — after slice 5 (builder, look, words, chopsticks), with our 4-year-old; non-blocking
- [ ] Final kick-the-tires exploration and feedback completed

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning wrap-up complete and `devpost/app-map.html` shared

## Revisions

- 2026-10-07, before the build: Michael moved the main flow first and the TV check second ("Start with the main flow and only then do TV"). Old slices 1 (food on the TV) and 2 (sign-in and builder) became slice 1 (main flow, with the food cards and the deploy) and slice 2 (TV mode).
- 2026-10-07, slice 1: Sign-in sends a short code by email, not a link. django-allauth 65 has "login by code" built in; a link needs extra code and breaks when the mail app opens a different browser. One page takes the email; a new email gets an account on the way. Open question for Michael: keep the code, or add a link too (factory task).
- 2026-10-07, slice 1: SES on the server uses the server user's existing AWS credentials (`~/.aws`), switched on by `EMAIL_SES=true`. No keys are copied into the app's `.env`.
- 2026-10-07, slice 1: Module stubs (words, do and don't, safety, transport, Street View, chopsticks, buy in advance) hold one "coming soon" card each, marked `ready: false`, so the builder lists the full set. Audiences: Street View hunt = kids; transport and buy in advance = grown-ups; the rest = everyone.
- 2026-10-07, slice 2: TV mode turns on by `?tv=1` (kept in the session, `?tv=0` turns it off) or by a smart-TV browser name (LG `Web0S`, Tizen and others), not by screen width. A desktop monitor is 1920 px wide too, and it must keep the normal layout.
- 2026-10-07, slice 2: OK on a fact card shows that card full screen; Back (webOS key 461) or Escape closes it. OK on a builder card flips its switch. The TV CSS uses no `:has()` and no `inset`, for older webOS browsers.
- 2026-10-07, slice 2: The headless check at 1920x1080 passes on the live site (10 of 10, `trip-companion-tools/tv_check.cjs`). The real TV was off at 14:20 (`lgtv/find_tv.py`: no webOS TV answered), so its model, webOS version and a screen photo are still missing. A factory task holds that check; it does not block the next slices.
- 2026-10-07, slice 3: Built before our 4-year-old's and Michael's answers came in (fast mode; the answers were asked for 18:00). The look follows `spec.md > Look and Feel` with placeholders: a warm cream page with soft dots, a Japan-red main colour, a sun-yellow header line, coloured icon circles on cards, the Nunito font (self-hosted, OFL), an orange fox-like guide drawn as SVG, and a finish celebration of confetti, a short four-note tune and a jumping guide. Every colour is a CSS variable at the top of `static/css/app.css`; the guide is one file, `templates/includes/guide.html`. The real answers swap in there. A factory QUESTION task holds the choice.
- 2026-10-07, slice 3: The contrast check found 4 failures and fixed them: the red was darkened to #b82a22 (the footer link was 4.34:1 on the dots), "coming soon" countries are no longer faded with opacity (dashed border instead), the muted grey was darkened, and the TV dimming of unfocused cards went from 70% to 85%. Result: 10 of 10 pages pass WCAG AA (`trip-companion-tools/theme_check.cjs`). Some browsers block the sound until the person taps the page; the "Party again!" button always plays it.
- 2026-10-07, slice 4: Sound comes from the browser's own Japanese voice (speech synthesis), not from audio files. A card shows "Tap to hear it" only when the browser has a Japanese voice; otherwise the card is silent. Word meanings are in English only for now; Hebrew can be added as a second field.
- 2026-10-07, slice 4: Seven words (konnichiwa, arigatou, ohayou, sayounara, hai, oishii, sumimasen). The quiz asks one question per page with four big answer buttons: a word asks for its meaning, a food card shows its picture and asks for the name. The wrong answers come from the same activity. The words module keeps its old activity id, so courses built before slice 4 keep their item.
- 2026-10-07, slice 4: Leitner timing: a right answer in box N moves the item to box N+1 and asks it again after 1, 2, 4, 7 or 14 days (by box N); box 5 stays in box 5. A wrong answer goes to box 1, due today. Items enter practice when the family presses "We did it!" on the activity. Nav link "Quiz"; the finish page has "Take the quiz".
- 2026-10-07, slice 4: When a "coming soon" module turns real, `load_content` clears the done marks of its course items, so a family who pressed past the stub gets the real activity (part of factory task T15).
- 2026-10-07, slice 5: The chopsticks module is one `steps` activity with four steps: kids' chopsticks link (only with a child), video, practice with tips on Japanese chopstick manners, record. It keeps its old activity id `chopsticks-intro`, so courses built before slice 5 keep their item; the loader clears the stub's done mark.
- 2026-10-07, slice 5: The referral link is an AliExpress search page for kids' training chopsticks, not one product page, so it does not break when one listing goes away. No affiliate id.
- 2026-10-07, slice 5: The video is `CBNw5yX1M34` (Pinkfong, "How to Use Chopsticks? Fun & Easy for Kids") with `approved: false`. Other candidates are in a comment in `chopsticks.yaml`. Until Michael approves one, step 2 shows three written "how" lines, and the video id is not in the page at all. An approved video plays from youtube-nocookie.com.
- 2026-10-07, slice 5: Clips are private family videos, so they live in `private/clips/` (setting `CLIP_ROOT`), outside `media/`, which nginx serves to anyone. Only the family's own login can open a clip (`/clips/<id>/`). A clip is saved only when the family presses "Keep it for our trip"; recording and sharing alone send nothing to the server. Recording stops by itself after 30 seconds. The phone records MP4 where the browser can (better for Instagram), else WebM. Where the browser cannot share a file, a Download button shows instead of Share.
- 2026-10-07, slice 6: The hunt has three places, one activity each: a fish shop in Tsukiji Outer Market (Tokyo), the entrance of Fushimi Inari Taisha (Kyoto, fox statues and orange gates), and the Kaminarimon gate of Senso-ji (Tokyo, the giant lantern). All three are 360° photos that visitors put on Google Maps; Google's own Street View has no inside view of the fish market. The first place keeps the old activity id `streetview-intro`, so courses built before slice 6 keep their item.
- 2026-10-07, slice 6: The embed is `google.com/maps/embed?pb=!6m7!1m6!2m2!1d<lat>!2d<lng>!3f<heading>...`, with no API key. It opens the photo nearest to the point, so the YAML keeps lat/lng to 7 digits. The other keyless form, with a panorama id, loads the frame but shows a black picture for these visitor photos, so it is not used. If a visitor deletes a photo, the embed shows the next nearest one and the spot list can be wrong: `trip-companion-tools/sv_probe.cjs` takes four shots per place to check again.
- 2026-10-07, slice 6: The family ticks each thing by hand (big buttons with a tick circle). When the last one is ticked, the confetti and the tune play, and the page goes on to the next activity after 2.6 s. The server marks the item done only when the form carries every thing; a partial form goes back to the hunt with "Keep looking!". In TV mode each thing to spot is a focus target, and OK ticks it.
- 2026-10-07, slice 7: Each of the four modules (do and don't, safety, transport, buy in advance) keeps its stub's one activity id (`<module>-intro`), so courses built before slice 7 keep their item; the loader clears the stub's done mark. Do and don't and safety are for everyone, with kid-readable cards; cards meant for parents start with "For grown-ups." Transport and buy in advance stay grown-up modules.
- 2026-10-07, slice 7: Facts checked on 2026-10-07: police 110, fire and ambulance 119, the JNTO Japan Visitor Hotline 050-3816-2787 (24 hours, English), JR children's fares (under 6 free with a paying adult, two per adult; 6 to 11 half fare), the large-luggage seat rule on the Tokaido, Sanyo and Kyushu Shinkansen (over 160 cm), type A plugs at 100 V.
- 2026-10-07, slice 7: A quiz card can name its own `answer` and `wrong` choices. The safety quiz asks "What number do you call for the police?" with the choices 110, 119, 100 and 911, instead of asking for a card title.
- 2026-10-07, slice 7: Every shop link (the buy-in-advance list and the chopsticks step) goes through `/go/<item>/<link id>/`. The view saves a `ReferralClick` row (trip, activity, link id, URL, time) and redirects. Only a URL that is in the content can be reached, so `/go/` is not an open redirect, and only the family's own course item works. Slice 11 counts these rows.
- 2026-10-07, slice 7: Buy in advance has six items: two snack box services (TokyoTreat, Bokksu), kids' training chopsticks (only with a child), a type A plug adapter, Visit Japan Web (free, official) and the Japan Rail Pass (official site). The chopsticks and adapter links are AliExpress search pages; factory task T25 replaces them with one product page each. `trip-companion-tools/link_check.py` checks every URL in the content: 6 of 6 answer 200 or 301.
- 2026-10-07, slice 8: The "last visit" is a `Contact.last_seen` time, written by a middleware at most once an hour per signed-in family. The two-day clock starts at the newest of: course built, last visit, last reminder. A trip with no start date still gets reminders; a trip whose start date is today or earlier gets none.
- 2026-10-07, slice 8: The unsubscribe link opens a page with a "Stop the reminder emails" button (POST). Opening the link alone changes nothing, so a mail scanner that follows links cannot unsubscribe a family. The same page offers "Send reminders again". The email also carries a `List-Unsubscribe` header.
- 2026-10-07, slice 8: The server runs in UTC. `/etc/cron.d/trip-reminders` starts `deploy/send_reminders.sh` at 14:00 and 15:00 UTC; the script sends only in the run where the Israel hour is 17, so the send stays at 17:00 in summer and in winter. Log: `/srv/www/trip-companion/reminders.log`. `deploy.sh` installs the cron file.
- 2026-10-07, slice 9: Home picks its screen by the trip dates. Before the start date and during the trip (start to end date, both days included), home shows the next activity or the finish page; the finish page says "Play the quiz every day until the trip" before and "You are in Japan now!" during. From the day after the end date, home shows the highlights. A trip with no end date never switches.
- 2026-10-07, slice 9: Highlights show the activities done (newest last, each opens again), the saved chopsticks clips (played from the family's private `/clips/<id>/`), and every word the family met in the words activity. A star marks a word the family got right in the quiz at least once (Leitner box 2 or higher). "Coming soon" stubs are left out. `/highlights/` opens the same page at any time, so a parent can look at it before the trip.
- 2026-10-07, slice 10: The admin has no password form. `/admin/login/` sends the reader to the site's email-code sign-in with `next=/admin/`; `manage.py make_superuser <email>` gives an account the admin. Michael's account (michael@example.com) was made a superuser on the server by hand, so his email is not in the public repo.
- 2026-10-07, slice 10: `deploy.sh` runs `load_content` on every deploy. So that a deploy does not throw admin edits away, a change in the admin marks the module `edited`, and `load_content` skips an edited module (with a warning) until `export_content` writes it to YAML or `--force` is given. `export_content` edits the YAML file in place with ruamel.yaml: it rewrites only the changed values and keeps the comments and the quoting. Exporting unchanged content changes no file.
- 2026-10-07, slice 10: Edits made on the live site live in the server's database. To bring them into the public repo: `export_content` on the server, then copy the changed `content/japan/*.yaml` files back and commit them. The activity data is edited as indented JSON; the activity list shows each video id and whether it is approved.
- 2026-10-07, slice 11: The `/stats/` funnel counts families from the real tables (users, trips, courses, done items), not from events. So families from before slice 11 count too. The per-day table and the shop-link table come from the `Event` table. A video play is counted when the family taps the YouTube frame (the page loses focus to the frame); the page cannot see the frame's own play button without the YouTube API. A reminder email click is an activity link with `?from=reminder`. A signed-out visitor to `/stats/` goes to sign-in; a signed-in family gets 403.
- 2026-10-07, slice 12 (part 1): Error pages (404 in the site style, 500 as a stand-alone page that needs no database), a privacy page linked from the footer, Open Graph and Twitter share tags with a 1200x630 image, and a compass favicon (`/favicon.ico` is served by Django). Sentry starts only when `SENTRY_DSN` is in the server `.env`, and the browser loader shows only when `SENTRY_JS_LOADER` is set, so the site runs the same without an account. Account deletion is by email to m@sveder.com for now (no self-serve button). Still open in slice 12: the Sentry account and DSN, Google sign-in, the nightly B2 backup and the Telegram uptime alert.
- 2026-10-07, slice 12 (part 2): The nightly backup and the uptime check run on the home server, not on the droplet, so the B2 keys stay at home. The scripts are private helper scripts, outside this repo. Backup at 03:20 Israel time: a consistent copy of `db.sqlite3` (SQLite backup API), `private/` (the clips) and `media/`, in an AES-256 zip, uploaded to the existing B2 bucket under `trip-companion/`; 7 copies kept at home, 30 on B2. First run 2026-10-07: 470 KB zip on B2, read back with 10 users and 2 clips. Uptime: every 5 minutes, two tries 20 s apart; a Telegram message goes to Michael only when the state changes (one on down, one on back up). Tested by stopping `trip.service`: one alert, no repeat, one "back up" line. Still open: the Sentry account and Google sign-in, both need a new account (questions in the task list).
- 2026-10-07, factory task T24: A wrong quiz answer is now due the next day, not the same day (spec Practice changed from "due next visit"). Before, a child who finished a quiz could tap Quiz and get the same missed items at once, in a loop, while the end screen said "come back soon". Now the end screen says "come back tomorrow", and a quiz opened the same day shows "All done for today! Come back tomorrow."
