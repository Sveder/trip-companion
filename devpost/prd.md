---
doc: prd
status: approved
---

# Trip Companion (working title) — Product Requirements

A kid-friendly, adult-friendly app that gets a family ready and excited for a trip to Japan: "a more interactive replacement
for watching YouTube videos about the place and just sitting on the couch".
Source: `scope.md > The Unique Kernel`, `scope.md > Who It's For`.

## The Core Journey
Develops `scope.md > The Core Loop` and `scope.md > What "Working" Looks Like`.

1. **No account** — anyone opens the site and starts. The browser keeps the family; no email, no password (Michael, 2026-10-11).
2. **Tell the app about the trip** — where (Japan; other countries show as "coming soon"), who is coming, in four age groups (little ones 0-3, kids 4-8, big kids 9-12, grown-ups 13+): the parent drags each person into a plane (Michael, feedback 2026-10-08).
3. **See the suggested course** — the app suggests a course and shows all available modules. Modules that fit the family are
   in the suggestion; the others (e.g. kids' activities for a family without kids) are shown, ready to add.
4. **Customise** — the parent adds or removes modules, e.g. adds "buy a snack box".
5. **Build** — the app processes the choices and builds the course: an ordered list of activities.
6. **Do the next activity** — from now on, opening the app shows the next activity automatically, then the next, and so on.
7. **Practise** — quizzes bring back earlier words and facts, so they stick.
8. **Come back** — a reminder a few times a week brings the family back. Missing days is fine.
9. **After the trip** — the app shows trip highlights.

## Screens and Layout
- **Login.**
- **Trip setup** — destination, and who is coming in four age groups, put on a plane.
- **Course builder** — the suggested course, the module list with add/remove, and the "build" action.
- **Today / next activity** — the main screen after the course exists; opens the next activity.
- **Activity screen** — the steps of one activity (video, practice, game, test).
- **Quiz / practice.**
- **Country preview cards** — Uzbekistan and others, "coming soon".
- **After the trip** — highlights.

**Rich lessons (Michael, feedback 2026-10-08):** each module grows a lesson of 10-20 short pages, one screen each: pictures,
tap-a-part-of-the-picture, games, a video in the middle, and where to get or try the thing at home and in Japan. More than
one screen of reading. Food (sushi) is first; the other modules follow the same pattern.

Works on a phone and in the TV's web browser (big, readable, remote-friendly on the TV). Source: `scope.md > The POC Boundary`.

## Look and Feel
- Kid friendly, bright and game-like, like Matific (https://www.matific.com/). Source: `scope.md > Inspiration & Identity`.
- Place facts in the spirit of Geography Now (https://www.youtube.com/@GeographyNow).
- Mood: excitement, "ready and pumped".
- Colour (Michael and our 4-year-old, feedback T83): red like the Japanese flag, but ONLY as a highlight colour (buttons, accents).
  No large red areas; it must not be jarring.
- Finishing a module (our 4-year-old): a star explosion and a nice sound.
- Guide animal: a Japanese animal, a Nara deer, on the Japan screens only (Michael, T87). Each country can get its own guide later; app-wide screens show a neutral paper-plane mark. our 4-year-old's penguin appears sometimes as an Easter egg (rarely, in a celebration).
  Own artwork only: no copyrighted characters (for example not the Suica penguin).

## Features and Behavior

### Login
- [ ] A new visitor taps "Let's start" and lands on trip setup, with no sign-in page.
- [ ] A returning user lands on "today / next activity".

### Trip setup and course builder
- [ ] The user picks Japan; other countries appear as "coming soon" cards and cannot be built.
- [ ] The user puts the family on a plane: drag (or tap) people from four age groups.
- [ ] The app shows a suggested course that matches the family: adults-only families get no kids' items in the suggestion,
      but kids' items stay visible and can be added.
- [ ] The user can add and remove modules, and the course updates.
- [ ] "Build" creates the course; the next screen shows its first activity.

### Modules (Japan)
From `scope.md > The POC Boundary`:
- **Food** — a short course on Japanese foods, watchable on a TV screen.
- **Language** — a few words, with repetition across days.
- **Do and don't in public.**
- **Safety** — emergency numbers.
- **Transport** — how to get around.
- **Guided Street View tour** — an unusual Street View, e.g. a temple full of lucky cats or a fox shrine, with a "things to spot" game.
- **Real-world activities** — e.g. chopsticks (below).
- **Buy in advance** — things to get before the trip, with referral links, e.g. a Japan snack box.
- **After the trip** — highlights.

### Chopsticks activity
1. If the family has a child: an AliExpress referral link to buy children's chopsticks.
2. How to hold them: three written lines (no video; Michael, 2026-10-08).
3. Practise with real chopsticks.
4. Final test: record a short video of yourself using the chopsticks, and share it (e.g. Instagram).
- [ ] The referral step shows only when the family has a child.
- [ ] The video plays inside the activity, also on the TV.
- [ ] The activity ends with the test step and marks itself done.

### Street View tour
- [ ] The tour opens an interactive Street View inside a place (e.g. the lucky cat temple or a fox shrine).
- [ ] A "things to spot" list sits next to it; finding each item ticks it off, and finding all of them finishes the activity.

### Quiz and repetition
- [ ] A quiz asks about words and facts from earlier activities.
- [ ] Items the family got wrong, or learned earlier, come back in later quizzes.

### Buy in advance
- [ ] A list of things to get before the trip, each with a referral link (e.g. a Japan snack box, children's chopsticks).
- [ ] No payment happens inside the app.

### Reminders
- [ ] A reminder a few times a week (about every two days), not daily, invites the family to the next activity.

### While we are there (Michael's feedback T52, 2026-10-08)
- [ ] During the trip, a photo hunt: a list of things to find in Japan (pretty manhole covers, Pikachu, a vending machine, a torii gate, a lucky cat, capsule toys, a bullet train, a convenience store, a police box, and "our own find"). A photo of a thing ticks it off.
- [ ] Only the family sees its photos. The photos feed the after-trip highlights.
- [ ] In Japan, the first home visit of the day opens the photo hunt. The course stays one tap away.

### After the trip
- [ ] After the trip dates, the app shows trip highlights, with the photos from the hunt first.

### Super user and analytics (added by Michael, 2026-10-07, after approval)
- [ ] Michael can sign in as super user and edit any module's content (text, videos, Street View, links); the site shows the change.
- [ ] A staff-only page shows usage: sign-ups, courses built, activities done, referral clicks.
- [ ] Errors reach Sentry; the site has proper error pages, a privacy page and share previews.

## States and Boundaries
- **First use** — login, then trip setup; no course yet.
- **No course yet** — the main screen sends the user to trip setup.
- **Missed days** — fine; the family continues where it stopped; no activity is skipped (confirmed 2026-10-07).
- **Adults-only family** — kids' items are not in the suggestion, but stay available.
- **Course finished** — all activities done before the trip: the app offers quizzes for practice until the trip (confirmed).
- **After the trip** — highlights replace the "next activity" screen.
- **Other countries** — preview cards only; tapping one shows "coming soon".

## Product Decisions
- Japan only in full; other countries as previews — to show that a little-known country can be unlocked, without building it now.
- Referral links (snack box, children's chopsticks) instead of a store — no payments now.
- Premium modules and real payments: later — "once we build it more".
- Login: none. A guest family lives in the browser: a 400-day cookie, plus a copy of the choices and progress in localStorage that brings the family back when the cookies are cleared (feedback T144, 2026-10-11).
- Reminders a few times a week, not daily — "kids have other activities to do and adults".
- YouTube videos are chosen by the agent and approved by Michael before use.
- Two languages: English and Hebrew, so our 4-year-old can play (Michael's feedback, 2026-10-08). A switch in the header
  changes the language; Hebrew pages run right to left. The Japanese words, their sound and the readings stay the same.

## What We're Building
Everything under **Features and Behavior**, for Japan, on a phone and in a TV web browser.

## Deferred From the POC
From `scope.md > Later`: what to wear, curated video lists, shop/affiliate links beyond the buy-in-advance list, premium
modules and payments, a real LG webOS app, full content for other countries.
