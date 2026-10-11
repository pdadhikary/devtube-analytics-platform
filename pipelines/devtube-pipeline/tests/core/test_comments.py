from datetime import UTC, datetime

from devtube_pipeline.core.comments import to_comment_rows


def comment(
    comment_id: str = "c1",
    author_name: str = "Alice",
    author_channel_id: str | None = "UCa",
    like_count: int | None = 3,
    text: str = "hello",
    published_at: str = "2026-10-01T10:00:00+00:00",
    updated_at: str = "2026-10-01T10:00:00+00:00",
) -> dict:
    snippet: dict = {
        "authorDisplayName": author_name,
        "likeCount": like_count,
        "textOriginal": text,
        "publishedAt": published_at,
        "updatedAt": updated_at,
    }
    if author_channel_id is not None:
        snippet["authorChannelId"] = {"value": author_channel_id}
    return {"id": comment_id, "snippet": snippet}


def thread_payload(
    video_id: str = "vid1",
    total_reply_count: int = 0,
    top: dict | None = None,
    replies: list[dict] | None = None,
) -> dict:
    item: dict = {
        "id": "thread-1",
        "snippet": {
            "videoId": video_id,
            "totalReplyCount": total_reply_count,
            "topLevelComment": top or comment(),
        },
    }
    if replies is not None:
        item["replies"] = {"comments": replies}
    return {"items": [item]}


class TestToCommentRows:
    def test_extracts_top_level_comment_fields(self) -> None:
        ingested_at = datetime(2026, 10, 10, tzinfo=UTC)

        rows = to_comment_rows(
            run_id="run-1",
            payloads=[thread_payload(total_reply_count=7)],
            ingested_at=ingested_at,
        )

        assert len(rows) == 1
        row = rows[0]
        assert row.run_id == "run-1"
        assert row.comment_id == "c1"
        assert row.video_id == "vid1"
        assert row.parent_comment_id is None
        assert row.total_reply_count == 7
        assert row.author_name == "Alice"
        assert row.author_channel_id == "UCa"
        assert row.like_count == 3
        assert row.text_original == "hello"
        assert row.published_at == datetime(2026, 10, 1, 10, tzinfo=UTC)
        assert row.updated_at == datetime(2026, 10, 1, 10, tzinfo=UTC)
        assert row.ingested_at == ingested_at

    def test_replies_reference_parent_and_inherit_video(self) -> None:
        rows = to_comment_rows(
            run_id="run-1",
            payloads=[
                thread_payload(
                    video_id="vid1",
                    total_reply_count=2,
                    top=comment(comment_id="top-1"),
                    replies=[
                        comment(comment_id="reply-1", author_name="Bob"),
                        comment(comment_id="reply-2", author_name="Carol"),
                    ],
                )
            ],
            ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
        )

        assert [row.comment_id for row in rows] == ["top-1", "reply-1", "reply-2"]
        assert all(row.video_id == "vid1" for row in rows)
        assert [row.parent_comment_id for row in rows] == [None, "top-1", "top-1"]
        assert [row.total_reply_count for row in rows] == [2, 0, 0]
        assert rows[1].author_name == "Bob"

    def test_defaults_when_optional_fields_missing(self) -> None:
        rows = to_comment_rows(
            run_id="run-1",
            payloads=[
                thread_payload(
                    top=comment(like_count=None, author_channel_id=None)
                )
            ],
            ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
        )

        assert rows[0].like_count == 0
        assert rows[0].author_channel_id is None

    def test_empty_payloads_yield_no_rows(self) -> None:
        rows = to_comment_rows(
            run_id="run-1",
            payloads=[{"items": []}, {"items": []}],
            ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
        )
        assert rows == []
