import json
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import structlog
import yt_dlp
from botocore.exceptions import ClientError
from pydantic import BaseModel
from pyiceberg.catalog import Catalog
from types_boto3_s3 import S3Client

from devtube_pipeline.core.transcripts import (
    build_transcript_object_key,
    find_transcript_track,
    to_no_transcript_rows,
    to_transcript_rows,
)
from devtube_pipeline.models import TranscriptTableRow
from devtube_pipeline.schema import transcriptArrowSchema, transcriptSchema
from devtube_pipeline.settings import settings
from devtube_pipeline.utils import get_today_dt, model_to_arrow_table
from devtube_pipeline.warehouse import ensure_table_and_upsert
from yt_dlp.networking.exceptions import RequestError

logger = structlog.get_logger(__name__)

WATCH_URL = "https://www.youtube.com/watch?v={video_id}"


class TranscriptIngestionResult(BaseModel):
    num_videos_processed: int
    num_videos_skipped_existing: int
    num_transcripts_ingested: int
    num_no_transcript: int
    num_failed: int
    num_transcripts_upserted: int
    aborted: bool


@dataclass
class TranscriptFetchResult:
    payloads: list[dict[str, Any]]
    no_transcript_video_ids: list[str]
    failed_video_ids: list[str]
    aborted: bool


