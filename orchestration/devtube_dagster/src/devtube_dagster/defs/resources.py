from collections.abc import Iterator
from contextlib import contextmanager

import boto3
import dagster as dg
import httpx
from devtube_pipeline.settings import settings
from mypy_boto3_s3 import S3Client
from pyiceberg.catalog import Catalog, load_catalog


class S3Resource(dg.ConfigurableResource):
    @contextmanager
    def yield_for_execution(
        self, context: dg.InitResourceContext
    ) -> Iterator[S3Client]:
        client = boto3.client(
            "s3",
            endpoint_url=settings.aws_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_default_region,
        )
        try:
            yield client
        finally:
            client.close()


class CatalogResource(dg.ConfigurableResource):
    @contextmanager
    def yield_for_execution(self, context: dg.InitResourceContext) -> Iterator[Catalog]:
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
        try:
            yield catalog
        finally:
            catalog.close()


class YoutubeClientResource(dg.ConfigurableResource):
    @contextmanager
    def yield_for_execution(
        self, context: dg.InitResourceContext
    ) -> Iterator[httpx.Client]:
        client = httpx.Client(
            base_url=str(settings.youtube_api_base),
            params={"key": settings.youtube_api_key},
            timeout=20.0,
        )
        try:
            yield client
        finally:
            client.close()
