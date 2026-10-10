import httpx
import pytest

from devtube_pipeline.media import fetch_image


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_image_returns_bytes_and_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"\xff\xd8fake-jpeg-bytes",
            headers={"content-type": "image/jpeg"},
        )

    image = fetch_image(
        make_client(handler), "https://i.ytimg.com/vi/vid1/maxresdefault.jpg"
    )

    assert image.data == b"\xff\xd8fake-jpeg-bytes"
    assert image.content_type == "image/jpeg"


def test_fetch_image_handles_missing_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"whatever")

    image = fetch_image(
        make_client(handler), "https://i.ytimg.com/vi/vid1/maxresdefault.jpg"
    )

    assert image.content_type is None


def test_fetch_image_raises_on_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPError):
        fetch_image(
            make_client(handler), "https://i.ytimg.com/vi/vid1/maxresdefault.jpg"
        )
