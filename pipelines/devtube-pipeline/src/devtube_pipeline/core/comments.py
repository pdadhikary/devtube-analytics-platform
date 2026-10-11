from datetime import datetime
from typing import Any

import structlog

from devtube_pipeline.models import CommentThreadTableRow

logger = structlog.get_logger(__name__)


def _to_comment_row(
    comment: dict[str, Any],
    video_id: str,
    parent_comment_id: str | None,
    total_reply_count: int,
    run_id: str,
    ingested_at: datetime,
) -> CommentThreadTableRow:
    snippet = comment["snippet"]
    author_channel_id: dict[str, Any] = snippet.get("authorChannelId") or {}

    return CommentThreadTableRow(
        run_id=run_id,
        comment_id=comment["id"],
        video_id=video_id,
        parent_comment_id=parent_comment_id,
        total_reply_count=total_reply_count,
        author_name=snippet.get("authorDisplayName"),
        author_channel_id=author_channel_id.get("value"),
        like_count=int(snippet.get("likeCount", 0) or 0),
        text_original=snippet.get("textOriginal"),
        published_at=snippet.get("publishedAt"),
        updated_at=snippet.get("updatedAt"),
        ingested_at=ingested_at,
    )


def to_comment_rows(
    run_id: str, payloads: list[dict[str, Any]], ingested_at: datetime
) -> list[CommentThreadTableRow]:
    table_rows: list[CommentThreadTableRow] = []

    for payload in payloads:
        for thread in payload.get("items", []):
            thread_snippet = thread["snippet"]
            video_id = thread_snippet["videoId"]
            total_reply_count = int(thread_snippet.get("totalReplyCount", 0) or 0)

            top_level_comment = thread_snippet["topLevelComment"]
            table_rows.append(
                _to_comment_row(
                    comment=top_level_comment,
                    video_id=video_id,
                    parent_comment_id=None,
                    total_reply_count=total_reply_count,
                    run_id=run_id,
                    ingested_at=ingested_at,
                )
            )

            for reply in thread.get("replies", {}).get("comments", []):
                table_rows.append(
                    _to_comment_row(
                        comment=reply,
                        video_id=video_id,
                        parent_comment_id=top_level_comment["id"],
                        total_reply_count=0,
                        run_id=run_id,
                        ingested_at=ingested_at,
                    )
                )

    logger.info(
        "comment_threads.payload_row_extraction_success",
        payload_count=len(payloads),
        row_count=len(table_rows),
    )
    return table_rows
