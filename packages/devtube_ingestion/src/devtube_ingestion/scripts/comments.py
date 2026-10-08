import typer

from devtube_ingestion.client import get_youtube_client
from devtube_ingestion.settings import settings


def main(videoId: str):
    with get_youtube_client() as client:
        response = client.get(
            "/commentThreads",
            params={
                "part": "id,snippet,replies",
                "videoId": videoId,
                "maxResults": settings.comment_threads_per_video,
                "textFormat": "plainText",
                "order": "relevance"
            },
        )

        response.raise_for_status()
        result = response.json()
        print(result)
        return result


if __name__ == "__main__":
    typer.run(main)
