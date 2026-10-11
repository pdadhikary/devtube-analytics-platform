from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlaylistItemTableRow(BaseModel):
    video_id: str
    playlist_id: str
    video_title: str
    run_id: str
    channel_title: str
    channel_id: str
    video_published_dt: datetime
    ingested_at: datetime


class VideoTableRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    video_id: str
    title: str
    tags: list[str] | None = None
    published_at: datetime
    duration: int
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    thumbnail_url: str
    thumbnail_width: int
    thumbnail_height: int
    channel_id: str
    category_id: str
    description: str | None = None
    s3_uri: str | None = None
    run_id: str
    ingested_at: datetime


class CommentThreadTableRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    comment_id: str
    video_id: str
    parent_comment_id: str | None = None
    total_reply_count: int = 0
    author_name: str | None = None
    author_channel_id: str | None = None
    like_count: int = 0
    text_original: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    ingested_at: datetime


class TranscriptTableRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    video_id: str
    lang: str | None = None
    source: str | None = None
    text: str | None = None
    s3_uri: str | None = None
    ingested_at: datetime
