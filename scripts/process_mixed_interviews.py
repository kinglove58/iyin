"""Analyze mixed-speaker interviews and publish only OpenAI-labelled Iyin turns."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Iterable
from typing import Any

import httpx
from apps.api.afs.config import get_settings


def batches(values: list[str], size: int = 200) -> Iterable[list[str]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


class InterviewProcessor:
    def __init__(self, base_url: str) -> None:
        self.settings = get_settings()
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=180)
        self.csrf_token = ""

    def close(self) -> None:
        self.client.close()

    def login(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={
                "email": self.settings.admin_email,
                "password": self.settings.admin_password,
            },
        )
        response.raise_for_status()
        self.csrf_token = str(response.json()["csrf_token"])

    def get(self, path: str, **params: object) -> Any:
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, object]) -> Any:
        response = self.client.post(
            path,
            json=payload,
            headers={"X-CSRF-Token": self.csrf_token},
        )
        response.raise_for_status()
        return response.json()

    def mixed_sources(self) -> list[dict[str, Any]]:
        return list(self.get("/speaker-reviews", status="mixed_speakers", limit=200))

    def suggestions(self, source_id: str, status: str = "all") -> list[dict[str, Any]]:
        return list(
            self.get(
                "/interview-turns",
                source_id=source_id,
                status=status,
                limit=5000,
            )
        )

    def review_pending(
        self,
        source_id: str,
        *,
        approve_iyin: bool = True,
    ) -> tuple[int, int]:
        pending = self.suggestions(source_id, "pending")
        iyin_ids = [
            str(item["id"])
            for item in pending
            if str(item["suggested_role"]) == "iyin"
        ]
        excluded_ids = [
            str(item["id"])
            for item in pending
            if str(item["suggested_role"]) != "iyin"
        ]
        approved = 0
        excluded = 0
        for suggestion_ids in batches(excluded_ids):
            result = self.post(
                "/interview-turns/review",
                {
                    "suggestion_ids": suggestion_ids,
                    "decision": "reject",
                    "note": (
                        "Automatically excluded from public RAG because OpenAI "
                        "classified the passage as interviewer, other, or uncertain."
                    ),
                },
            )
            excluded += int(result["reviewed_count"])
        if not approve_iyin:
            return approved, excluded
        for suggestion_ids in batches(iyin_ids):
            result = self.post(
                "/interview-turns/review",
                {
                    "suggestion_ids": suggestion_ids,
                    "decision": "approve_as_iyin",
                    "note": (
                        "Administrator authorized automatic approval of passages "
                        "OpenAI labelled as Iyin; timestamp citations retained."
                    ),
                },
            )
            approved += int(result["reviewed_count"])
        return approved, excluded

    def run(
        self,
        poll_seconds: float,
        *,
        exclude_only: bool = False,
        existing_only: bool = False,
    ) -> int:
        self.login()
        sources = self.mixed_sources()
        source_ids = {str(item["source_id"]) for item in sources}
        titles = {str(item["source_id"]): str(item["title"]) for item in sources}
        print(f"Found {len(sources)} mixed-speaker sources.", flush=True)

        completed: set[str] = set()
        queued: set[str] = set()
        approved_total = 0
        excluded_total = 0

        for source_id in source_ids:
            existing = self.suggestions(source_id)
            if existing:
                approved, excluded = self.review_pending(
                    source_id,
                    approve_iyin=not exclude_only,
                )
                approved_total += approved
                excluded_total += excluded
                completed.add(source_id)
                print(
                    f"Reviewed existing suggestions: {titles[source_id]} "
                    f"({approved} approved, {excluded} excluded).",
                    flush=True,
                )
                continue
            if exclude_only or existing_only:
                continue
            result = self.post(
                "/interview-turns/analyze",
                {"source_id": source_id},
            )
            queued.add(source_id)
            print(
                f"Queued: {titles[source_id]} ({result['job_id']}).",
                flush=True,
            )

        if exclude_only:
            print(
                f"Finished exclusion pass: {excluded_total} non-Iyin passages excluded.",
                flush=True,
            )
            return 0
        if existing_only:
            print(
                f"Finished existing-suggestion review: {approved_total} Iyin passages "
                f"approved and {excluded_total} non-Iyin passages excluded.",
                flush=True,
            )
            return 0

        failed: dict[str, str] = {}
        while queued - completed - failed.keys():
            jobs = [
                job
                for job in self.get("/ingestion-jobs")
                if job["job_type"] == "interview_turn_analysis"
                and str(job["payload"].get("source_id")) in queued
            ]
            latest_by_source: dict[str, dict[str, Any]] = {}
            for job in jobs:
                source_id = str(job["payload"]["source_id"])
                latest_by_source.setdefault(source_id, job)

            for source_id in sorted(queued - completed - failed.keys()):
                job = latest_by_source.get(source_id)
                if job is None:
                    continue
                if job["status"] == "failed":
                    failed[source_id] = str(job.get("error_details") or "Unknown failure")
                    print(
                        f"Failed: {titles[source_id]} — {failed[source_id]}",
                        flush=True,
                    )
                    continue
                if job["status"] != "succeeded":
                    continue
                approved, excluded = self.review_pending(source_id)
                approved_total += approved
                excluded_total += excluded
                completed.add(source_id)
                print(
                    f"Completed: {titles[source_id]} "
                    f"({approved} approved, {excluded} excluded).",
                    flush=True,
                )

            remaining = len(queued - completed - failed.keys())
            if remaining:
                statuses: dict[str, int] = {}
                for job in latest_by_source.values():
                    status = str(job["status"])
                    statuses[status] = statuses.get(status, 0) + 1
                print(
                    f"Waiting on {remaining} sources; job states: {statuses}.",
                    flush=True,
                )
                time.sleep(poll_seconds)

        print(
            f"Finished: {len(completed)}/{len(source_ids)} sources reviewed, "
            f"{approved_total} Iyin passages approved, "
            f"{excluded_total} non-Iyin passages excluded, "
            f"{len(failed)} source failures.",
            flush=True,
        )
        return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000/api/v1",
        help="Public API base URL.",
    )
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument(
        "--exclude-only",
        action="store_true",
        help="Reject pending non-Iyin passages without making provider calls.",
    )
    parser.add_argument(
        "--existing-only",
        action="store_true",
        help="Review saved suggestions without queueing unprocessed interviews.",
    )
    args = parser.parse_args()
    processor = InterviewProcessor(args.api_url)
    try:
        return processor.run(
            args.poll_seconds,
            exclude_only=args.exclude_only,
            existing_only=args.existing_only,
        )
    finally:
        processor.close()


if __name__ == "__main__":
    sys.exit(main())
