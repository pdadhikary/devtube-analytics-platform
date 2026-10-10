from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pyarrow as pa
import yaml
from pydantic import BaseModel


def parse_iso_to_datetime(dt: str) -> datetime:
    return datetime.fromisoformat(dt)


def get_n_days_ago(dt: datetime, n_days: int) -> datetime:
    dt_delta = timedelta(days=n_days)
    return dt - dt_delta


def get_today_dt() -> datetime:
    return datetime.now(tz=UTC)


def get_uuid() -> str:
    return str(uuid4())


def model_to_arrow_table(model: Sequence[BaseModel], schema: pa.schema) -> pa.Table:
    arrow_table = pa.Table.from_pylist(
        [row.model_dump() for row in model], schema=schema
    )

    return arrow_table


def get_channel_ids(channel_yaml_file_path: str) -> list[str]:
    with open(channel_yaml_file_path, "r") as channels_file:
        channels_list = yaml.safe_load(channels_file)["channels"]

    if not channels_list:
        raise OSError(
            f"Could not load YAML channels file from {channel_yaml_file_path}"
        )

    channel_ids = [channel["id"] for channel in channels_list]

    return channel_ids
