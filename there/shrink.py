"""Shrink a phone photo before it is stored: upright, 1600 px on the long side, JPEG, no EXIF (no GPS)."""
import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

LONG_SIDE = 1600
QUALITY = 82


def shrink(data):
    """Return (jpeg_bytes, width, height), or None when Pillow cannot read the file (for example HEIC)."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        background = Image.new("RGB", img.size, "white")
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    img.thumbnail((LONG_SIDE, LONG_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return out.getvalue(), img.width, img.height


def shrink_upload(upload):
    """An upload as a small JPEG ContentFile with its content type, or the upload as it is."""
    upload.seek(0)
    small = shrink(upload.read())
    upload.seek(0)
    if small is None:
        return upload, None
    return ContentFile(small[0], name="photo.jpg"), "image/jpeg"
