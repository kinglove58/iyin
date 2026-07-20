import pytest
from services.youtube_ingestion import CaptionSegment, caption_chunks, youtube_video_id


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abcdefghijk", "abcdefghijk"),
        ("https://youtu.be/abcdefghijk?t=30", "abcdefghijk"),
        ("https://www.youtube.com/shorts/abcdefghijk", "abcdefghijk"),
        ("https://www.youtube.com/live/abcdefghijk", "abcdefghijk"),
    ],
)
def test_youtube_video_id_supports_public_url_shapes(url: str, expected: str) -> None:
    assert youtube_video_id(url) == expected


def test_caption_chunks_preserve_timestamps_and_text() -> None:
    segments = [
        CaptionSegment("First short sentence.", 0, 2),
        CaptionSegment("Second short sentence.", 2, 5),
    ]
    chunks = caption_chunks(segments, target_words=3, max_words=20)
    assert [chunk.text for chunk in chunks] == [
        "First short sentence.",
        "Second short sentence.",
    ]
    assert chunks[0].start_seconds == 0
    assert chunks[1].end_seconds == 5


def test_youtube_video_id_rejects_non_youtube_urls() -> None:
    with pytest.raises(ValueError, match="valid YouTube"):
        youtube_video_id("https://example.com/watch?v=abcdefghijk")
