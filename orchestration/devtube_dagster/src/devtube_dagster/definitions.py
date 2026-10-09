import dagster as dg

from devtube_dagster.defs.assets import (
    playlist_items,
)
from devtube_dagster.defs.jobs import devtube_ingestion_job
from devtube_dagster.defs.resources import (
    CatalogResource,
    S3Resource,
    YoutubeClientResource,
)
from devtube_dagster.defs.schedules import devtube_pipeline_schedule

defs = dg.Definitions(
    assets=[
        playlist_items,
    ],
    jobs=[
        devtube_ingestion_job,
    ],
    schedules=[
        devtube_pipeline_schedule,
    ],
    resources={
        "youtube": YoutubeClientResource(),
        "s3": S3Resource(),
        "catalog": CatalogResource(),
    },
)
