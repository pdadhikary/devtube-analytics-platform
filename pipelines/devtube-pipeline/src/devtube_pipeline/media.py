from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ImagePayload:
    data: bytes
    content_type: str | None


def fetch_image(image_client: httpx.Client, url: str) -> ImagePayload:
    response = image_client.get(url)
    response.raise_for_status()
    return ImagePayload(
        data=response.content,
        content_type=response.headers.get("content-type"),
    )
