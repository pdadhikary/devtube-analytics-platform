import boto3
import pyarrow as pa
import yaml
from mypy_boto3_s3 import S3Client
from pyiceberg.catalog import load_catalog

from devtube_ingestion.client import get_youtube_client
from devtube_ingestion.models import PlaylistItemTableRow, PlaylistResponse
from devtube_ingestion.schema import playlistItemArrowSchema, playlistItemSchema
from devtube_ingestion.settings import settings
from devtube_ingestion.utils import get_n_days_ago, get_uuid, iso_to_UTC, today


def main(channels_yaml_file: str):
    with open(channels_yaml_file, "r") as channels_file:
        channels_list = yaml.safe_load(channels_file)

    if not channels_list:
        raise OSError(f"Could not load YAML channels file from {channels_yaml_file}")

    run_id = get_uuid()

    s3_client: S3Client = boto3.client("s3", endpoint_url=settings.aws_endpoint_url)
    with get_youtube_client() as client:
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

            object_key = f"raw/playlist_items/ingestion_date={today_dt.strftime('%Y-%m-%d')}/playlist_id={recently_uploaded_playlistId}/run_id={run_id}/payload.json"
            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=object_key,
                Body=data.model_dump_json().encode("utf-8"),
                ContentType="application/json",
            )

    s3_client.close()

    arrow_table = pa.Table.from_pylist(
        [row.model_dump() for row in table_rows], schema=playlistItemArrowSchema
    )

    catalog = load_catalog(
        "default",
        **{
            "type": "sql",
            "uri": "sqlite:///catalog.db",
            "warehouse": f"s3://{settings.s3_bucket_name}/",
            "s3.endpoint": settings.aws_endpoint_url,
            "s3.region": settings.aws_default_region,
            "s3.access-key-id": settings.aws_access_key_id,
            "s3.secret-access-key": settings.aws_secret_access_key,
        },
    )

    if not catalog.namespace_exists(settings.s3_bucket_name):
        catalog.create_namespace(settings.s3_bucket_name)

    table = catalog.create_table_if_not_exists(
        schema=playlistItemSchema,
        identifier=f"{settings.s3_bucket_name}.playlist_items",
        location=f"s3://{settings.s3_bucket_name}/curated/playlist_items/",
    )

    table.upsert(
        arrow_table,
        join_cols=["video_id"],
        when_matched_update_all=True,
        when_not_matched_insert_all=True,
    )


if __name__ == "__main__":
    import typer

    typer.run(main)
