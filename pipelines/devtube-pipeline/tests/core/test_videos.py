from datetime import UTC, datetime

import pytest

from devtube_pipeline.core.videos import (
    filter_videos_by_duration,
    select_best_thumbnail,
    to_video_row,
)

FULL_THUMBNAILS = {
    "default": {
        "url": "https://example.com/thumb_default.jpg",
        "width": 120,
        "height": 90,
    },
    "medium": {
        "url": "https://example.com/thumb_medium.jpg",
        "width": 320,
        "height": 180,
    },
    "high": {
        "url": "https://example.com/thumb_high.jpg",
        "width": 480,
        "height": 360,
    },
    "standard": {
        "url": "https://example.com/thumb_standard.jpg",
        "width": 640,
        "height": 480,
    },
    "maxres": {
        "url": "https://example.com/thumb_maxres.jpg",
        "width": 1280,
        "height": 720,
    },
}


def make_video(
    video_id: str = "vid1",
    duration: str = "PT10M30S",
    tags: list[str] | None = ["rust", "duckdb"],
    description: str | None = "some text",
    statistics: dict | None = {"viewCount": "100", "likeCount": "10", "commentCount": "2"},
    thumbnails: dict | None = None,
) -> dict:
    video = {
        "id": video_id,
        "snippet": {
            "title": "Some video",
            "tags": tags,
            "publishedAt": "2026-10-05T12:00:00+00:00",
            "thumbnails": (
                thumbnails if thumbnails is not None else dict(FULL_THUMBNAILS)
            ),
            "channelId": "UCx1",
            "categoryId": "28",
            "description": description,
        },
        "statistics": statistics if statistics is not None else {},
        "contentDetails": {"duration": duration},
    }
    if statistics is None:
        del video["statistics"]
    return video


class TestToVideoRow:
    def test_parses_all_fields(self) -> None:
        ingested_at = datetime(2026, 10, 10, tzinfo=UTC)

        row = to_video_row(make_video(), run_id="run-1", ingested_at=ingested_at)

        assert row.video_id == "vid1"
        assert row.title == "Some video"
        assert row.tags == ["rust", "duckdb"]
        assert row.published_at == datetime(2026, 10, 5, 12, tzinfo=UTC)
        assert row.duration == 630
        assert row.view_count == 100
        assert row.like_count == 10
        assert row.comment_count == 2
        assert row.thumbnail_url == "https://example.com/thumb_maxres.jpg"
        assert row.thumbnail_width == 1280
        assert row.thumbnail_height == 720
        assert row.channel_id == "UCx1"
        assert row.category_id == "28"
        assert row.description == "some text"
        assert row.s3_uri is None
        assert row.run_id == "run-1"
        assert row.ingested_at == ingested_at

    def test_parses_hours_minutes_seconds_duration(self) -> None:
        row = to_video_row(
            make_video(duration="PT1H2M3S"),
            run_id="run-1",
            ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
        )
        assert row.duration == 3723

    def test_missing_statistics_yields_none_counts(self) -> None:
        row = to_video_row(
            make_video(statistics=None),
            run_id="run-1",
            ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
        )
        assert row.view_count is None
        assert row.like_count is None
        assert row.comment_count is None

    def test_empty_description_and_missing_tags_become_none(self) -> None:
        row = to_video_row(
            make_video(tags=None, description=""),
            run_id="run-1",
            ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
        )
        assert row.description is None
        assert row.tags is None

    def test_uses_best_thumbnail_tier_available(self) -> None:
        ingested_at = datetime(2026, 10, 10, tzinfo=UTC)

        row = to_video_row(
            make_video(
                thumbnails={
                    "default": FULL_THUMBNAILS["default"],
                    "high": FULL_THUMBNAILS["high"],
                }
            ),
            run_id="run-1",
            ingested_at=ingested_at,
        )
        assert row.thumbnail_url == "https://example.com/thumb_high.jpg"
        assert row.thumbnail_width == 480
        assert row.thumbnail_height == 360


class TestSelectBestThumbnail:
    def test_prefers_maxres_when_present(self) -> None:
        assert (
            select_best_thumbnail(dict(FULL_THUMBNAILS)) == FULL_THUMBNAILS["maxres"]
        )

    def test_falls_back_through_preference_order(self) -> None:
        for available in ("standard", "high", "medium", "default"):
            thumbnails = {available: FULL_THUMBNAILS[available]}
            assert select_best_thumbnail(thumbnails) == FULL_THUMBNAILS[available]

    def test_picks_widest_when_only_unknown_qualities(self) -> None:
        thumbnails = {
            "future": {"url": "https://example.com/future.jpg", "width": 2000, "height": 1200},
            "other": {"url": "https://example.com/other.jpg", "width": 800, "height": 600},
        }
        assert select_best_thumbnail(thumbnails)["url"] == (
            "https://example.com/future.jpg"
        )

    def test_empty_thumbnails_raise(self) -> None:
        with pytest.raises(ValueError):
            select_best_thumbnail({})


class TestFilterVideosByDuration:
    def test_filters_shorts_and_long_forms_inclusively(self) -> None:
        ingested_at = datetime(2026, 10, 10, tzinfo=UTC)
        durations = {
            "short": 60,
            "at-shorts-boundary": 90,
            "normal": 300,
            "at-max-boundary": 2700,
            "over-max": 2701,
            "just-under-shorts": 89,
        }
        rows = [
            to_video_row(
                make_video(video_id=video_id, duration=f"PT{seconds}S"),
                run_id="run-1",
                ingested_at=ingested_at,
            )
            for video_id, seconds in durations.items()
        ]

        kept, num_shorts, num_long_forms = filter_videos_by_duration(
            rows, shorts_max_seconds=90, max_duration_seconds=2700
        )

        assert [row.video_id for row in kept] == [
            "at-shorts-boundary",
            "normal",
            "at-max-boundary",
        ]
        assert num_shorts == 2
        assert num_long_forms == 1

    def test_empty_rows(self) -> None:
        kept, num_shorts, num_long_forms = filter_videos_by_duration(
            [], shorts_max_seconds=90, max_duration_seconds=2700
        )
        assert kept == []
        assert num_shorts == 0
        assert num_long_forms == 0
