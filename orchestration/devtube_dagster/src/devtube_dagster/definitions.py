import dagster as dg

from devtube_dagster.defs.assets import (
    comment_threads,
    playlist_items,
    transcripts,
    videos,
)
from devtube_dagster.defs.jobs import devtube_ingestion_job
from devtube_dagster.defs.resources import (
    CatalogResource,
    ImageClientResource,
    S3Resource,
    TranscriptClientResource,
    YoutubeClientResource,
)
from devtube_dagster.defs.schedules import devtube_pipeline_schedule

defs = dg.Definitions(
    assets=[playlist_items, videos, comment_threads, transcripts],
    jobs=[
        devtube_ingestion_job,
    ],
    schedules=[
        devtube_pipeline_schedule,
    ],
    resources={
        "youtube": YoutubeClientResource(),
        "image_client": ImageClientResource(),
        "s3": S3Resource(),
        "catalog": CatalogResource(),
        "transcript_client": TranscriptClientResource(),
    },
)
