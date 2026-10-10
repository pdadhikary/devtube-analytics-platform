from pathlib import Path
from urllib.parse import urlparse

_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def extension_for_image(content_type: str | None, url: str) -> str:
    """Resolve the file extension for a thumbnail image.

    Content type wins; the URL path suffix is the fallback; ".jpg" is the
    last resort for thumbnail CDNs.
    """
    if content_type:
        base_type = content_type.split(";", 1)[0].strip().lower()
        extension = _CONTENT_TYPE_EXTENSIONS.get(base_type)
        if extension:
            return extension

    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in _CONTENT_TYPE_EXTENSIONS.values():
        return suffix

    return ".jpg"


def build_thumbnail_object_key(video_id: str, extension: str) -> str:
    """Stable curated key: one canonical thumbnail object per video."""
    return f"thumbnails/video_id={video_id}{extension}"


def build_thumbnail_s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"
