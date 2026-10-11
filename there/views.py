from django.conf import settings
from django.contrib import messages
from accounts.guest import family_required
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from analytics.models import track
from content_admin.i18n import localize
from courses.highlights import trip_phase
from trips.models import active_trip

from .models import Photo
from .shrink import shrink_upload
from .things import KEYS, THINGS

PHOTO_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
               "image/heic": "heic", "image/heif": "heif", "image/gif": "gif"}


def things_with_photos(trip):
    """The hunt list in the active language, each thing with the photos the family took of it."""
    photos = {}
    for p in Photo.objects.filter(trip=trip):
        photos.setdefault(p.thing, []).append(p)
    rows = [{**localize(t), "photos": photos.get(t["key"], [])} for t in THINGS]
    return rows


@family_required
def hunt(request):
    """'While we are there': a list of things to find in Japan. A photo of a thing ticks it off."""
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    rows = things_with_photos(trip)
    track("hunt_opened", trip=trip)
    return render(request, "there/hunt.html", {
        "trip": trip, "things": rows, "phase": trip_phase(trip),
        "found": sum(1 for r in rows if r["photos"]), "total": len(rows)})


@family_required
@require_POST
def add_photo(request, thing):
    trip = active_trip(request.user)
    if trip is None:
        return redirect("trip_setup")
    if thing not in KEYS:
        raise Http404("No such thing.")
    upload = request.FILES.get("photo")
    if upload is None or upload.size == 0:
        return HttpResponseBadRequest("No photo.")
    if upload.size > settings.PHOTO_MAX_BYTES:
        return HttpResponseBadRequest("The photo is too big.")
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type not in PHOTO_TYPES:
        return HttpResponseBadRequest("Not a photo.")
    upload.name = f"photo.{PHOTO_TYPES[content_type]}"
    stored, small_type = shrink_upload(upload)
    content_type = small_type or content_type
    first = not Photo.objects.filter(trip=trip, thing=thing).exists()
    Photo.objects.create(trip=trip, thing=thing, file=stored, content_type=content_type, size=stored.size)
    track("photo_saved", trip=trip, thing=thing, size=upload.size, stored=stored.size)
    messages.success(request, _("Great find! 📸") if first else _("One more photo! 📸"))
    return redirect(reverse("there") + f"#{thing}")


@family_required
def photo_file(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id, trip__user=request.user)
    response = FileResponse(photo.file.open("rb"), content_type=photo.content_type)
    response["Cache-Control"] = "private, max-age=86400"
    return response


@family_required
@require_POST
def delete_photo(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id, trip__user=request.user)
    thing = photo.thing
    photo.file.delete(save=False)
    photo.delete()
    return redirect(reverse("there") + f"#{thing}")
