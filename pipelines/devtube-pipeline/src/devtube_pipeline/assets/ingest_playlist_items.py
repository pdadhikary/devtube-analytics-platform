import json

import httpx
import structlog
from botocore.exceptions import ClientError
from pydantic import BaseModel
from pyiceberg.catalog import Catalog
from types_boto3_s3 import S3Client

from devtube_pipeline.core.playlists import (
    filter_playlist_items_by_published_dt,
    to_playlist_item_table_rows,
)
from devtube_pipeline.core.raw_layout import build_raw_object_key
from devtube_pipeline.models import PlaylistItemTableRow
from devtube_pipeline.schema import playlistItemArrowSchema, playlistItemSchema
from devtube_pipeline.settings import settings
from devtube_pipeline.utils import (
    get_channel_ids,
    get_n_days_ago,
    get_today_dt,
    model_to_arrow_table,
)
from devtube_pipeline.warehouse import ensure_table_and_upsert
from devtube_pipeline.youtube import fetch_playlist_item_payloads

logger = structlog.get_logger(__name__)


class PlaylistItemIngestionResult(BaseModel):
    num_payloads_ingested: int
    num_items_extracted: int
    num_items_filtered: int


def ingest_playlist_items(
    run_id: str,
    channels_yaml_file: str,
    yt_client: httpx.Client,
    s3_client: S3Client,
    catalog: Catalog,
) -> PlaylistItemIngestionResult:
    channel_ids = get_channel_ids(channels_yaml_file)
    today_dt = get_today_dt()

    payloads = fetch_playlist_item_payloads(
        yt_client=yt_client,
        channel_ids=channel_ids,
        max_results_per_channel=settings.max_videos_per_channel,
        run_id=run_id,
    )
    num_payload = len(payloads)

    table_rows: list[PlaylistItemTableRow] = to_playlist_item_table_rows(
        run_id=run_id, payloads=payloads, ingested_at=today_dt
    )
    num_items_extracted = len(table_rows)

    table_rows: list[PlaylistItemTableRow] = (
        filter_playlist_items_by_published_dt(
            rows=table_rows,
            earliest_published_dt=get_n_days_ago(
                today_dt, settings.video_windows_days
            ),
        )
    )
    num_items_filtered = len(table_rows)

    arrow_table = model_to_arrow_table(table_rows, playlistItemArrowSchema)

    try:
        ensure_table_and_upsert(
            catalog=catalog,
            namespace=settings.s3_bucket_name,
            table_name="playlist_items",
            location=f"s3://{settings.s3_bucket_name}/curated/playlist_items/",
            schema=playlistItemSchema,
            arrow_table=arrow_table,
            join_cols=["video_id"],
        )
    except Exception:
        logger.error("playlist_items.iceberg_catalog_upsert_failed", run_id=run_id)
        raise

    try:
        for payload in payloads:
            items = payload["items"]
            if not items:
                continue
            playlist_id = items[0]["snippet"]["playlistId"]
            object_key = build_raw_object_key(
                kind="playlist_items",
                ingestion_date=today_dt,
                run_id=run_id,
                partitions={"playlist_id": playlist_id},
            )
            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=object_key,
                Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
    except ClientError as e:
        logger.error("playlist_items.s3_put_object_failed", run_id=run_id, error=e)
        raise

    return PlaylistItemIngestionResult(
        num_payloads_ingested=num_payload,
        num_items_extracted=num_items_extracted,
        num_items_filtered=num_items_filtered,
    )
