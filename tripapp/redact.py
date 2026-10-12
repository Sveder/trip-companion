"""T191: the continue-on-another-device link opens a family. Its token must not land in a log.

`redact` hides it (and the reminder stop token) in a path or a URL. gunicorn's access log uses
`RedactingLogger` (deploy/trip.service), Sentry uses `scrub_event` (settings.py), and nginx does not log
those paths at all (deploy/nginx-trip.conf).
"""
import re

from gunicorn.glogging import Logger

SECRET_PATH = re.compile(r"/(continue|reminders/stop)/[^/?#\s]+")


def redact(text):
    return SECRET_PATH.sub(r"/\1/<token>", text) if isinstance(text, str) else text


class RedactingLogger(Logger):
    def atoms(self, resp, req, environ, request_time):
        atoms = super().atoms(resp, req, environ, request_time)
        # Every atom: the request line, the path, the referer and the request headers.
        return {key: redact(value) for key, value in atoms.items()}


def scrub_event(event, hint=None):
    """Sentry before_send: no link token in the request URL, the transaction name or the breadcrumbs."""
    request = event.get("request") or {}
    for key in ("url", "query_string"):
        if key in request:
            request[key] = redact(request[key])
    headers = request.get("headers") or {}
    if "Referer" in headers:
        headers["Referer"] = redact(headers["Referer"])
    if "transaction" in event:
        event["transaction"] = redact(event["transaction"])
    for crumb in (event.get("breadcrumbs") or {}).get("values", []):
        if "message" in crumb:
            crumb["message"] = redact(crumb["message"])
        data = crumb.get("data") or {}
        for key in ("url", "to", "from"):
            if key in data:
                data[key] = redact(data[key])
    return event
