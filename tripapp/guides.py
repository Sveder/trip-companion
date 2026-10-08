"""The country guide (Michael, feedback T87): each country can have its own guide animal.
The guide shows on that country's screens only. App-wide screens use the neutral mark."""
from trips.models import active_trip

# destination -> template of the guide's artwork
GUIDES = {
    "japan": "includes/guides/japan.html",
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
    return {"country_guide": guide}
