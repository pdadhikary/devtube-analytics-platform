import boto3
import httpx
import pyarrow as pa
import structlog
from botocore.exceptions import ClientError
from pydantic import BaseModel
from pyiceberg.catalog import Catalog

import devtube_pipeline.core.playlists as pl_ingest
from devtube_pipeline.models import PlaylistItemTableRow, PlaylistResponse
from devtube_pipeline.schema import playlistItemArrowSchema, playlistItemSchema
from devtube_pipeline.settings import settings
from devtube_pipeline.utils import (
    get_channel_ids,
    get_n_days_ago,
    get_today_dt,
)

logger = structlog.get_logger(__name__)


class PlaylistItemIngestionResult(BaseModel):
    num_payloads_ingested: int
    num_items_extracted: int
    num_items_filtered: int


def ingest_playlist_items(
    run_id: str,
    channels_yaml_file: str,
    yt_client: httpx.Client,
    s3_client: boto3.client,
    catalog: Catalog,
) -> PlaylistItemIngestionResult:
    channel_ids = get_channel_ids(channels_yaml_file)

    today_dt = get_today_dt()
    responses: list[PlaylistResponse] = (
        pl_ingest.fetch_recently_uploaded_playlist_items(
            run_id=run_id, channel_ids=channel_ids, yt_client=yt_client
        )
    )

    num_payload = len(responses)

    table_rows: list[PlaylistItemTableRow] = pl_ingest.to_playlist_item_table_row(
        run_id=run_id, responses=responses, ingested_at=today_dt
    )
    num_items_extracted = len(table_rows)

    table_rows: list[PlaylistItemTableRow] = (
        pl_ingest.filter_playlist_items_by_published_dt(
            rows=table_rows,
            earliest_published_dt=get_n_days_ago(today_dt, settings.video_windows_days),
        )
    )
    num_items_filtered = len(table_rows)

    arrow_table = pa.Table.from_pylist(
        [row.model_dump() for row in table_rows], schema=playlistItemArrowSchema
    )

    try:
        if not catalog.namespace_exists(settings.s3_bucket_name):
            catalog.create_namespace(settings.s3_bucket_name)

        table = catalog.create_table_if_not_exists(
            schema=playlistItemSchema,
            identifier=f"{settings.s3_bucket_name}.playlist_items",
            location=f"s3://{settings.s3_bucket_name}/curated/playlist_items/",
        )

        table.upsert(
            arrow_table,
            join_cols=["video_id"],
            when_matched_update_all=True,
            when_not_matched_insert_all=True,
        )
    except Exception:
        logger.error("playlist_items.iceberg_catalog_upsert_failed", run_id=run_id)
        raise
    finally:
        catalog.close()

    try:
        for response in responses:
            playlist_id = response.items[0].snippet.playlistId
            object_key = f"raw/playlist_items/ingestion_date={today_dt.strftime('%Y-%m-%d')}/playlist_id={playlist_id}/run_id={run_id}/payload.json"
            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=object_key,
                Body=response.model_dump_json().encode("utf-8"),
                ContentType="application/json",
            )
    except ClientError as e:
        logger.error("playlist_items.s3_put_object_failed", run_id=run_id, error=e)
        raise
    finally:
        s3_client.close()

    return PlaylistItemIngestionResult(
        num_payloads_ingested=num_payload,
        num_items_extracted=num_items_extracted,
        num_items_filtered=num_items_filtered,
    )
