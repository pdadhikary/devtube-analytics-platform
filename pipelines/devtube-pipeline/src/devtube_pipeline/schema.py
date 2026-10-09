import pyarrow as pa
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, TimestamptzType

playlistItemSchema = Schema(
    NestedField(field_id=1, name="video_id", field_type=StringType(), required=True),
    NestedField(field_id=2, name="playlist_id", field_type=StringType(), required=True),
    NestedField(field_id=3, name="video_title", field_type=StringType(), required=True),
    NestedField(field_id=4, name="run_id", field_type=StringType(), required=True),
    NestedField(
        field_id=5, name="channel_title", field_type=StringType(), required=True
    ),
    NestedField(field_id=6, name="channel_id", field_type=StringType(), required=True),
    NestedField(
        field_id=7,
        name="video_published_dt",
        field_type=TimestamptzType(),
        required=True,
    ),
    NestedField(
        field_id=8, name="ingested_at", field_type=TimestamptzType(), required=True
    ),
)

playlistItemArrowSchema = pa.schema(
    [
        pa.field("video_id", pa.string(), nullable=False),
        pa.field("playlist_id", pa.string(), nullable=False),
        pa.field("video_title", pa.string(), nullable=False),
        pa.field("run_id", pa.string(), nullable=False),
        pa.field("channel_title", pa.string(), nullable=False),
        pa.field("channel_id", pa.string(), nullable=False),
        pa.field("video_published_dt", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ]
)
