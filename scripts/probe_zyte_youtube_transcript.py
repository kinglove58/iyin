"""Run one explicitly authorized YouTube transcript attempt through Zyte Proxy Mode."""

import argparse
import os

from apps.api.afs.config import get_settings
from services.youtube_ingestion import fetch_zyte_caption_segments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--allow-one-video", action="store_true")
    parser.add_argument("--max-proxy-requests", type=int, default=5, choices=range(2, 6))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.allow_one_video:
        raise SystemExit("Refusing paid proxy traffic without --allow-one-video")
    settings = get_settings()
    if not settings.zyte_api_key:
        raise SystemExit("ZYTE_API_KEY is not configured")

    try:
        result = fetch_zyte_caption_segments(
            args.url,
            settings.zyte_api_key,
            args.max_proxy_requests,
        )
    except Exception as exc:
        print("ZYTE_PROBE_STATUS=failed")
        print(f"ERROR_TYPE={type(exc).__name__}")
        raise SystemExit(1) from None

    print("ZYTE_PROBE_STATUS=succeeded")
    print(f"VIDEO_ID={result.video_id}")
    print(f"CAPTION_SEGMENTS={len(result.segments)}")
    print(f"ZYTE_PROXY_REQUESTS={result.proxy_requests}")
    print(f"CAPTION_LANGUAGE={result.language}")
    print(f"AUTOMATICALLY_GENERATED={str(result.is_generated).lower()}")
    print("COST_SOURCE=Check Zyte API Stats; proxy responses do not expose exact billed cost.")


if __name__ == "__main__":
    os.environ.setdefault("NO_PROXY", "")
    main()
