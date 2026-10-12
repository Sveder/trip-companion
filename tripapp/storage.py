"""Static file storage for production (T229)."""
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class HashedStaticStorage(ManifestStaticFilesStorage):
    """Every static URL carries a content hash (app.3f2a91c0.css), so nginx can cache /static/ for a year.

    Not strict: a file that is missing from the manifest keeps its plain name instead of a 500 page.
    """

    manifest_strict = False
