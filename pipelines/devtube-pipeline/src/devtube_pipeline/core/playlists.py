from datetime import datetime
from typing import Any

import structlog

from devtube_pipeline.models import PlaylistItemTableRow
from devtube_pipeline.utils import parse_iso_to_datetime

logger = structlog.get_logger(__name__)


def to_playlist_item_table_rows(
    run_id: str, payloads: list[dict[str, Any]], ingested_at: datetime
) -> list[PlaylistItemTableRow]:
    table_rows: list[PlaylistItemTableRow] = []
    for payload in payloads:
        for item in payload["items"]:
            snippet = item["snippet"]
            details = item["contentDetails"]

            row = PlaylistItemTableRow(
                video_id=details["videoId"],
                playlist_id=snippet["playlistId"],
                video_title=snippet["title"],
                run_id=run_id,
                channel_title=snippet["channelTitle"],
                channel_id=snippet["channelId"],
                video_published_dt=parse_iso_to_datetime(
                    details["videoPublishedAt"]
                ),
                ingested_at=ingested_at,
            )

            table_rows.append(row)
    logger.info(
        "playlist_items.payload_row_extraction_success",
        payload_count=len(payloads),
        row_count=len(table_rows),
    )
    return table_rows


def filter_playlist_items_by_published_dt(
    rows: list[PlaylistItemTableRow], earliest_published_dt: datetime
) -> list[PlaylistItemTableRow]:
    result = [row for row in rows if row.video_published_dt >= earliest_published_dt]
    logger.info(
        "playlist_items.row_filter_success",
        incoming_row_count=len(rows),
        filtered_row_count=len(result),
        discarded_row_count=len(rows) - len(result),
    )
    return result
