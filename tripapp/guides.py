"""The country guide (Michael, feedback T87): each country can have its own guide animal.
The guide shows on that country's screens only. App-wide screens use the neutral mark."""
from trips.models import active_trip

# destination -> template of the guide's artwork
GUIDES = {
    "japan": "includes/guides/japan.html",
    "uzbekistan": "includes/guides/uzbekistan.html",  # T234: Tuya the camel
}


def country_guide(request):
    """The guide template for the family's active trip, or "" with no trip or no guide.
    Lazy: the trip is read only when a template asks for the guide, and only once per request."""
    def guide():
        if not hasattr(request, "_country_guide"):
            user = getattr(request, "user", None)
            trip = active_trip(user) if user is not None and user.is_authenticated else None
            request._country_guide = GUIDES.get(trip.destination, "") if trip else ""
        return request._country_guide

    def country():
        """T171: the trip's place, for the lines that name it. 'other' is True for a trip that is not to Japan:
        those screens say the place's name and hide the Japan-only photo hunt."""
        if not hasattr(request, "_trip_country"):
            from content_admin.i18n import localize
            from content_admin.loader import load_previews

            user = getattr(request, "user", None)
            trip = active_trip(user) if user is not None and user.is_authenticated else None
            place = next((p for p in localize(load_previews()) if trip and p["id"] == trip.destination), None)
            request._trip_country = {"id": trip.destination, "name": place["name"] if place else trip.destination,
                                     "other": trip.destination != "japan"} if trip else {}
        return request._trip_country
    return {"country_guide": guide, "trip_country": country}
