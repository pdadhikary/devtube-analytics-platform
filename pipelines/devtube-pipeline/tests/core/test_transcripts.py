from datetime import UTC, datetime

from devtube_pipeline.core.transcripts import (
    build_transcript_object_key,
    find_transcript_track,
    json3_to_segments,
    segments_to_text,
    to_no_transcript_rows,
    to_transcript_rows,
)


def json3_format(url: str, ext: str = "json3") -> list[dict]:
    return [{"ext": ext, "url": url}]


def info(subtitles: dict | None = None, automatic_captions: dict | None = None) -> dict:
    return {
        "subtitles": subtitles or {},
        "automatic_captions": automatic_captions or {},
    }


def json3(*events: dict) -> dict:
    return {"events": list(events)}


class TestFindTranscriptTrack:
    def test_prefers_manual_over_auto(self) -> None:
        track = find_transcript_track(
            info(
                subtitles={"en": json3_format("manual-url")},
                automatic_captions={"en": json3_format("auto-url")},
            ),
            langs=["en"],
            sources=["manual", "auto"],
        )
        assert track == ("en", "manual", "manual-url")

    def test_falls_back_to_auto(self) -> None:
        track = find_transcript_track(
            info(automatic_captions={"en": json3_format("auto-url")}),
            langs=["en"],
            sources=["manual", "auto"],
        )
        assert track == ("en", "auto", "auto-url")

    def test_respects_language_preference_order(self) -> None:
        track = find_transcript_track(
            info(
                subtitles={
                    "en": json3_format("en-url"),
                    "fr": json3_format("fr-url"),
                }
            ),
            langs=["fr", "en"],
            sources=["manual"],
        )
        assert track == ("fr", "manual", "fr-url")

    def test_skips_non_json3_formats(self) -> None:
        track = find_transcript_track(
            info(subtitles={"en": json3_format("vtt-url", ext="vtt")}),
            langs=["en"],
            sources=["manual"],
        )
        assert track is None

    def test_returns_none_when_no_tracks(self) -> None:
        track = find_transcript_track(info(), langs=["en"], sources=["manual", "auto"])
        assert track is None


class TestJson3ToSegments:
    def test_parses_events_with_timing_and_text(self) -> None:
        segments = json3_to_segments(
            json3(
                {
                    "tStartMs": 0,
                    "dDurationMs": 1850,
                    "segs": [{"utf8": "Hello "}, {"utf8": "world"}],
                },
                {"tStartMs": 1850, "dDurationMs": 1000, "segs": [{"utf8": "again"}]},
            )
        )
        assert segments == [
            {"start": 0.0, "duration": 1.85, "text": "Hello world"},
            {"start": 1.85, "duration": 1.0, "text": "again"},
        ]

    def test_skips_window_events_and_empty_text(self) -> None:
        segments = json3_to_segments(
            json3(
                {"tStartMs": 0, "dDurationMs": 10},
                {"tStartMs": 0, "dDurationMs": 10, "segs": [{"utf8": "\n"}]},
                {"tStartMs": 10, "dDurationMs": 10, "segs": [{"utf8": "real"}]},
            )
        )
        assert [segment["text"] for segment in segments] == ["real"]


class TestSegmentsToText:
    def test_joins_segments_with_spaces(self) -> None:
        text = segments_to_text(
            [
                {"start": 0.0, "duration": 1.0, "text": "Hello"},
                {"start": 1.0, "duration": 1.0, "text": "world"},
            ]
        )
        assert text == "Hello world"

    def test_empty_segments_yield_empty_text(self) -> None:
        assert segments_to_text([]) == ""


class TestBuildTranscriptObjectKey:
    def test_builds_partitioned_raw_key(self) -> None:
        key = build_transcript_object_key(
            ingestion_date=datetime(2026, 10, 10, tzinfo=UTC),
            run_id="run-1",
            video_id="vid1",
            lang="en",
            source="manual",
        )
        assert key == (
            "raw/transcripts/ingestion_date=2026-10-10/run_id=run-1/"
            "video_id=vid1/lang=en/source=manual/payload.json"
        )


class TestToTranscriptRows:
    def test_builds_row_with_text_and_s3_uri(self) -> None:
        ingested_at = datetime(2026, 10, 10, tzinfo=UTC)
        rows = to_transcript_rows(
            run_id="run-1",
            payloads=[
                {
                    "video_id": "vid1",
                    "lang": "en",
                    "source": "manual",
                    "json3": json3(
                        {"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "Hi"}]}
                    ),
                }
            ],
            ingested_at=ingested_at,
            bucket="devtube-lakehouse",
        )

        assert len(rows) == 1
        row = rows[0]
        assert row.run_id == "run-1"
        assert row.video_id == "vid1"
        assert row.lang == "en"
        assert row.source == "manual"
        assert row.text == "Hi"
        assert row.s3_uri == (
            "s3://devtube-lakehouse/raw/transcripts/ingestion_date=2026-10-10/"
            "run_id=run-1/video_id=vid1/lang=en/source=manual/payload.json"
        )
        assert row.ingested_at == ingested_at

    def test_empty_payloads_yield_no_rows(self) -> None:
        rows = to_transcript_rows(
            run_id="run-1",
            payloads=[],
            ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
            bucket="devtube-lakehouse",
        )
        assert rows == []


class TestToNoTranscriptRows:
    def test_builds_marker_rows_with_null_transcript_fields(self) -> None:
        ingested_at = datetime(2026, 10, 10, tzinfo=UTC)

        rows = to_no_transcript_rows(
            run_id="run-1",
            video_ids=["vid1", "vid2"],
            ingested_at=ingested_at,
        )

        assert [row.video_id for row in rows] == ["vid1", "vid2"]
        for row in rows:
            assert row.run_id == "run-1"
            assert row.lang is None
            assert row.source is None
            assert row.text is None
            assert row.s3_uri is None
            assert row.ingested_at == ingested_at

    def test_empty_video_ids_yield_no_rows(self) -> None:
        assert (
            to_no_transcript_rows(
                run_id="run-1",
                video_ids=[],
                ingested_at=datetime(2026, 10, 10, tzinfo=UTC),
            )
            == []
        )
