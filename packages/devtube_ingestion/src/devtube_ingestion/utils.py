from datetime import UTC, datetime, timedelta
from uuid import uuid4


def iso_to_UTC(dt: str) -> datetime:
    return datetime.fromisoformat(dt)


def get_n_days_ago(dt: datetime, n_days: int) -> datetime:
    dt_delta = timedelta(days=n_days)
    return dt - dt_delta


def today() -> datetime:
    return datetime.now(tz=UTC)

def get_uuid() -> str:
    return str(uuid4())
