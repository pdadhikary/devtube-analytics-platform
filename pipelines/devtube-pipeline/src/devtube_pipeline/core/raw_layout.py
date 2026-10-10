from datetime import datetime


def build_raw_object_key(
    kind: str,
    ingestion_date: datetime,
    run_id: str,
    partitions: dict[str, str] | None = None,
) -> str:
    """Build the canonical raw-lake object key for one ingestion payload.

    Layout: raw/{kind}/ingestion_date={YYYY-MM-DD}/run_id={run_id}/[{name}={value}...]payload.json
    """
    parts = [
        "raw",
        kind,
        f"ingestion_date={ingestion_date.strftime('%Y-%m-%d')}",
        f"run_id={run_id}",
    ]
    for name, value in (partitions or {}).items():
        parts.append(f"{name}={value}")
    parts.append("payload.json")
    return "/".join(parts)
