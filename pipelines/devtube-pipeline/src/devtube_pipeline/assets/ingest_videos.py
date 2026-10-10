import json
from typing import Any

import httpx
import structlog
from botocore.exceptions import ClientError
from pydantic import BaseModel
from pyiceberg.catalog import Catalog
from types_boto3_s3 import S3Client

from devtube_pipeline.core.videos import (
    batched_video_ids,
    filter_videos_by_duration,
    to_video_row,
)
from devtube_pipeline.models import PlaylistItemTableRow, VideoTableRow
from devtube_pipeline.schema import videoArrowSchema, videoSchema
from devtube_pipeline.settings import settings
from devtube_pipeline.utils import get_today_dt, model_to_arrow_table

logger = structlog.get_logger(__name__)


class VideosIngestionResult(BaseModel):
    num_videos_processed: int
    num_new_videos_added: int
    num_shorts_discarded: int
    num_long_forms_discarded: int


def ingest_videos(
    run_id: str,
    yt_client: httpx.Client,
    s3_client: S3Client,
    catalog: Catalog,
) -> VideosIngestionResult:
    playlist_items_table = catalog.load_table(
        f"{settings.s3_bucket_name}.playlist_items"
    )

    playlist_items_rows = (
        playlist_items_table.scan(row_filter=f"run_id = '{run_id}'")
        .to_arrow()
        .to_pylist()
    )

    playlist_item_table_rows = [
        PlaylistItemTableRow(**item) for item in playlist_items_rows
    ]

    video_ids = [item.video_id for item in playlist_item_table_rows]

    today_dt = get_today_dt()

    payloads: list[dict[str, Any]] = []
    for video_id_batch in batched_video_ids(video_ids, batch_size=50):
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
                "maxResults": 50,
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

    table_rows: list[VideoTableRow] = [
        to_video_row(video, run_id=run_id, ingested_at=today_dt)
        for payload in payloads
        for video in payload["items"]
    ]

    num_videos_processed = len(table_rows)

    table_rows, num_shorts_discarded, num_long_forms_discarded = (
        filter_videos_by_duration(
            table_rows,
            shorts_max_seconds=settings.shorts_max_duration_seconds,
            max_duration_seconds=settings.max_video_duration_seconds,
        )
    )

    arrow_table = model_to_arrow_table(table_rows, videoArrowSchema)

    try:
        if not catalog.namespace_exists(settings.s3_bucket_name):
            catalog.create_namespace(settings.s3_bucket_name)

        table = catalog.create_table_if_not_exists(
            schema=videoSchema,
            identifier=f"{settings.s3_bucket_name}.videos",
            location=f"s3://{settings.s3_bucket_name}/curated/videos/",
        )

        upsert_result = table.upsert(
            arrow_table,
            join_cols=["video_id"],
            when_matched_update_all=True,
            when_not_matched_insert_all=True,
        )
        num_new_videos_added = upsert_result.rows_inserted
    except Exception:
        logger.error("videos.iceberg_catalog_upsert_failed", run_id=run_id)
        raise
    finally:
        catalog.close()

    try:
        for batch_index, payload in enumerate(payloads):
            if not payload["items"]:
                continue
            object_key = f"raw/videos/ingestion_date={today_dt.strftime('%Y-%m-%d')}/run_id={run_id}/batch={batch_index}/payload.json"
            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=object_key,
                Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
    except ClientError as e:
        logger.error("videos.s3_put_object_failed", run_id=run_id, error=e)
        raise
    finally:
        s3_client.close()

    return VideosIngestionResult(
        num_videos_processed=num_videos_processed,
        num_new_videos_added=num_new_videos_added,
        num_shorts_discarded=num_shorts_discarded,
        num_long_forms_discarded=num_long_forms_discarded,
    )
