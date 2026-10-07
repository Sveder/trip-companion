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

1. **Log in** — a simple email login, or Google sign-in.
2. **Tell the app about the trip** — where (Japan; other countries show as "coming soon"), how big the family is, and the ages.
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
- **Trip setup** — destination, family size, ages.
- **Course builder** — the suggested course, the module list with add/remove, and the "build" action.
- **Today / next activity** — the main screen after the course exists; opens the next activity.
- **Activity screen** — the steps of one activity (video, practice, game, test).
- **Quiz / practice.**
- **Country preview cards** — Uzbekistan and others, "coming soon".
- **After the trip** — highlights.

Works on a phone and in the TV's web browser (big, readable, remote-friendly on the TV). Source: `scope.md > The POC Boundary`.

## Look and Feel
- Kid friendly, bright and game-like, like Matific (https://www.matific.com/). Source: `scope.md > Inspiration & Identity`.
- Place facts in the spirit of Geography Now (https://www.youtube.com/@GeographyNow).
- Mood: excitement, "ready and pumped".
- **Pending (asked 2026-10-07 18:00):** our 4-year-old's answers — the guide animal, the colour, what happens when you finish a game —
  and Michael's own direction on colours, letters, a guide character, and anything to avoid.

## Features and Behavior

### Login
- [ ] A new user can sign in with an email login or with Google, and lands on trip setup.
- [ ] A returning user lands on "today / next activity".

### Trip setup and course builder
- [ ] The user picks Japan; other countries appear as "coming soon" cards and cannot be built.
- [ ] The user sets family size and ages.
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
2. A how-to video from YouTube. The agent proposes it; Michael approves it before it ships.
3. Watch the video and practise with real chopsticks.
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

### After the trip
- [ ] After the trip dates, the app shows trip highlights.

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
- Login: simple email, or Google.
- Reminders a few times a week, not daily — "kids have other activities to do and adults".
- YouTube videos are chosen by the agent and approved by Michael before use.

## What We're Building
Everything under **Features and Behavior**, for Japan, on a phone and in a TV web browser.

## Deferred From the POC
From `scope.md > Later`: what to wear, curated video lists, shop/affiliate links beyond the buy-in-advance list, premium
modules and payments, a real LG webOS app, full content for other countries.
