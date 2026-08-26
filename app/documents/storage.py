from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol
from uuid import UUID

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings


class ObjectNotFoundError(Exception):
    pass


class StorageUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    required_headers: dict[str, str]


@dataclass(frozen=True)
class StoredObject:
    size_bytes: int
    content_type: str | None
    metadata: dict[str, str]


@dataclass(frozen=True)
class StoredObjectContent:
    size_bytes: int
    metadata: dict[str, str]
    body: bytes


class DocumentStorage(Protocol):
    def create_upload_url(
        self,
        *,
        bucket: str,
        key: str,
        document_id: UUID,
        file_size_bytes: int,
        expires_in: int,
    ) -> PresignedUpload: ...

    def head_object(self, *, bucket: str, key: str) -> StoredObject: ...

    def read_object(self, *, bucket: str, key: str) -> StoredObjectContent: ...
    def write_object(
        self,
        *,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str,
    ) -> None: ...


class S3DocumentStorage:
    def __init__(self, *, region_name: str) -> None:
        import boto3  # type: ignore[import-untyped]

        self.client = boto3.client(
            "s3",
            region_name=region_name,
            endpoint_url=f"https://s3.{region_name}.amazonaws.com",
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )

    def create_upload_url(
        self,
        *,
        bucket: str,
        key: str,
        document_id: UUID,
        file_size_bytes: int,
        expires_in: int,
    ) -> PresignedUpload:
        document_id_text = str(document_id)
        try:
            url = self.client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "ContentType": "application/pdf",
                    "ContentLength": file_size_bytes,
                    "Metadata": {"document-id": document_id_text},
                },
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailableError("Could not generate upload URL") from exc
        return PresignedUpload(
            url=url,
            required_headers={
                "Content-Type": "application/pdf",
                "x-amz-meta-document-id": document_id_text,
            },
        )

    def head_object(self, *, bucket: str, key: str) -> StoredObject:
        try:
            response = self.client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectNotFoundError(key) from exc
            raise StorageUnavailableError("Could not inspect uploaded object") from exc
        except BotoCoreError as exc:
            raise StorageUnavailableError("Could not inspect uploaded object") from exc
        return StoredObject(
            size_bytes=int(response["ContentLength"]),
            content_type=response.get("ContentType"),
            metadata={
                str(key).casefold(): str(value)
                for key, value in response.get("Metadata", {}).items()
            },
        )

    def write_object(
        self,
        *,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str,
    ) -> None:
        try:
            self.client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailableError("Could not write document object") from exc

    def read_object(self, *, bucket: str, key: str) -> StoredObjectContent:
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            stream = response["Body"]
            try:
                body = stream.read()
            finally:
                stream.close()
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectNotFoundError(key) from exc
            raise StorageUnavailableError("Could not read uploaded object") from exc
        except (BotoCoreError, OSError) as exc:
            raise StorageUnavailableError("Could not read uploaded object") from exc
        if not isinstance(body, bytes):
            body = bytes(body)
        return StoredObjectContent(
            size_bytes=int(response["ContentLength"]),
            metadata={
                str(name).casefold(): str(value)
                for name, value in response.get("Metadata", {}).items()
            },
            body=body,
        )


@lru_cache
def get_document_storage() -> S3DocumentStorage:
    settings = get_settings()
    return S3DocumentStorage(region_name=settings.aws_region)
