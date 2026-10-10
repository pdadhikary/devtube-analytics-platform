import json

import httpx
import structlog
from botocore.exceptions import ClientError
from pydantic import BaseModel
from pyiceberg.catalog import Catalog
from types_boto3_s3 import S3Client

from devtube_pipeline.core.raw_layout import build_raw_object_key
from devtube_pipeline.core.videos import (
    filter_videos_by_duration,
    to_video_row,
)
from devtube_pipeline.models import PlaylistItemTableRow, VideoTableRow
from devtube_pipeline.schema import videoArrowSchema, videoSchema
from devtube_pipeline.settings import settings
from devtube_pipeline.utils import get_today_dt, model_to_arrow_table
from devtube_pipeline.warehouse import ensure_table_and_upsert
from devtube_pipeline.youtube import fetch_video_payloads

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

    payloads = fetch_video_payloads(
        yt_client=yt_client,
        video_ids=video_ids,
        run_id=run_id,
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
        upsert_result = ensure_table_and_upsert(
            catalog=catalog,
            namespace=settings.s3_bucket_name,
            table_name="videos",
            location=f"s3://{settings.s3_bucket_name}/curated/videos/",
            schema=videoSchema,
            arrow_table=arrow_table,
            join_cols=["video_id"],
        )
        num_new_videos_added = upsert_result.rows_inserted
    except Exception:
        logger.error("videos.iceberg_catalog_upsert_failed", run_id=run_id)
        raise

    try:
        for batch_index, payload in enumerate(payloads):
            if not payload["items"]:
                continue
            object_key = build_raw_object_key(
                kind="videos",
                ingestion_date=today_dt,
                run_id=run_id,
                partitions={"batch": str(batch_index)},
            )
            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=object_key,
                Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
    except ClientError as e:
        logger.error("videos.s3_put_object_failed", run_id=run_id, error=e)
        raise

    return VideosIngestionResult(
        num_videos_processed=num_videos_processed,
        num_new_videos_added=num_new_videos_added,
        num_shorts_discarded=num_shorts_discarded,
        num_long_forms_discarded=num_long_forms_discarded,
    )
