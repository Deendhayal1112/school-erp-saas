"""
File Storage Abstraction and Provider Implementations.
"""

import abc
import os
from typing import Any


class StorageProvider(abc.ABC):
    """Abstract interface defining required file storage backend operations."""

    @abc.abstractmethod
    async def upload(self, key: str, file_bytes: bytes, content_type: str) -> str:
        """
        Uploads raw file bytes to the target key.
        Returns the resolved file path or absolute download URL string.
        """
        pass

    @abc.abstractmethod
    async def download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generates a temporary signed download link referencing the target key."""
        pass

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        """Deletes the target file from the storage backend."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local Disk implementation of the StorageProvider interface."""

    def __init__(self, base_dir: str = "media", base_url: str = "/media") -> None:
        self.base_dir = base_dir
        self.base_url = base_url
        os.makedirs(self.base_dir, exist_ok=True)

    async def upload(self, key: str, file_bytes: bytes, content_type: str) -> str:
        file_path = os.path.join(self.base_dir, key)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return f"{self.base_url}/{key}"

    async def download_url(self, key: str, expires_in: int = 3600) -> str:
        # Local files do not need complex pre-signed URLs in dev; returns direct web route path
        return f"{self.base_url}/{key}"

    async def delete(self, key: str) -> None:
        file_path = os.path.join(self.base_dir, key)
        if os.path.exists(file_path):
            os.remove(file_path)


class S3StorageProvider(StorageProvider):
    """AWS S3 implementation of the StorageProvider interface."""

    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name

    def _get_client(self) -> Any:
        try:
            import boto3

            return boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name,
            )
        except ImportError:
            # Fallback simulator or exception raised if executed in production without boto3
            raise RuntimeError("boto3 package is required to execute S3 operations.")

    async def upload(self, key: str, file_bytes: bytes, content_type: str) -> str:
        client = self._get_client()
        import asyncio

        # Run synchronous boto3 upload call in thread executor to prevent event loop blocking
        await asyncio.to_thread(
            client.put_object,
            Bucket=self.bucket_name,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return (
            f"https://{self.bucket_name}.s3.{self.region_name or 'amazonaws'}.com/{key}"
        )

    async def download_url(self, key: str, expires_in: int = 3600) -> str:
        client = self._get_client()
        import asyncio

        url = await asyncio.to_thread(
            client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )
        return str(url)

    async def delete(self, key: str) -> None:
        client = self._get_client()
        import asyncio

        await asyncio.to_thread(
            client.delete_object,
            Bucket=self.bucket_name,
            Key=key,
        )