def _retry_delay(response: Any, retry_backoff: float, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
    return retry_backoff * (2**attempt)


def _is_bot_check(message: str) -> bool:
    lowered = message.lower()
    return "not a bot" in lowered or "sign in to confirm" in lowered


def _existing_transcript_video_ids(catalog: Catalog, bucket: str) -> set[str]:
    identifier = f"{bucket}.transcripts"
    if not catalog.table_exists(identifier):
        return set()
    table = catalog.load_table(identifier)
    return {row["video_id"] for row in table.scan().to_arrow().to_pylist()}


def _migrate_transcripts_schema(catalog: Catalog, bucket: str) -> None:
    identifier = f"{bucket}.transcripts"
    if not catalog.table_exists(identifier):
        return

    table = catalog.load_table(identifier)
    fields = {field.name: field for field in table.schema().fields}

    update = table.update_schema()
    changed = False
    for name in ("lang", "source", "text", "s3_uri"):
        field = fields.get(name)
        if field is not None and field.required:
            update = update.make_column_optional(name)
            changed = True

    if changed:
        update.commit()
        logger.info("transcripts.schema_migrated")


def _extract_info_with_retry(
    ydl: yt_dlp.YoutubeDL,
    url: str,
    max_retries: int,
    retry_backoff: float,
    run_id: str,
    video_id: str,
) -> tuple[dict[str, Any] | None, bool]:
    for attempt in range(max_retries + 1):
        try:
            return ydl.extract_info(url, download=False), False
        except yt_dlp.utils.DownloadError as e:
            message = str(e)
            if _is_bot_check(message):
                logger.warning(
                    "transcripts.bot_check_detected",
                    run_id=run_id,
                    video_id=video_id,
                )
                return None, True
            if attempt < max_retries and "429" in message:
                delay = retry_backoff * (2**attempt)
                logger.warning(
                    "transcripts.yt_info_ingestion_retry",
                    run_id=run_id,
                    video_id=video_id,
                    attempt=attempt + 1,
                    delay=delay,
                )
                time.sleep(delay)
                continue
            logger.warning(
                "transcripts.yt_info_ingestion_failed",
                run_id=run_id,
                video_id=video_id,
                error=message,
            )
            return None, "429" in message
    return None, True


def _fetch_subtitle_body(
    ydl: yt_dlp.YoutubeDL,
    url: str,
    max_retries: int,
    retry_backoff: float,
    run_id: str,
    video_id: str,
) -> tuple[bytes | None, bool]:
    for attempt in range(max_retries + 1):
        try:
            response = ydl.urlopen(url)
        except RequestError as e:
            message = str(e)
            if _is_bot_check(message):
                logger.warning(
                    "transcripts.bot_check_detected",
                    run_id=run_id,
                    video_id=video_id,
                )
                return None, True
            if attempt < max_retries and "429" in message:
                delay = retry_backoff * (2**attempt)
                logger.warning(
                    "transcripts.yt_payload_ingestion_retry",
                    run_id=run_id,
                    video_id=video_id,
                    attempt=attempt + 1,
                    delay=delay,
                    error=message,
                )
                time.sleep(delay)
                continue
            logger.warning(
                "transcripts.yt_payload_ingestion_failed",
                run_id=run_id,
                video_id=video_id,
                error=message,
            )
            return None, "429" in message

        if response.status == 200:
            return response.read(), False

        if response.status == 429 and attempt < max_retries:
            delay = _retry_delay(response, retry_backoff, attempt)
            logger.warning(
                "transcripts.yt_payload_ingestion_retry",
                run_id=run_id,
                video_id=video_id,
                attempt=attempt + 1,
                delay=delay,
                status_code=response.status,
            )
            time.sleep(delay)
            continue

        logger.warning(
            "transcripts.yt_payload_ingestion_failed",
            run_id=run_id,
            video_id=video_id,
            status_code=response.status,
        )
        return None, response.status == 429
    return None, True


def fetch_transcript_payloads(
    ydl: yt_dlp.YoutubeDL,
    video_ids: Sequence[str],
    langs: Sequence[str],
    sources: Sequence[str],
    run_id: str,
    request_delay: float,
    max_retries: int,
    retry_backoff: float,
    max_consecutive_failures: int,
    retry_pass_cooldown: float,
) -> TranscriptFetchResult:
    payloads: list[dict[str, Any]] = []
    no_transcript_video_ids: list[str] = []
    failed_video_ids: list[str] = []

    def run_pass(pass_video_ids: Sequence[str], pass_name: str) -> bool:
        consecutive_failures = 0
        for index, video_id in enumerate(pass_video_ids):
            if index > 0 and request_delay > 0:
                time.sleep(request_delay * random.uniform(0.5, 1.5))

            logger.info(
                "transcripts.yt_info_ingestion_started",
                run_id=run_id,
                video_id=video_id,
                pass_name=pass_name,
            )

            info, info_failed = _extract_info_with_retry(
                ydl,
                WATCH_URL.format(video_id=video_id),
                max_retries,
                retry_backoff,
                run_id,
                video_id,
            )
            if info is None:
                failed_video_ids.append(video_id)
                if info_failed:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(
                            "transcripts.ingestion_aborted",
                            run_id=run_id,
                            pass_name=pass_name,
                            consecutive_failures=consecutive_failures,
                            remaining_video_count=len(pass_video_ids) - index - 1,
                        )
                        return True
                continue

            logger.info(
                "transcripts.yt_info_ingestion_success",
                run_id=run_id,
                video_id=video_id,
            )

            track = find_transcript_track(info, langs=langs, sources=sources)
            if track is None:
                consecutive_failures = 0
                no_transcript_video_ids.append(video_id)
                logger.info(
                    "transcripts.no_matching_track",
                    run_id=run_id,
                    video_id=video_id,
                )
                continue

            lang, source, url = track

            logger.info(
                "transcripts.yt_payload_ingestion_started",
                run_id=run_id,
                video_id=video_id,
                lang=lang,
                source=source,
            )

            body, subtitle_failed = _fetch_subtitle_body(
                ydl, url, max_retries, retry_backoff, run_id, video_id
            )
            if body is None:
                failed_video_ids.append(video_id)
                if subtitle_failed:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(
                            "transcripts.ingestion_aborted",
                            run_id=run_id,
                            pass_name=pass_name,
                            consecutive_failures=consecutive_failures,
                            remaining_video_count=len(pass_video_ids) - index - 1,
                        )
                        return True
                continue

            logger.info(
                "transcripts.yt_payload_ingestion_success",
                run_id=run_id,
                video_id=video_id,
                lang=lang,
                source=source,
            )

            consecutive_failures = 0
            payloads.append(
                {
                    "video_id": video_id,
                    "lang": lang,
                    "source": source,
                    "json3": json.loads(body),
                    "raw_body": body,
                }
            )
        return False

    aborted = run_pass(video_ids, "primary")

    if not aborted and failed_video_ids:
        retry_video_ids = list(failed_video_ids)
        failed_video_ids.clear()
        if retry_pass_cooldown > 0:
            logger.info(
                "transcripts.retry_pass_started",
                run_id=run_id,
                retry_video_count=len(retry_video_ids),
                cooldown=retry_pass_cooldown,
            )
            time.sleep(retry_pass_cooldown)
        aborted = run_pass(retry_video_ids, "retry")

    logger.info(
        "transcripts.yt_payload_ingestion_finished",
        payload_count=len(payloads),
        no_transcript_count=len(no_transcript_video_ids),
        failed_video_ids=failed_video_ids,
        aborted=aborted,
    )

    return TranscriptFetchResult(
        payloads=payloads,
        no_transcript_video_ids=no_transcript_video_ids,
        failed_video_ids=failed_video_ids,
        aborted=aborted,
    )


def ingest_transcripts(
    run_id: str,
    ydl: yt_dlp.YoutubeDL,
    s3_client: S3Client,
    catalog: Catalog,
) -> TranscriptIngestionResult:
    bucket = settings.s3_bucket_name
    videos_table = catalog.load_table(f"{bucket}.videos")

    video_rows = videos_table.scan().to_arrow().to_pylist()
    video_rows.sort(key=lambda row: row["published_at"], reverse=True)
    all_video_ids = [row["video_id"] for row in video_rows]

    existing_video_ids = _existing_transcript_video_ids(catalog, bucket)
    missing_video_ids = [
        video_id for video_id in all_video_ids if video_id not in existing_video_ids
    ]
    candidate_video_ids = missing_video_ids
    if settings.video_limit:
        candidate_video_ids = missing_video_ids[: settings.video_limit]

    logger.info(
        "transcripts.transcript_ingestion_started",
        run_id=run_id,
        all_video_count=len(all_video_ids),
        skipped_existing_count=len(all_video_ids) - len(missing_video_ids),
        missing_video_count=len(missing_video_ids),
        candidate_video_count=len(candidate_video_ids),
    )

    today_dt = get_today_dt()

    fetch_result = fetch_transcript_payloads(
        ydl=ydl,
        video_ids=candidate_video_ids,
        langs=settings.transcript_langs,
        sources=settings.transcript_sources,
        run_id=run_id,
        request_delay=settings.transcript_request_delay_seconds,
        max_retries=settings.transcript_max_retries,
        retry_backoff=settings.transcript_retry_backoff_seconds,
        max_consecutive_failures=settings.transcript_max_consecutive_failures,
        retry_pass_cooldown=settings.transcript_retry_pass_cooldown_seconds,
    )

    table_rows: list[TranscriptTableRow] = to_transcript_rows(
        run_id=run_id,
        payloads=fetch_result.payloads,
        ingested_at=today_dt,
        bucket=bucket,
    ) + to_no_transcript_rows(
        run_id=run_id,
        video_ids=fetch_result.no_transcript_video_ids,
        ingested_at=today_dt,
    )

    arrow_table = model_to_arrow_table(table_rows, transcriptArrowSchema)

    _migrate_transcripts_schema(catalog, bucket)

    num_transcripts_upserted = 0
    if table_rows:
        try:
            upsert_result = ensure_table_and_upsert(
                catalog=catalog,
                namespace=bucket,
                table_name="transcripts",
                location=f"s3://{bucket}/curated/transcripts/",
                schema=transcriptSchema,
                arrow_table=arrow_table,
                join_cols=["video_id"],
            )
        except Exception:
            logger.error("transcripts.iceberg_catalog_upsert_failed", run_id=run_id)
            raise
        num_transcripts_upserted = upsert_result.rows_inserted

    try:
        for payload in fetch_result.payloads:
            object_key = build_transcript_object_key(
                ingestion_date=today_dt,
                run_id=run_id,
                video_id=payload["video_id"],
                lang=payload["lang"],
                source=payload["source"],
            )
            s3_client.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=payload["raw_body"],
                ContentType="application/json",
            )
    except ClientError as e:
        logger.error("transcripts.s3_put_object_failed", run_id=run_id, error=e)
        raise

    return TranscriptIngestionResult(
        num_videos_processed=len(all_video_ids),
        num_videos_skipped_existing=len(all_video_ids) - len(missing_video_ids),
        num_transcripts_ingested=len(fetch_result.payloads),
        num_no_transcript=len(fetch_result.no_transcript_video_ids),
        num_failed=len(fetch_result.failed_video_ids),
        num_transcripts_upserted=num_transcripts_upserted,
        aborted=fetch_result.aborted,
    )
