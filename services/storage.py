import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import boto3
from apps.api.afs.config import Settings
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class StoredArtifact:
    object_key: str
    sha256: str
    byte_size: int
    created: bool


class RawEvidenceStore:
    """Content-addressed immutable S3 storage for original evidence bytes."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.settings.s3_bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.settings.s3_bucket)

    def put_immutable(self, data: bytes, media_type: str, *, suffix: str = "bin") -> StoredArtifact:
        digest = hashlib.sha256(data).hexdigest()
        today = datetime.now(UTC).strftime("%Y/%m/%d")
        key = f"raw/{today}/{digest}.{suffix.lstrip('.')}"
        created = True
        try:
            self.client.put_object(
                Bucket=self.settings.s3_bucket,
                Key=key,
                Body=data,
                ContentType=media_type,
                Metadata={"sha256": digest, "immutable": "true"},
                IfNoneMatch="*",
            )
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") in {409, 412}:
                created = False
            else:
                raise
        return StoredArtifact(key, digest, len(data), created)
