import httpx

from devtube_pipeline.youtube import (
    fetch_comment_thread_payloads,
    fetch_playlist_item_payloads,
    fetch_video_payloads,
)


def make_client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://www.googleapis.com/youtube/v3",
        transport=httpx.MockTransport(handler),
    )


class TestFetchPlaylistItemPayloads:
    def test_derives_uploads_playlist_and_returns_payloads(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200, json={"items": [{"snippet": {"playlistId": "x"}}]}
            )

        client = make_client(handler)

        payloads = fetch_playlist_item_payloads(
            yt_client=client,
            channel_ids=["UCabc", "UCdef"],
            max_results_per_channel=5,
            run_id="run-1",
        )

        assert len(payloads) == 2
        assert len(requests) == 2
        assert [r.url.path for r in requests] == ["/youtube/v3/playlistItems"] * 2
        assert requests[0].url.params["playlistId"] == "UUabc"
        assert requests[1].url.params["playlistId"] == "UUdef"
        assert requests[0].url.params["maxResults"] == "5"
        client.close()

    def test_failed_channel_is_skipped_not_raised(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.params["playlistId"] == "UUbad":
                return httpx.Response(500, text="boom")
            return httpx.Response(200, json={"items": [{"snippet": {}}]})

        client = make_client(handler)

        payloads = fetch_playlist_item_payloads(
            yt_client=client,
            channel_ids=["UCgood", "UCbad"],
            max_results_per_channel=5,
            run_id="run-1",
        )

        assert len(payloads) == 1
        client.close()


class TestFetchVideoPayloads:
    def test_batches_video_ids(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"items": [{"id": "x"}]})

        client = make_client(handler)
        video_ids = [f"vid{i}" for i in range(120)]

        payloads = fetch_video_payloads(
            yt_client=client, video_ids=video_ids, run_id="run-1"
        )

        assert len(payloads) == 3
        assert len(requests) == 3
        batch_sizes = [len(r.url.params["id"].split(",")) for r in requests]
        assert batch_sizes == [50, 50, 20]
        assert requests[0].url.params["id"] == ",".join(video_ids[:50])
        client.close()

    def test_failed_batch_is_skipped_not_raised(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 2:
                return httpx.Response(500, text="boom")
            return httpx.Response(200, json={"items": [{"id": "x"}]})

        client = make_client(handler)
        video_ids = [f"vid{i}" for i in range(120)]

        payloads = fetch_video_payloads(
            yt_client=client, video_ids=video_ids, run_id="run-1"
        )

        assert len(payloads) == 2
        client.close()


class TestFetchCommentThreadPayloads:
    def test_requests_relevant_threads_per_video(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"items": [{"id": "t"}]})

        client = make_client(handler)

        payloads = fetch_comment_thread_payloads(
            yt_client=client,
            video_ids=["vid1", "vid2"],
            max_results_per_video=30,
            run_id="run-1",
        )

        assert len(payloads) == 2
        assert len(requests) == 2
        assert [r.url.path for r in requests] == ["/youtube/v3/commentThreads"] * 2
        assert requests[0].url.params["videoId"] == "vid1"
        assert requests[1].url.params["videoId"] == "vid2"
        assert requests[0].url.params["order"] == "relevance"
        assert requests[0].url.params["part"] == "id,snippet,replies"
        assert requests[0].url.params["maxResults"] == "30"
        client.close()

    def test_max_results_capped_at_100(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"items": [{"id": "t"}]})

        client = make_client(handler)

        fetch_comment_thread_payloads(
            yt_client=client,
            video_ids=["vid1"],
            max_results_per_video=500,
            run_id="run-1",
        )

        assert requests[0].url.params["maxResults"] == "100"
        client.close()

    def test_failed_video_is_skipped_not_raised(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.params["videoId"] == "vid-bad":
                return httpx.Response(403, text="comments disabled")
            return httpx.Response(200, json={"items": [{"id": "t"}]})

        client = make_client(handler)

        payloads = fetch_comment_thread_payloads(
            yt_client=client,
            video_ids=["vid-good", "vid-bad"],
            max_results_per_video=30,
            run_id="run-1",
        )

        assert len(payloads) == 1
        client.close()
