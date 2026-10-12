"""T191, T233: the Content-Security-Policy.

Every page gets a fresh nonce. Only a <script> tag that carries that nonce runs, so an injected script
cannot run and cannot read the link token in localStorage. 'strict-dynamic' lets a nonced script (the
Sentry loader) add its own scripts. 'unsafe-inline' and https: are only for old browsers with no nonce
support; a modern browser ignores them once a nonce is in the rule.
"""
import secrets

POLICY = "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
SCRIPT_POLICY = "script-src 'nonce-{nonce}' 'strict-dynamic' https: 'unsafe-inline'"
# Django's admin has its own inline scripts with no nonce: it keeps the old policy.
NO_NONCE_PREFIXES = ("/admin/",)
# A family photo or clip: the browser shows it as a file and runs nothing in it.
FILE_POLICY = "default-src 'none'; media-src 'self'; img-src 'self'; sandbox"


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        if request.path.startswith(NO_NONCE_PREFIXES):
            policy = POLICY
        else:
            policy = POLICY + "; " + SCRIPT_POLICY.format(nonce=request.csp_nonce)
        response.headers.setdefault("Content-Security-Policy", policy)
        return response


def csp_nonce(request):
    """The nonce for every <script> tag in a template: <script nonce="{{ csp_nonce }}">."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}


def private_file(response):
    """Headers for a family upload served back to the family."""
    response["Content-Security-Policy"] = FILE_POLICY
    response["Content-Disposition"] = "inline"
    return response
