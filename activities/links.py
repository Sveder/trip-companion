"""The 'links' activity type (buy in advance) and the referral click hook.

Every shop link on the site goes through /go/<item>/<link id>/. The view counts the
click, then sends the browser on. Only URLs that are in the content can be reached,
so /go/ is not an open redirect.
"""


def _audience_ok(entry, trip):
    audience = entry.get("audience", "all")
    if audience == "child":
        return trip.has_child
    if audience == "adult":
        return trip.has_adult
    return True


def visible_links(data, trip):
    return [link for link in data.get("links", []) if _audience_ok(link, trip)]


def find_link(activity, link_id):
    """The URL of one link in an activity (a `links` item, a `link` step or a lesson page link), or None."""
    data = activity.data or {}
    entries = list(data.get("links", []))
    entries += [s for s in data.get("steps", []) if s.get("kind") == "link"]
    entries += [p["link"] for p in data.get("pages", []) if isinstance(p.get("link"), dict)]
    for entry in entries:
        if entry.get("id") == link_id and str(entry.get("url", "")).startswith("https://"):
            return entry["url"]
    return None
