import pyarrow as pa
from pyiceberg.schema import Schema
from pyiceberg.types import (
    IntegerType,
    ListType,
    LongType,
    NestedField,
    StringType,
    TimestamptzType,
)

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


videoSchema = Schema(
    NestedField(field_id=1, name="video_id", field_type=StringType(), required=True),
    NestedField(field_id=2, name="title", field_type=StringType(), required=True),
    NestedField(
        field_id=3,
        name="tags",
        field_type=ListType(
            element_id=101, element_type=StringType(), element_required=False
        ),
        required=False,
    ),
    NestedField(
        field_id=4, name="published_at", field_type=TimestamptzType(), required=True
    ),
    NestedField(field_id=5, name="duration", field_type=IntegerType(), required=True),
    NestedField(field_id=6, name="view_count", field_type=LongType(), required=False),
    NestedField(field_id=7, name="like_count", field_type=LongType(), required=False),
    NestedField(
        field_id=8, name="comment_count", field_type=LongType(), required=False
    ),
    NestedField(
        field_id=9, name="thumbnail_url", field_type=StringType(), required=True
    ),
    NestedField(
        field_id=10, name="thumbnail_width", field_type=IntegerType(), required=True
    ),
    NestedField(
        field_id=11, name="thumbnail_height", field_type=IntegerType(), required=True
    ),
    NestedField(field_id=12, name="channel_id", field_type=StringType(), required=True),
    NestedField(
        field_id=13, name="category_id", field_type=StringType(), required=True
    ),
    NestedField(
        field_id=14, name="description", field_type=StringType(), required=False
    ),
    NestedField(field_id=15, name="run_id", field_type=StringType(), required=True),
    NestedField(
        field_id=16, name="ingested_at", field_type=TimestamptzType(), required=True
    ),
)


videoArrowSchema = pa.schema(
    [
        pa.field("video_id", pa.string(), nullable=False),
        pa.field("title", pa.string(), nullable=False),
        pa.field("tags", pa.list_(pa.string()), nullable=True),
        pa.field("published_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("duration", pa.int32(), nullable=False),
        pa.field("view_count", pa.int64(), nullable=True),
        pa.field("like_count", pa.int64(), nullable=True),
        pa.field("comment_count", pa.int64(), nullable=True),
        pa.field("thumbnail_url", pa.string(), nullable=False),
        pa.field("thumbnail_width", pa.int32(), nullable=False),
        pa.field("thumbnail_height", pa.int32(), nullable=False),
        pa.field("channel_id", pa.string(), nullable=False),
        pa.field("category_id", pa.string(), nullable=False),
        pa.field("description", pa.string(), nullable=True),
        pa.field("run_id", pa.string(), nullable=False),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ]
)
