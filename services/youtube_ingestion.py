import json
import re
import ssl
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import certifi
import requests
from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig

from .content import prompt_injection_flags


@dataclass(frozen=True)
class CaptionSegment:
    text: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class CaptionChunk:
    text: str
    start_seconds: float
    end_seconds: float
    token_count: int
    quality_flags: list[str]


@dataclass(frozen=True)
class CaptionFetch:
    video_id: str
    language: str
    is_generated: bool
    segments: list[CaptionSegment]
    raw_bytes: bytes
    pathway: str
    proxy_requests: int = 0


class LimitedSession(requests.Session):
    def __init__(self, max_requests: int) -> None:
        super().__init__()
        self.max_requests = max_requests
        self.request_count = 0

    def send(self, request: PreparedRequest, **kwargs: Any) -> Response:
        if self.request_count >= self.max_requests:
            raise RuntimeError(f"Zyte request cap of {self.max_requests} was reached")
        self.request_count += 1
        return super().send(request, **kwargs)


class ZyteTLSAdapter(HTTPAdapter):
    def __init__(self, context: ssl.SSLContext) -> None:
        self.context = context
        super().__init__()

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["ssl_context"] = self.context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:
        proxy_kwargs["ssl_context"] = self.context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


@lru_cache(maxsize=1)
def build_zyte_ssl_context() -> ssl.SSLContext:
    response = requests.get("https://docs.zyte.com/_static/zyte-ca.crt", timeout=20)
    response.raise_for_status()
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cadata=response.text)
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    video_id = ""
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/shorts/", "/live/", "/embed/")):
            video_id = parsed.path.strip("/").split("/", 1)[1].split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("The source URL does not contain a valid YouTube video ID")
    return video_id


def fetch_public_caption_segments(
    url: str,
) -> CaptionFetch:
    video_id = youtube_video_id(url)
    transcript = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
    return _caption_fetch(transcript, video_id, "youtube_public_captions")


def fetch_zyte_caption_segments(
    url: str,
    zyte_api_key: str,
    max_proxy_requests: int = 5,
) -> CaptionFetch:
    video_id = youtube_video_id(url)
    proxy_key = quote(zyte_api_key, safe="")
    proxy_url = f"http://{proxy_key}:@api.zyte.com:8011"
    session = LimitedSession(max_proxy_requests)
    session.mount("https://", ZyteTLSAdapter(build_zyte_ssl_context()))
    api = YouTubeTranscriptApi(
        proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url),
        http_client=session,
    )
    try:
        transcript = api.fetch(video_id, languages=["en"])
        return _caption_fetch(
            transcript,
            video_id,
            "youtube_public_captions_via_zyte",
            proxy_requests=session.request_count,
        )
    finally:
        session.close()


def _caption_fetch(
    transcript: Any,
    video_id: str,
    pathway: str,
    proxy_requests: int = 0,
) -> CaptionFetch:
    raw = transcript.to_raw_data()
    segments = [
        CaptionSegment(
            text=str(item["text"]).strip(),
            start_seconds=float(item["start"]),
            end_seconds=float(item["start"]) + float(item["duration"]),
        )
        for item in raw
        if str(item.get("text", "")).strip()
    ]
    if not segments:
        raise ValueError("The public caption track was empty")
    payload = json.dumps(
        {
            "video_id": video_id,
            "language": transcript.language_code,
            "is_generated": transcript.is_generated,
            "segments": raw,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return CaptionFetch(
        video_id=video_id,
        language=transcript.language_code,
        is_generated=transcript.is_generated,
        segments=segments,
        raw_bytes=payload,
        pathway=pathway,
        proxy_requests=proxy_requests,
    )


def caption_chunks(
    segments: list[CaptionSegment],
    *,
    target_words: int = 180,
    max_words: int = 320,
) -> list[CaptionChunk]:
    chunks: list[CaptionChunk] = []
    buffer: list[CaptionSegment] = []
    word_count = 0

    def flush() -> None:
        nonlocal word_count
        if not buffer:
            return
        text = " ".join(segment.text for segment in buffer)
        chunks.append(
            CaptionChunk(
                text=text,
                start_seconds=buffer[0].start_seconds,
                end_seconds=buffer[-1].end_seconds,
                token_count=max(1, round(len(text.split()) * 1.3)),
                quality_flags=prompt_injection_flags(text),
            )
        )
        buffer.clear()
        word_count = 0

    for segment in segments:
        segment_words = len(segment.text.split())
        if buffer and word_count + segment_words > max_words:
            flush()
        buffer.append(segment)
        word_count += segment_words
        if word_count >= target_words and segment.text.rstrip().endswith((".", "?", "!")):
            flush()
    flush()
    return chunks
