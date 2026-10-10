from datetime import UTC, datetime

from devtube_pipeline.core.videos import (
    filter_videos_by_duration,
    to_video_row,
)


def make_video(
    video_id: str = "vid1",
    duration: str = "PT10M30S",
    tags: list[str] | None = ["rust", "duckdb"],
    description: str | None = "some text",
    statistics: dict | None = {"viewCount": "100", "likeCount": "10", "commentCount": "2"},
) -> dict:
    video = {
        "id": video_id,
        "snippet": {
            "title": "Some video",
            "tags": tags,
            "publishedAt": "2026-10-05T12:00:00+00:00",
            "thumbnails": {
                "default": {
                    "url": "https://example.com/thumb.jpg",
                    "width": 120,
                    "height": 90,
                }
            },
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
        assert row.thumbnail_url == "https://example.com/thumb.jpg"
        assert row.thumbnail_width == 120
        assert row.thumbnail_height == 90
        assert row.channel_id == "UCx1"
        assert row.category_id == "28"
        assert row.description == "some text"
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
