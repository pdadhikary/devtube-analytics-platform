from datetime import datetime
from typing import Any

import httpx
import structlog

from devtube_pipeline.models import PlaylistItemTableRow
from devtube_pipeline.settings import settings
from devtube_pipeline.utils import parse_iso_to_datetime

logger = structlog.get_logger(__name__)


def fetch_recently_uploaded_playlist_items(
    run_id: str, channel_ids: list[str], yt_client: httpx.Client
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for channel_id in channel_ids:
        recently_uploaded_playlistId = channel_id.replace("C", "U", 1)

        logger.info(
            "playlist_items.yt_playload_ingestion_started",
            run_id=run_id,
            playlist_id=recently_uploaded_playlistId,
            channel_id=channel_id,
        )

        response = yt_client.get(
            "/playlistItems",
            params={
                "part": "id,snippet,contentDetails",
                "playlistId": recently_uploaded_playlistId,
                "maxResults": settings.max_videos_per_channel,
            },
        )

        if response.status_code != 200:
            logger.error(
                "playlist_items.yt_payload_ingestion_failed",
                run_id=run_id,
                status_code=response.status_code,
                response_text=response.text[:200],
                endpoint=response.url.path,
                playlist_id=recently_uploaded_playlistId,
                channel_id=channel_id,
            )
            continue

        payloads.append(response.json())

    logger.info(
        "playlist_items.yt_playload_ingestion_success",
        payload_count=len(payloads),
    )

    return payloads


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
        descarded_row_count=len(rows) - len(result),
    )
    return result
