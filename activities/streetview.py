"""The 'streetview' activity type: a 360° photo of a real place and a list of things to spot.

The Google Maps embed needs no API key. It takes a point and opens the Street View photo nearest to it.
The embed cannot tell the page what is on screen, so the family ticks each find by hand.
"""
from urllib.parse import quote

EMBED = "https://www.google.com/maps/embed?pb=!6m7!1m6!2m2!1d{lat}!2d{lng}!3f{heading}!4f0!5f1"
MAPS_LINK = "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}&heading={heading}"


def _point(data):
    lat = float(data["lat"])
    lng = float(data["lng"])
    heading = float(data.get("heading", 0)) % 360
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("lat/lng out of range")
    return {"lat": f"{lat:.7f}", "lng": f"{lng:.7f}", "heading": f"{heading:g}"}


def embed_url(data):
    return EMBED.format(**_point(data))


def maps_link(data):
    return MAPS_LINK.format(**{k: quote(v) for k, v in _point(data).items()})


def all_found(data, found):
    """found: the spot numbers the family ticked (strings from the form)."""
    wanted = {str(i) for i in range(len(data.get("spots", [])))}
    return bool(wanted) and wanted <= set(found)
