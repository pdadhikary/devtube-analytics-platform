from collections.abc import Sequence
from datetime import datetime
from typing import Any

import structlog

from devtube_pipeline.core.raw_layout import build_raw_object_key
from devtube_pipeline.models import TranscriptTableRow

logger = structlog.get_logger(__name__)

JSON3_FORMAT = "json3"


def find_transcript_track(
    info: dict[str, Any], langs: Sequence[str], sources: Sequence[str]
) -> tuple[str, str, str] | None:
    """Return (lang, source, url) for the first preferred json3 track.

    Walks ``sources`` first (e.g. manual before auto), then ``langs`` in
    preference order. Returns None when no json3 track is available.
    """
    source_tracks: dict[str, dict[str, list[dict[str, Any]]]] = {
        "manual": info.get("subtitles") or {},
        "auto": info.get("automatic_captions") or {},
    }
    for source in sources:
        tracks = source_tracks.get(source)
        if not tracks:
            continue
        for lang in langs:
            url = _json3_url(tracks.get(lang))
            if url:
                return lang, source, url
    return None


def _json3_url(formats: list[dict[str, Any]] | None) -> str | None:
    for fmt in formats or []:
        if fmt.get("ext") == JSON3_FORMAT and fmt.get("url"):
            return fmt["url"]
    return None


def json3_to_segments(json3: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for event in json3.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue
        text = "".join(seg.get("utf8", "") for seg in segs).strip()
        if not text:
            continue
        segments.append(
            {
                "start": event.get("tStartMs", 0) / 1000.0,
                "duration": event.get("dDurationMs", 0) / 1000.0,
                "text": text,
            }
        )
    return segments


def segments_to_text(segments: list[dict[str, Any]]) -> str:
    return " ".join(segment["text"] for segment in segments if segment["text"]).strip()


def build_transcript_object_key(
    ingestion_date: datetime, run_id: str, video_id: str, lang: str, source: str
) -> str:
    return build_raw_object_key(
        kind="transcripts",
        ingestion_date=ingestion_date,
        run_id=run_id,
        partitions={"video_id": video_id, "lang": lang, "source": source},
    )


def to_transcript_rows(
    run_id: str,
    payloads: list[dict[str, Any]],
    ingested_at: datetime,
    bucket: str,
) -> list[TranscriptTableRow]:
    table_rows: list[TranscriptTableRow] = []
    for payload in payloads:
        video_id = payload["video_id"]
        lang = payload["lang"]
        source = payload["source"]
        text = segments_to_text(json3_to_segments(payload["json3"]))
        object_key = build_transcript_object_key(
            ingestion_date=ingested_at,
            run_id=run_id,
            video_id=video_id,
            lang=lang,
            source=source,
        )
        table_rows.append(
            TranscriptTableRow(
                run_id=run_id,
                video_id=video_id,
                lang=lang,
                source=source,
                text=text,
                s3_uri=f"s3://{bucket}/{object_key}",
                ingested_at=ingested_at,
            )
        )
    logger.info(
        "transcripts.payload_row_extraction_success",
        payload_count=len(payloads),
        row_count=len(table_rows),
    )
    return table_rows


def to_no_transcript_rows(
    run_id: str, video_ids: Sequence[str], ingested_at: datetime
) -> list[TranscriptTableRow]:
    table_rows = [
        TranscriptTableRow(
            run_id=run_id,
            video_id=video_id,
            lang=None,
            source=None,
            text=None,
            s3_uri=None,
            ingested_at=ingested_at,
        )
        for video_id in video_ids
    ]
    logger.info(
        "transcripts.no_transcript_row_extraction_success",
        row_count=len(table_rows),
    )
    return table_rows
