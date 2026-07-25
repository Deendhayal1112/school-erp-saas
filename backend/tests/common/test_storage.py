"""
Tests for File Storage Service.
"""

import os
from io import BytesIO

import pytest
from fastapi import UploadFile

from app.exceptions.exceptions import BadRequestException
from app.storage.service import FileStorageService


@pytest.mark.asyncio
async def test_file_storage_local_provider():
    storage = FileStorageService()

    # Simulate a file upload
    file_content = b"fake image bytes content"
    upload_file = UploadFile(
        file=BytesIO(file_content),
        filename="test_avatar.png",
        headers={"content-type": "image/png"},
    )

    # 1. Test successful upload
    url = await storage.upload_file(
        file=upload_file,
        folder="avatars",
    )
    assert "/media/avatars/" in url
    assert url.endswith(".png")

    # Verify file exists on local disk
    local_path = url.replace("/media", "media", 1)
    assert os.path.exists(local_path)

    # 2. Test signed URL generation
    signed_url = await storage.generate_signed_url(url)
    assert signed_url == url

    # 3. Test delete operation
    await storage.delete_file(url)
    assert not os.path.exists(local_path)


@pytest.mark.asyncio
async def test_file_storage_size_and_extension_validation():
    storage = FileStorageService()

    # 1. Size violation
    large_content = b"x" * (11 * 1024 * 1024)  # 11MB (limit is 10MB)
    upload_file_large = UploadFile(
        file=BytesIO(large_content),
        filename="huge_file.zip",
        headers={"content-type": "application/zip"},
    )
    with pytest.raises(BadRequestException) as exc:
        await storage.upload_file(upload_file_large, max_size_mb=10)
    assert "size" in str(exc.value).lower()

    # 2. Unsupported extension format violation
    invalid_ext_file = UploadFile(
        file=BytesIO(b"executable content"),
        filename="malicious.exe",
        headers={"content-type": "application/x-msdownload"},
    )
    with pytest.raises(BadRequestException) as exc:
        await storage.upload_file(invalid_ext_file, allowed_extensions={"png"})
    assert "extension" in str(exc.value).lower()
