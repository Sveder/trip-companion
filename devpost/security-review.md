# Security and code review (T191, 2026-10-12)

Michael asked for one review run before more features. Each check below gives the result and the fix.
The tests for the fixes are in `tripapp/test_security.py` (17 tests). The full suite: 418 tests, all pass, none skipped.

## 1. Dependencies

| Check | Result |
|---|---|
| Every package in `requirements.txt` is the real PyPI package | Pass. All 10 names are the well-known projects (Django, django-allauth, boto3, gunicorn, python-dotenv, PyYAML, ruamel.yaml, sentry-sdk, polib, Pillow). No look-alike names. |
| Every package is pinned | Pass. Every line uses `==`. |
| Known vulnerabilities (osv.dev batch query, all 28 installed packages, 2026-10-12) | Pass for every runtime package. `pip 24.0` in the venv had 12 advisories. pip is a tool, not part of the app. Fix: upgraded pip in the local and the server venv. |
| Third-party JavaScript | Pass. All scripts are local files, except the Sentry loader (`SENTRY_JS_LOADER`, js.sentry-cdn.com) and the YouTube-nocookie iframe for an approved video. Both are expected. |

## 2. Django settings

| Check | Result |
|---|---|
| DEBUG off in production | Pass. The server `.env` sets `DJANGO_DEBUG`; a 404 on the live site shows no debug page. |
| SECRET_KEY from the environment | Pass. The server key comes from `.env`. With DEBUG off and no key set, the app now refuses to start (it never runs on the dev key). |
| CSRF on every POST | Pass. `CsrfViewMiddleware` is on and no view uses `csrf_exempt` (a test checks this). |
| Secure cookies, HSTS, nosniff | Pass. Session and CSRF cookies are `Secure` and `SameSite=Lax`; HSTS 30 days with subdomains; `X-Content-Type-Options: nosniff`. |
| X-Frame-Options | Pass. `DENY`, sent once. Since T231 the trip nginx block sets X-Frame-Options, X-Content-Type-Options and Referrer-Policy itself (DENY, nosniff, same-origin), so the global `conf.d/security.conf` values do not reach this site, and it hides the Django copies. |
| CSP | Added. `object-src 'none'; base-uri 'self'; frame-ancestors 'none'` on every page (`tripapp/security.py`). A `script-src` rule needs nonces for the inline scripts first; not done in this run. |
| `manage.py check --deploy` | Pass, no warnings with production settings (a test runs it). |

## 3. The no-login code

| Check | Result |
|---|---|
| The continue link token is long and random | Pass. `secrets.token_urlsafe(32)`: 256 bits, 43 characters. A test checks length, charset and uniqueness. |
| The token is not logged | **Fixed.** The gunicorn access log held one full link (the system journal, 7 days). Now gunicorn uses `tripapp.redact.RedactingLogger`, nginx does not log `/continue/<token>/` or `/reminders/stop/<token>/`, and Sentry events go through `scrub_event`. The one old line stays in the journal until journald rotates it. |
| No IDOR | Pass. Every URL with an id filters on `trip__user=request.user`. `state.json` takes no id and returns the caller's own family only. A test sends every id URL from another family and gets 404. |
| Rate limit on the continue mail | **Fixed.** The limit (3 per family, 10 per IP address per hour) read `X-Real-IP`, but nginx did not set that header. A browser could send its own value and skip the IP limit. nginx now sets `X-Real-IP $remote_addr`. |
| Rate limit on the sign-in code mail | **Fixed.** `/signin/` called allauth's code flow directly, so allauth's own limit did not run. It also made a new account for ANY address and mailed it a code. Now: no new accounts, no mail to an unknown address (`ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`, the page looks the same, so it does not tell who has an account), 3 codes per address and 10 per IP address per hour. Only staff and the old email families use this page. |
| Uploads: type and size | Pass, with one fix. Photos: image types only (no SVG), 25 MB, then shrunk by Pillow. Clips: webm/mp4/mov only, 40 MB. **Added:** a cap per trip (300 photos, 60 clips), so one browser cannot fill the disk. |
| Uploads: served safely | **Fixed.** Files live in `private/`, not in `/media/`, and only the owner gets them. Now each file answer also has `Content-Security-Policy: default-src 'none'; sandbox` and `Content-Disposition: inline`, so a file with a false type cannot run a script. |

## 4. Secrets

| Check | Result |
|---|---|
| Secrets in the repo or in its history (249 commits) | Pass. A search of every diff for AWS keys, private keys, Django keys, OAuth secrets, Sentry tokens and GitHub tokens found nothing. No `.env`, key or database file was ever committed. |
| Files that could leak next | **Fixed.** `devpost/.aiopylgtv.sqlite` (the LG TV pairing key from the TV test) was untracked but not ignored. `.gitignore` now lists it. |

## 5. Code quality

| Check | Result |
|---|---|
| Dead code from the old login | **Fixed.** `user_for_email` no longer makes accounts; `make_account` does that for `manage.py make_superuser` only. The empty `content_admin/views.py` is gone. |
| Failing or skipped tests | Pass. 418 tests, 0 failures, 0 skipped. Tests now use a memory cache: before, the rate-limit tests cleared the dev server's file cache. |
| pyflakes | **Fixed.** 6 unused imports removed. One stays on purpose: `analytics/apps.py` imports `.signals` to connect the signal handlers. |

## Open risks (not fixed in this run)

- Every browser with no cookie that opens a family page makes a guest account. A crawler can make many. Today: 143 guest families, 41 with no trip. A cleanup job for old empty guests would keep the table small.
- The continue link token never changes. A family cannot cancel a link they mailed to a wrong address. A "new link" button would fix this.
- The link token is also in the browser copy (`localStorage`), so a script injection on the site would expose it. The strict CSP above (`script-src` with nonces) is the next step against that.
- The admin sign-in check counts failed codes per IP with allauth, which sees nginx's address (127.0.0.1). The limit is site-wide, which is safe but strict.
