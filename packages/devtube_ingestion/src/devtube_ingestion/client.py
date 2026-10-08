from collections.abc import Iterator
from contextlib import contextmanager

from httpx import Client

from devtube_ingestion.settings import settings


def build_youtube_client() -> Client:
    return Client(
        base_url=str(settings.youtube_api_base),
        params={"key": settings.youtube_api_key},
        timeout=20.0,
    )


@contextmanager
def get_youtube_client() -> Iterator[Client]:
    client = build_youtube_client()
    try:
        yield client
    finally:
        client.close()
