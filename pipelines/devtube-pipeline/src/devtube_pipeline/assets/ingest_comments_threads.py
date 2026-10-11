import json

import httpx
import structlog
from botocore.exceptions import ClientError
from pydantic import BaseModel
from pyiceberg.catalog import Catalog
from types_boto3_s3 import S3Client

from devtube_pipeline.core.comments import to_comment_rows
from devtube_pipeline.core.raw_layout import build_raw_object_key
from devtube_pipeline.models import CommentThreadTableRow
from devtube_pipeline.schema import commentArrowSchema, commentSchema
from devtube_pipeline.settings import settings
from devtube_pipeline.utils import get_today_dt, model_to_arrow_table
from devtube_pipeline.warehouse import ensure_table_and_upsert
from devtube_pipeline.youtube import fetch_comment_thread_payloads

logger = structlog.get_logger(__name__)


class CommentThreadIngestionResult(BaseModel):
    num_videos_processed: int
    num_payloads_ingested: int
    num_comments_extracted: int
    num_comments_upserted: int


def ingest_comment_threads(
    run_id: str,
    yt_client: httpx.Client,
    s3_client: S3Client,
    catalog: Catalog,
) -> CommentThreadIngestionResult:
    videos_table = catalog.load_table(f"{settings.s3_bucket_name}.videos")

    videos_rows = (
        videos_table.scan(row_filter=f"run_id = '{run_id}'").to_arrow().to_pylist()
    )
    video_ids = [row["video_id"] for row in videos_rows]

    today_dt = get_today_dt()

    payloads = fetch_comment_thread_payloads(
        yt_client=yt_client,
        video_ids=video_ids,
        max_results_per_video=settings.comment_threads_per_video,
        run_id=run_id,
    )

    table_rows: list[CommentThreadTableRow] = to_comment_rows(
        run_id=run_id, payloads=payloads, ingested_at=today_dt
    )

    arrow_table = model_to_arrow_table(table_rows, commentArrowSchema)

    try:
        upsert_result = ensure_table_and_upsert(
            catalog=catalog,
            namespace=settings.s3_bucket_name,
            table_name="comment_threads",
            location=f"s3://{settings.s3_bucket_name}/curated/comment_threads/",
            schema=commentSchema,
            arrow_table=arrow_table,
            join_cols=["comment_id"],
        )
    except Exception:
        logger.error(
            "comment_threads.iceberg_catalog_upsert_failed", run_id=run_id
        )
        raise

    try:
        for payload in payloads:
            items = payload.get("items", [])
            if not items:
                continue
            video_id = items[0]["snippet"]["videoId"]
            object_key = build_raw_object_key(
                kind="comment_threads",
                ingestion_date=today_dt,
                run_id=run_id,
                partitions={"video_id": video_id},
            )
            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=object_key,
                Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
    except ClientError as e:
        logger.error(
            "comment_threads.s3_put_object_failed", run_id=run_id, error=e
        )
        raise

    return CommentThreadIngestionResult(
        num_videos_processed=len(video_ids),
        num_payloads_ingested=len(payloads),
        num_comments_extracted=len(table_rows),
        num_comments_upserted=upsert_result.rows_inserted,
    )
