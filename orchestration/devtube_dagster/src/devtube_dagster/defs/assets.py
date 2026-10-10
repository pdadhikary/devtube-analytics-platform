from dagster import AssetExecutionContext, asset
from devtube_pipeline.assets.ingest_playlist_items import ingest_playlist_items
from devtube_pipeline.assets.ingest_videos import ingest_videos

from devtube_dagster.defs.resources import (
    CatalogResource,
    ImageClientResource,
    S3Resource,
    YoutubeClientResource,
)


@asset
def playlist_items(
    context: AssetExecutionContext,
    youtube: YoutubeClientResource,
    s3: S3Resource,
    catalog: CatalogResource,
):
    return ingest_playlist_items(
        run_id=context.run_id,
        channels_yaml_file="/home/deepta/Projects/devtube-analytics-platform/channels/channels.yaml",
        yt_client=youtube,
        s3_client=s3,
        catalog=catalog,
    )


@asset(deps=[playlist_items])
def videos(
    context: AssetExecutionContext,
    youtube: YoutubeClientResource,
    image_client: ImageClientResource,
    s3: S3Resource,
    catalog: CatalogResource,
):
    return ingest_videos(
        run_id=context.run_id,
        yt_client=youtube,
        image_client=image_client,
        s3_client=s3,
        catalog=catalog,
    )
