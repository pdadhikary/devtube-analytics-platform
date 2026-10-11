from typing import cast

import yt_dlp

from devtube_pipeline.assets.ingest_transcripts import (
    TranscriptFetchResult,
    fetch_transcript_payloads,
)


class FakeYdl:
    def __init__(self, behavior) -> None:
        self._behavior = behavior

    def extract_info(self, url: str, download: bool = False) -> dict:
        return self._behavior(url.split("v=")[-1])


def fetch(
    ydl: FakeYdl, video_ids: list[str], **overrides
) -> TranscriptFetchResult:
    kwargs = {
        "langs": ["en"],
        "sources": ["manual", "auto"],
        "run_id": "run-1",
        "request_delay": 0.0,
        "max_retries": 0,
        "retry_backoff": 0.0,
        "max_consecutive_failures": 3,
        "retry_pass_cooldown": 0.0,
    }
    kwargs.update(overrides)
    return fetch_transcript_payloads(
        ydl=cast(yt_dlp.YoutubeDL, ydl), video_ids=video_ids, **kwargs
    )


class TestFailureAccounting:
    def test_unexpected_failure_is_recorded_without_abort(self) -> None:
        def behavior(video_id: str) -> dict:
            raise yt_dlp.utils.DownloadError(
                f"ERROR: [youtube] {video_id}: The page needs to be reloaded."
            )

        result = fetch(FakeYdl(behavior), ["vid1", "vid2", "vid3", "vid4"])

        assert result.payloads == []
        assert result.failed_video_ids == ["vid1", "vid2", "vid3", "vid4"]
        assert result.aborted is False

    def test_bot_check_failures_abort_after_threshold(self) -> None:
        def behavior(video_id: str) -> dict:
            raise yt_dlp.utils.DownloadError(
                "ERROR: Sign in to confirm you're not a bot."
            )

        result = fetch(
            FakeYdl(behavior),
            ["vid1", "vid2", "vid3", "vid4"],
            max_consecutive_failures=2,
        )

        assert result.failed_video_ids == ["vid1", "vid2"]
        assert result.aborted is True

    def test_missing_track_is_no_transcript_not_failure(self) -> None:
        def behavior(video_id: str) -> dict:
            return {"subtitles": {}, "automatic_captions": {}}

        result = fetch(FakeYdl(behavior), ["vid1"])

        assert result.no_transcript_video_ids == ["vid1"]
        assert result.failed_video_ids == []
