"""The 'steps' activity type: a guided real-world activity, e.g. the chopsticks.

Each step has a kind: text, link, video or record. A step can carry an audience
(child / adult); a step for children shows only when the trip has a child.
"""
import re

YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def video_ok(step):
    """A video renders only when Michael approved it and the id looks like a YouTube id."""
    return bool(step.get("approved") is True and YOUTUBE_ID.match(str(step.get("youtube", ""))))


def visible_steps(data, trip):
    has_child = trip.has_child
    has_adult = trip.has_adult
    out = []
    for step in data.get("steps", []):
        audience = step.get("audience", "all")
        if audience == "child" and not has_child:
            continue
        if audience == "adult" and not has_adult:
            continue
        step = dict(step)
        if step.get("kind") == "video":
            step["show_video"] = video_ok(step)
            if not step["show_video"]:
                # Never let an unapproved id reach the page, not even in an attribute.
                step.pop("youtube", None)
        out.append(step)
    return out
