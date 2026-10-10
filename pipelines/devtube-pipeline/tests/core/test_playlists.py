from datetime import UTC, datetime

from devtube_pipeline.core.playlists import (
    filter_playlist_items_by_published_dt,
    to_playlist_item_table_rows,
)


def playlist_payload(
    video_id: str = "vid1",
    published_at: str = "2026-10-05T12:00:00+00:00",
    playlist_id: str = "UUx1",
    channel_id: str = "UCx1",
) -> dict:
    return {
        "items": [
            {
                "snippet": {
                    "playlistId": playlist_id,
                    "title": "Some video",
                    "channelTitle": "Some Channel",
                    "channelId": channel_id,
                },
                "contentDetails": {
                    "videoId": video_id,
                    "videoPublishedAt": published_at,
                },
            }
        ]
    }


class TestToPlaylistItemTableRows:
    def test_extracts_rows_from_payloads(self) -> None:
        ingested_at = datetime(2026, 10, 10, tzinfo=UTC)

        rows = to_playlist_item_table_rows(
            run_id="run-1",
            payloads=[
                playlist_payload(),
                playlist_payload(video_id="vid2", playlist_id="UUx2"),
            ],
            ingested_at=ingested_at,
        )

        assert len(rows) == 2
        row = rows[0]
        assert row.video_id == "vid1"
        assert row.playlist_id == "UUx1"
        assert row.video_title == "Some video"
        assert row.channel_title == "Some Channel"
        assert row.channel_id == "UCx1"
        assert row.run_id == "run-1"
        assert row.video_published_dt == datetime(2026, 10, 5, 12, tzinfo=UTC)
        assert row.ingested_at == ingested_at
        assert rows[1].playlist_id == "UUx2"

    def test_empty_payloads_yield_no_rows(self) -> None:
        rows = to_playlist_item_table_rows(
            run_id="run-1",
            payloads=[{"items": []}, {"items": []}],
            ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
        )
        assert rows == []


class TestFilterPlaylistItemsByPublishedDt:
    def test_keeps_rows_at_or_after_boundary(self) -> None:
        boundary = datetime(2026, 10, 3, tzinfo=UTC)
        ingested_at = datetime(2026, 10, 10, tzinfo=UTC)
        rows = to_playlist_item_table_rows(
            run_id="run-1",
            payloads=[
                playlist_payload(video_id="at-boundary", published_at="2026-10-03T00:00:00+00:00"),
                playlist_payload(video_id="after", published_at="2026-10-04T00:00:00+00:00"),
                playlist_payload(video_id="before", published_at="2026-10-02T00:00:00+00:00"),
            ],
            ingested_at=ingested_at,
        )

        kept = filter_playlist_items_by_published_dt(rows, earliest_published_dt=boundary)

        assert [row.video_id for row in kept] == ["at-boundary", "after"]
