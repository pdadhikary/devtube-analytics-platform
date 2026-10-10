from collections.abc import Iterator
from datetime import datetime
from typing import Any

import isodate
import structlog

from devtube_pipeline.models import VideoTableRow

logger = structlog.get_logger(__name__)


def batched_video_ids(video_ids: list[str], batch_size: int = 50) -> Iterator[list[str]]:
    for i in range(0, len(video_ids), batch_size):
        yield video_ids[i : i + batch_size]


def to_video_row(
    video: dict[str, Any], run_id: str, ingested_at: datetime
) -> VideoTableRow:
    snippet = video["snippet"]
    statistics = video.get("statistics", {})
    thumbnail = snippet["thumbnails"]["default"]
    return VideoTableRow(
        video_id=video["id"],
        title=snippet["title"],
        tags=snippet.get("tags"),
        published_at=snippet["publishedAt"],
        duration=int(
            isodate.parse_duration(video["contentDetails"]["duration"]).total_seconds()
        ),
        view_count=statistics.get("viewCount"),
        like_count=statistics.get("likeCount"),
        comment_count=statistics.get("commentCount"),
        thumbnail_url=thumbnail["url"],
        thumbnail_width=thumbnail["width"],
        thumbnail_height=thumbnail["height"],
        channel_id=snippet["channelId"],
        category_id=snippet["categoryId"],
        description=snippet.get("description") or None,
        run_id=run_id,
        ingested_at=ingested_at,
    )


def filter_videos_by_duration(
    rows: list[VideoTableRow], shorts_max_seconds: int, max_duration_seconds: int
) -> tuple[list[VideoTableRow], int, int]:
    shorts = [row for row in rows if row.duration < shorts_max_seconds]
    long_forms = [row for row in rows if row.duration > max_duration_seconds]
    kept = [
        row
        for row in rows
        if shorts_max_seconds <= row.duration <= max_duration_seconds
    ]
    logger.info(
        "videos.duration_filter_success",
        incoming_row_count=len(rows),
        kept_row_count=len(kept),
        shorts_discarded_count=len(shorts),
        long_forms_discarded_count=len(long_forms),
    )
    return kept, len(shorts), len(long_forms)
