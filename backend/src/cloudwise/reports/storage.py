"""Report object storage boundary with local and S3 implementations."""

from pathlib import Path
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from cloudwise.core.config import Settings


class ReportStorageError(RuntimeError):
    """Safe report object storage failure."""


class ReportStorage(Protocol):
    """Minimal private object storage operations."""

    def put(self, key: str, content: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalReportStorage:
    """Private filesystem storage for local development."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()

    def put(self, key: str, content: bytes, content_type: str) -> None:
        del content_type
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        except OSError as exc:
            raise ReportStorageError("REPORT_STORAGE_WRITE_FAILED") from exc

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except OSError as exc:
            raise ReportStorageError("REPORT_STORAGE_READ_FAILED") from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise ReportStorageError("REPORT_STORAGE_DELETE_FAILED") from exc

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ReportStorageError("INVALID_REPORT_STORAGE_KEY")
        return path


class S3ReportStorage:
    """Private S3 object storage for staging and production."""

    def __init__(self, bucket: str) -> None:
        self._bucket = bucket
        self._client = boto3.client("s3")

    def put(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )
        except (ClientError, BotoCoreError) as exc:
            raise ReportStorageError("REPORT_STORAGE_WRITE_FAILED") from exc

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            content = response["Body"].read()
            if not isinstance(content, bytes | bytearray):
                raise ReportStorageError("REPORT_STORAGE_READ_FAILED")
            return bytes(content)
        except (ClientError, BotoCoreError, KeyError) as exc:
            raise ReportStorageError("REPORT_STORAGE_READ_FAILED") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise ReportStorageError("REPORT_STORAGE_DELETE_FAILED") from exc


def build_report_storage(settings: Settings) -> ReportStorage:
    """Build the configured report storage provider."""
    if settings.report_storage_provider == "s3":
        if not settings.report_s3_bucket:
            raise ReportStorageError("REPORT_STORAGE_NOT_CONFIGURED")
        return S3ReportStorage(settings.report_s3_bucket)
    return LocalReportStorage(settings.report_local_directory)
