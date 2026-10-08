"""The 'lesson' activity type: a course of 10-20 short pages, one screen each.

Page kinds:
  text   a picture and a few lines
  spots  a picture with dots: tap a dot to learn what that part is
  flip   cards that turn over when tapped
  pick   a game: rounds of "tap the right picture"
  train  a game: plates ride past on a sushi train, catch the one asked for
  video  a YouTube video, only when Michael approved it; else its written lines
  local  places to try it: at home and in Japan

A page can carry an audience (child / adult), like a step.
"""
from .steps import video_ok

KINDS = ("text", "spots", "flip", "pick", "train", "video", "local")


def visible_pages(data, trip):
    out = []
    for page in data.get("pages", []):
        audience = page.get("audience", "all")
        if audience == "child" and not trip.has_child:
            continue
        if audience == "adult" and not trip.has_adult:
            continue
        page = dict(page)
        if page.get("kind") not in KINDS:
            continue
        if page["kind"] == "video":
            page["show_video"] = video_ok(page)
            if not page["show_video"]:
                # Never let an unapproved id reach the page, not even in an attribute.
                page.pop("youtube", None)
        if page["kind"] in ("pick", "train"):
            pics = {p["id"]: p for p in data.get("pictures", [])}
            page["rounds"] = [dict(r, choices=[pics[c] for c in r.get("choices", []) if c in pics]) for r in page.get("rounds", [])]
            page["belt"] = [pics[c] for c in page.get("belt", []) if c in pics]
        out.append(page)
    return out
