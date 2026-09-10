"""Provider-neutral private object storage boundary."""

from __future__ import annotations

from io import BytesIO
from typing import Protocol

from app.core.config import Settings


class ObjectStorage(Protocol):
    def put_object(self, object_key: str, body: bytes, content_type: str) -> None: ...
    def delete_object(self, object_key: str) -> None: ...
    def create_read_url(self, object_key: str, expires_seconds: int = 300) -> str: ...


class S3ObjectStorage:
    def __init__(self, settings: Settings):
        if (
            not settings.s3_bucket
            or not settings.s3_access_key_id
            or not settings.s3_secret_access_key
        ):
            raise ValueError("S3 bucket and credentials are required")
        import boto3

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        )

    def put_object(self, object_key: str, body: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=object_key, Body=BytesIO(body), ContentType=content_type
        )

    def delete_object(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def create_read_url(self, object_key: str, expires_seconds: int = 300) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=expires_seconds,
        )


def build_object_storage(settings: Settings) -> ObjectStorage | None:
    values = (
        settings.s3_endpoint_url,
        settings.s3_bucket,
        settings.s3_access_key_id,
        settings.s3_secret_access_key,
        settings.s3_region,
    )
    if any(values) and not all(values):
        raise ValueError("S3 endpoint, bucket, credentials, and region must be configured together")
    return S3ObjectStorage(settings) if all(values) else None
