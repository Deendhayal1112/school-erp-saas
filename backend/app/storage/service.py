"""
File Storage Orchestration Service.
"""

import logging
import uuid

from fastapi import UploadFile

from app.common.constants import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_FILE_SIZE_MB,
)
from app.core.config import settings
from app.exceptions.exceptions import BadRequestException
from app.storage.providers import (
    LocalStorageProvider,
    S3StorageProvider,
    StorageProvider,
)

logger = logging.getLogger(__name__)


class FileStorageService:
    """Manages files and validation checks across Local and S3 providers."""

    def __init__(self, provider: StorageProvider | None = None) -> None:
        if provider:
            self.provider = provider
        else:
            # Initialize default provider from configuration settings
            if settings.STORAGE_PROVIDER == "s3":
                self.provider = S3StorageProvider(
                    bucket_name=settings.S3_BUCKET_NAME,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION_NAME,
                )
            else:
                self.provider = LocalStorageProvider(
                    base_dir=settings.STORAGE_BASE_DIR,
                    base_url=settings.STORAGE_BASE_URL,
                )

    async def scan_file_virus(self, file_bytes: bytes) -> bool:
        """
        Scan file bytes for viruses.
        Placeholder implementation. Can be integrated with ClamAV or external scan API.
        """
        # Returns True if file is clean, False if infected/suspicious
        return True

    async def upload_file(
        self,
        file: UploadFile,
        allowed_extensions: set[str] | None = None,
        max_size_mb: int = MAX_FILE_SIZE_MB,
        folder: str = "general",
    ) -> str:
        """
        Validates size, format, extension type, scans for viruses, and uploads target file.
        Returns the download URL path.
        """
        # 1. Read file bytes
        file_bytes = await file.read()
        await file.seek(0)  # Reset pointer position

        # 2. Check file size limits
        size_mb = len(file_bytes) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise BadRequestException(
                f"File size exceeds the limit of {max_size_mb}MB."
            )

        # 3. Validate file extension
        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        target_allowed = allowed_extensions or ALLOWED_IMAGE_EXTENSIONS.union(
            ALLOWED_DOCUMENT_EXTENSIONS
        )
        if ext not in target_allowed:
            raise BadRequestException(f"Unsupported file extension: .{ext}")

        # 4. Perform virus check
        is_clean = await self.scan_file_virus(file_bytes)
        if not is_clean:
            raise BadRequestException("File safety scan failed. Malware detected.")

        # 5. Build unique key
        key = f"{folder}/{uuid.uuid4().hex}.{ext}"
        content_type = file.content_type or "application/octet-stream"

        # 6. Upload via active provider
        logger.info("Uploading file key=%s via storage provider", key)
        return await self.provider.upload(key, file_bytes, content_type)

    async def delete_file(self, file_url_or_key: str) -> None:
        """Deletes a file key from the storage backend."""
        # Extract storage key from URL path
        key = file_url_or_key
        # If it contains base_url prefix, strip it
        if "/" in key:
            # e.g., /media/general/abc.png -> general/abc.png
            if key.startswith(settings.STORAGE_BASE_URL):
                key = key.replace(settings.STORAGE_BASE_URL, "", 1).lstrip("/")
            elif "s3.amazonaws.com" in key:
                key = key.split(".com/")[-1]

        logger.info("Deleting file key=%s", key)
        await self.provider.delete(key)

    async def generate_signed_url(
        self, file_url_or_key: str, expires_in: int = 3600
    ) -> str:
        """Generates pre-signed link for retrieval."""
        key = file_url_or_key
        if key.startswith(settings.STORAGE_BASE_URL):
            key = key.replace(settings.STORAGE_BASE_URL, "", 1).lstrip("/")
        elif "s3.amazonaws.com" in key:
            key = key.split(".com/")[-1]

        return await self.provider.download_url(key, expires_in)
