"""T191: a small Content-Security-Policy that cannot break a page.

The pages use inline scripts and the Sentry loader, so a script-src rule needs nonces first. These rules
only stop plugins, a changed <base>, and framing by another site.
"""
POLICY = "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
# A family photo or clip: the browser shows it as a file and runs nothing in it.
FILE_POLICY = "default-src 'none'; media-src 'self'; img-src 'self'; sandbox"


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", POLICY)
        return response


def private_file(response):
    """Headers for a family upload served back to the family."""
    response["Content-Security-Policy"] = FILE_POLICY
    response["Content-Disposition"] = "inline"
    return response
