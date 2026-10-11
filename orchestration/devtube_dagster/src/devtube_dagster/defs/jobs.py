import dagster as dg

from devtube_dagster.defs.assets import (
    comment_threads,
    playlist_items,
    transcripts,
    videos,
)

devtube_ingestion_job = dg.define_asset_job(
    name="devtube_ingestion",
    selection=dg.AssetSelection.assets(
        playlist_items,
        videos,
        comment_threads,
        transcripts,
    ),
)
