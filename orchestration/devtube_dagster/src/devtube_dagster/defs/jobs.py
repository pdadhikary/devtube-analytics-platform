import dagster as dg

from devtube_dagster.defs.assets import playlist_items

devtube_ingestion_job = dg.define_asset_job(
    name="devtube_ingestion",
    selection=dg.AssetSelection.assets(
        playlist_items,
    ),
)
