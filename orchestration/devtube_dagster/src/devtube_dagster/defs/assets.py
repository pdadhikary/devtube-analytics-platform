import httpx
import yt_dlp
from dagster import AssetExecutionContext, ResourceParam, asset
from devtube_pipeline.assets.ingest_comments_threads import ingest_comment_threads
from devtube_pipeline.assets.ingest_playlist_items import ingest_playlist_items
from devtube_pipeline.assets.ingest_transcripts import ingest_transcripts
from devtube_pipeline.assets.ingest_videos import ingest_videos
from devtube_pipeline.settings import settings
from pyiceberg.catalog import Catalog
from types_boto3_s3 import S3Client


@asset
def playlist_items(
    context: AssetExecutionContext,
    youtube: ResourceParam[httpx.Client],
    s3: ResourceParam[S3Client],
    catalog: ResourceParam[Catalog],
):
    return ingest_playlist_items(
        run_id=context.run_id,
        channels_yaml_file=str(settings.channels_yaml_file),
        yt_client=youtube,
        s3_client=s3,
        catalog=catalog,
    )


@asset(deps=[playlist_items])
def videos(
    context: AssetExecutionContext,
    youtube: ResourceParam[httpx.Client],
    image_client: ResourceParam[httpx.Client],
    s3: ResourceParam[S3Client],
    catalog: ResourceParam[Catalog],
):
    return ingest_videos(
        run_id=context.run_id,
        yt_client=youtube,
        image_client=image_client,
        s3_client=s3,
        catalog=catalog,
    )


@asset(deps=[videos])
def comment_threads(
    context: AssetExecutionContext,
    youtube: ResourceParam[httpx.Client],
    s3: ResourceParam[S3Client],
    catalog: ResourceParam[Catalog],
):
    return ingest_comment_threads(
        run_id=context.run_id,
        yt_client=youtube,
        s3_client=s3,
        catalog=catalog,
    )


@asset(deps=[videos])
def transcripts(
    context: AssetExecutionContext,
    transcript_client: ResourceParam[yt_dlp.YoutubeDL],
    s3: ResourceParam[S3Client],
    catalog: ResourceParam[Catalog],
):
    return ingest_transcripts(
        run_id=context.run_id,
        ydl=transcript_client,
        s3_client=s3,
        catalog=catalog,
    )
