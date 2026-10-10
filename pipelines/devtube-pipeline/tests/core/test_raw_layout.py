from datetime import UTC, datetime

from devtube_pipeline.core.raw_layout import build_raw_object_key


def test_builds_key_with_partitions() -> None:
    key = build_raw_object_key(
        kind="playlist_items",
        ingestion_date=datetime(2026, 10, 10, tzinfo=UTC),
        run_id="run-1",
        partitions={"playlist_id": "UUx1"},
    )
    assert key == (
        "raw/playlist_items/ingestion_date=2026-10-10/run_id=run-1/"
        "playlist_id=UUx1/payload.json"
    )


def test_builds_key_without_partitions() -> None:
    key = build_raw_object_key(
        kind="videos",
        ingestion_date=datetime(2026, 10, 10, tzinfo=UTC),
        run_id="run-1",
    )
    assert key == "raw/videos/ingestion_date=2026-10-10/run_id=run-1/payload.json"

    assert build_raw_object_key(
        kind="videos",
        ingestion_date=datetime(2026, 10, 10, tzinfo=UTC),
        run_id="run-1",
        partitions={},
    ) == key


def test_multiple_partitions_preserve_order() -> None:
    key = build_raw_object_key(
        kind="videos",
        ingestion_date=datetime(2026, 10, 10, tzinfo=UTC),
        run_id="run-1",
        partitions={"batch": "0", "page": "3"},
    )
    assert key == (
        "raw/videos/ingestion_date=2026-10-10/run_id=run-1/batch=0/page=3/payload.json"
    )
