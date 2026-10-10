from itertools import batched
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


def fetch_playlist_item_payloads(
    yt_client: httpx.Client,
    channel_ids: list[str],
    max_results_per_channel: int,
    run_id: str,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for channel_id in channel_ids:
        recently_uploaded_playlist_id = channel_id.replace("C", "U", 1)

        logger.info(
            "playlist_items.yt_payload_ingestion_started",
            run_id=run_id,
            playlist_id=recently_uploaded_playlist_id,
            channel_id=channel_id,
        )

        response = yt_client.get(
            "/playlistItems",
            params={
                "part": "id,snippet,contentDetails",
                "playlistId": recently_uploaded_playlist_id,
                "maxResults": max_results_per_channel,
            },
        )

        if response.status_code != 200:
            logger.error(
                "playlist_items.yt_payload_ingestion_failed",
                run_id=run_id,
                status_code=response.status_code,
                response_text=response.text[:200],
                endpoint=response.url.path,
                playlist_id=recently_uploaded_playlist_id,
                channel_id=channel_id,
            )
            continue

        payloads.append(response.json())

    logger.info(
        "playlist_items.yt_payload_ingestion_success",
        payload_count=len(payloads),
    )

    return payloads


def fetch_video_payloads(
    yt_client: httpx.Client,
    video_ids: list[str],
    run_id: str,
    batch_size: int = 50,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for video_id_batch in batched(video_ids, batch_size):
        video_id_batch = list(video_id_batch)
        logger.info(
            "videos.yt_payload_ingestion_started",
            run_id=run_id,
            video_id_batch=video_id_batch,
        )

        response = yt_client.get(
            "/videos",
            params={
                "part": "id,snippet,statistics,contentDetails",
                "id": ",".join(video_id_batch),
                "maxResults": batch_size,
            },
        )

        if response.status_code != 200:
            logger.error(
                "videos.yt_payload_ingestion_failed",
                run_id=run_id,
                status_code=response.status_code,
                response_text=response.text[:200],
                endpoint=response.url.path,
                video_id_batch=video_id_batch,
            )
            continue

        payloads.append(response.json())

    logger.info(
        "videos.yt_payload_ingestion_success",
        payload_count=len(payloads),
    )

    return payloads
