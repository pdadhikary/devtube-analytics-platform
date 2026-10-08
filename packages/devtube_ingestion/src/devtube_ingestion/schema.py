from pyiceberg.schema import Schema
from pyiceberg.types import DateType, NestedField, StringType

playlistItemSchema = Schema(
    NestedField(field_id=1, name="video_id", field_type=StringType, required=True),
    NestedField(field_id=2, name="playlist_id", field_type=StringType, required=True),
    NestedField(field_id=3, name="video_title", field_type=StringType, required=True),
    NestedField(field_id=4, name="run_id", field_type=StringType, required=True),
    NestedField(field_id=5, name="channel_title", field_type=StringType, required=True),
    NestedField(field_id=6, name="channel_id", field_type=StringType, required=True),
    NestedField(field_id=7, name="ingested_at", field_type=DateType, required=True),
)
