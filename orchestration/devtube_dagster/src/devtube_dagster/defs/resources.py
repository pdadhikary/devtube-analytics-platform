from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import boto3
import dagster as dg
import httpx
import structlog
import yt_dlp
from devtube_pipeline.settings import settings
from pyiceberg.catalog import Catalog, load_catalog
from types_boto3_s3 import S3Client
from yt_dlp.cookies import CookieLoadError

logger = structlog.get_logger(__name__)


class S3Resource(dg.ConfigurableResource):
    @contextmanager
    def yield_for_execution(
        self, context: dg.InitResourceContext
    ) -> Generator[S3Client]:
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
    def yield_for_execution(self, context: dg.InitResourceContext) -> Generator[Catalog]:
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
    ) -> Generator[httpx.Client]:
        client = httpx.Client(
            base_url=str(settings.youtube_api_base),
            params={"key": settings.youtube_api_key},
            timeout=20.0,
        )
        try:
            yield client
        finally:
            client.close()


class ImageClientResource(dg.ConfigurableResource):
    @contextmanager
    def yield_for_execution(
        self, context: dg.InitResourceContext
    ) -> Generator[httpx.Client]:
        client = httpx.Client(timeout=20.0, follow_redirects=True)
        try:
            yield client
        finally:
            client.close()


class TranscriptClientResource(dg.ConfigurableResource):
    @contextmanager
    def yield_for_execution(
        self, context: dg.InitResourceContext
    ) -> Generator[yt_dlp.YoutubeDL]:
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignore_no_formats_error": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "json3",
            "subtitleslangs": settings.transcript_langs,
            "retries": settings.transcript_max_retries,
            "extractor_retries": settings.transcript_max_retries,
        }
        browser_specification = self._browser_cookie_specification()
        if browser_specification:
            ydl_opts["cookiesfrombrowser"] = browser_specification

        try:
            ydl = yt_dlp.YoutubeDL(ydl_opts)
        except CookieLoadError as e:
            logger.warning(
                "cookies.load_failed",
                error=str(e),
                browser=settings.transcript_cookies_from_browser,
                profile=settings.transcript_cookies_profile,
            )
            ydl_opts.pop("cookiesfrombrowser", None)
            ydl = yt_dlp.YoutubeDL(ydl_opts)

        with ydl:
            yield ydl

    @staticmethod
    def _browser_cookie_specification() -> tuple[str, str | None, None, None] | None:
        browser = settings.transcript_cookies_from_browser
        profile = settings.transcript_cookies_profile

        if not browser:
            logger.warning(
                "cookies.disabled", reason="TRANSCRIPT_COOKIES_FROM_BROWSER is not set"
            )
            return None

        if not profile:
            logger.warning(
                "cookies.disabled",
                reason="TRANSCRIPT_COOKIES_PROFILE is not set",
                browser=browser,
            )
            return None

        if not Path(profile).exists():
            logger.warning(
                "cookies.profile_not_found",
                profile=profile,
                browser=browser,
            )
            return None

        return browser, profile, None, None
