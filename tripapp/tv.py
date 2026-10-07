"""TV mode: a big, remote-friendly layout for the TV's web browser.

On when the URL has ?tv=1 (remembered in the session, ?tv=0 turns it off) or
when the browser says it is a smart TV (LG webOS, Tizen and others).
"""
import re

TV_AGENTS = re.compile(r"Web0S|webOS|SmartTV|SMART-TV|Tizen|NetCast|HbbTV|BRAVIA|AFT[A-Z]", re.I)


class TvModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        flag = request.GET.get("tv")
        if flag in ("0", "1") and hasattr(request, "session"):
            request.session["tv"] = flag == "1"
        stored = request.session.get("tv") if hasattr(request, "session") else None
        if stored is None:
            stored = bool(TV_AGENTS.search(request.headers.get("User-Agent", "")))
        request.tv_mode = stored
        return self.get_response(request)


def tv_mode(request):
    return {"tv_mode": getattr(request, "tv_mode", False)}
