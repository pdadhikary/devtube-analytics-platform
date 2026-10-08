import boto3
import polars as pl
import yaml
from mypy_boto3_s3 import S3Client
from pyiceberg.catalog import load_catalog

from devtube_ingestion.client import get_youtube_client
from devtube_ingestion.models import PlaylistItemTableRow, PlaylistResponse
from devtube_ingestion.settings import settings
from devtube_ingestion.utils import get_n_days_ago, get_uuid, iso_to_UTC, today


def main(channels_yaml_file: str):
    with open(channels_yaml_file, "r") as channels_file:
        channels_list = yaml.safe_load(channels_file)

    if not channels_list:
        raise OSError(f"Could not load YAML channels file from {channels_yaml_file}")

    run_id = get_uuid()

    with get_youtube_client() as client:
        s3_client: S3Client = boto3.client("s3", endpoint_url=settings.aws_endpoint_url)
        table_rows: list[PlaylistItemTableRow] = []
        for channels in channels_list["channels"]:
            channel_id, channel_name = channels["id"], channels["name"]
            print(f"Retreiving videos from channel={channel_name}")
            # manipulate channel id to get recently uploaded hidden playlist id
            recently_uploaded_playlistId = channel_id.replace("C", "U", 1)

            response = client.get(
                "/playlistItems",
                params={
                    "part": "id,snippet,contentDetails",
                    "playlistId": recently_uploaded_playlistId,
                    "maxResults": settings.max_videos_per_playlist,
                },
            )

            if response.status_code != 200:
                print(
                    f"Could not retreive data for channelId:{channel_id} channelName:{channel_name}"
                )
                continue

            data = PlaylistResponse.model_validate(response.json())

            today_dt = today()
            ingestion_window_last_dt = get_n_days_ago(
                today_dt, settings.video_windows_days
            )

            for item in data.items:
                video_published_date = iso_to_UTC(item.contentDetails.videoPublishedAt)

                if video_published_date >= ingestion_window_last_dt:
                    row = PlaylistItemTableRow(
                        video_id=item.contentDetails.videoId,
                        playlist_id=item.snippet.playlistId,
                        video_title=item.snippet.title,
                        run_id=run_id,
                        channel_title=item.snippet.channelTitle,
                        channel_id=item.snippet.channelId,
                        ingested_at=today_dt,
                    )
                    table_rows.append(row)

            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=f"raw/playlist_items/ingestion_date={today_dt.strftime('%Y-%m-%d')}/playlist_id={recently_uploaded_playlistId}/run_id={run_id}/payload.json",
                Body=data.model_dump_json().encode("utf-8"),
                ContentType="application/json",
            )

    df = pl.DataFrame([row.model_dump() for row in table_rows])
    arrow_table = df.to_arrow()

    catalog = load_catalog("default")
    table = catalog.create_table_if_not_exists(
        identifier=f"{settings.s3_bucket_name}.playlist_items",
        location=f"s3://{settings.s3_bucket_name}/curated/playlist_items/",
    )

    table.upsert(arrow_table, join_cols="video_id", when_matched_update_all=True, when_not_matched_insert_all=True)

    df.write_parquet(
        f"s3://{settings.s3_bucket_name}/curated/playlist_items/data/ingestion_date={today_dt.strftime('%Y-%m-%d')}/run_id={run_id}/data.parquet",
        storage_options={
            "aws_endpoint_url": settings.aws_endpoint_url,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
            "aws_region": settings.aws_default_region,
        },
    )

if __name__ == "__main__":
    import typer

    typer.run(main)
