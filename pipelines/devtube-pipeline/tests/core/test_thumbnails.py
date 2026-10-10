from devtube_pipeline.core.thumbnails import (
    build_thumbnail_object_key,
    build_thumbnail_s3_uri,
    extension_for_image,
)


class TestExtensionForImage:
    def test_content_type_takes_priority(self) -> None:
        assert (
            extension_for_image("image/jpeg", "https://i.ytimg.com/vi/v1/maxresdefault.jpg")
            == ".jpg"
        )
        assert (
            extension_for_image("image/webp; charset=binary", "https://i.ytimg.com/vi/v1/hqdefault.jpg")
            == ".webp"
        )
        assert (
            extension_for_image("image/png", "https://i.ytimg.com/vi/v1/maxresdefault.jpg")
            == ".png"
        )

    def test_falls_back_to_url_suffix_when_no_content_type(self) -> None:
        assert (
            extension_for_image(None, "https://i.ytimg.com/vi/v1/maxresdefault.jpg")
            == ".jpg"
        )
        assert (
            extension_for_image(None, "https://i.ytimg.com/vi/v1/hqdefault.webp?sqp=xyz")
            == ".webp"
        )

    def test_unknown_content_type_uses_url_suffix(self) -> None:
        assert (
            extension_for_image("text/html", "https://i.ytimg.com/vi/v1/maxresdefault.jpg")
            == ".jpg"
        )

    def test_defaults_to_jpg(self) -> None:
        assert extension_for_image(None, "https://i.ytimg.com/vi/v1/noextension") == ".jpg"
        assert extension_for_image("text/html", "https://i.ytimg.com/vi/v1/noextension") == ".jpg"


class TestThumbnailKeys:
    def test_builds_object_key(self) -> None:
        key = build_thumbnail_object_key("vid1", ".jpg")
        assert key == "thumbnails/video_id=vid1.jpg"

    def test_builds_s3_uri(self) -> None:
        uri = build_thumbnail_s3_uri("devtube-lakehouse", "thumbnails/video_id=vid1.jpg")
        assert uri == "s3://devtube-lakehouse/thumbnails/video_id=vid1.jpg"
