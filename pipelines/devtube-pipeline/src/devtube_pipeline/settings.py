from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    youtube_api_base: HttpUrl
    youtube_api_key: str
    aws_endpoint_url_http: HttpUrl = Field(validation_alias="AWS_ENDPOINT_URL")
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str
    s3_bucket_name: str = Field(validation_alias="TF_VAR_s3_bucket_name")
    transcript_langs: list[str]
    transcript_sources: list[Literal["manual", "auto"]]
    video_windows_days: int = Field(default=7, ge=1)
    comment_threads_per_video: int = Field(default=30, ge=1)
    max_videos_per_channel: int = Field(default=10, ge=1)
    video_limit: int = Field(default=500, ge=1)
    max_video_duration_seconds: int = Field(default=2700, ge=1)
    shorts_max_duration_seconds: int = Field(default=90, ge=1)

    @property
    def aws_endpoint_url(self) -> str:
        return self.aws_endpoint_url_http.encoded_string().rstrip('/')


settings = IngestionSettings() # type: ignore[call-arg]

__all__ = ["settings"]
