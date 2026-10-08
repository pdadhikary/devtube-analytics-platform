from datetime import datetime

from pydantic import BaseModel


class ResourceId(BaseModel):
    kind: str
    videoId: str


class ContentDetails(BaseModel):
    videoId: str
    videoPublishedAt: str


class Snippet(BaseModel):
    publishedAt: str
    channelId: str
    title: str
    description: str
    channelTitle: str
    playlistId: str
    position: int
    resourceId: ResourceId


class PlaylistItem(BaseModel):
    kind: str
    etag: str
    id: str
    snippet: Snippet
    contentDetails: ContentDetails


class PlaylistResponse(BaseModel):
    kind: str
    etag: str
    nextPageToken: str | None = None
    items: list[PlaylistItem]


class PlaylistItemTableRow(BaseModel):
    video_id: str
    playlist_id: str
    video_title: str
    run_id: str
    channel_title: str
    channel_id: str
    ingested_at: datetime

