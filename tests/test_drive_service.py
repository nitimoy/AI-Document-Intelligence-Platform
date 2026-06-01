"""Unit tests for Google Drive service integration logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.models.document import DocumentMetadata
from app.services.drive_service import DriveService
from app.services.storage_service import StorageService
from app.utils.exceptions import (
    AuthenticationError,
    ConfigurationError,
    FileDownloadError,
)


def build_settings(tmp_path: Path) -> Settings:
    """Create settings with temp service account file and download directory."""

    service_account_file = tmp_path / "service-account.json"
    service_account_file.write_text("{}", encoding="utf-8")

    return Settings(
        google_drive_folder_id="folder_123",
        google_service_account_file=str(service_account_file),
        download_dir=str(tmp_path / "downloads"),
    )


@patch("app.services.drive_service.build")
@patch(
    "app.services.drive_service.service_account.Credentials.from_service_account_file"
)
def test_authentication_success(
    mock_from_file: MagicMock, mock_build: MagicMock, tmp_path: Path
) -> None:
    """DriveService should authenticate and return a Drive resource client."""

    settings = build_settings(tmp_path)
    mock_from_file.return_value = MagicMock(name="credentials")
    mock_build.return_value = MagicMock(name="drive_service")

    service = DriveService(settings)
    client = service.authenticate()

    assert client is mock_build.return_value
    mock_from_file.assert_called_once()
    mock_build.assert_called_once()


@patch("app.services.drive_service.build", side_effect=RuntimeError("auth failed"))
@patch(
    "app.services.drive_service.service_account.Credentials.from_service_account_file"
)
def test_authentication_error_raises(
    mock_from_file: MagicMock, _: MagicMock, tmp_path: Path
) -> None:
    """DriveService should raise AuthenticationError when auth repeatedly fails."""

    settings = build_settings(tmp_path)
    mock_from_file.return_value = MagicMock(name="credentials")

    service = DriveService(settings)

    with pytest.raises(AuthenticationError):
        service.authenticate()


@patch("app.services.drive_service.build")
@patch(
    "app.services.drive_service.service_account.Credentials.from_service_account_file"
)
def test_list_files_filters_supported_types(
    mock_from_file: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """DriveService.list_files should include only supported MIME types."""

    settings = build_settings(tmp_path)

    files_api = MagicMock()
    files_api.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "1",
                "name": "doc.pdf",
                "mimeType": "application/pdf",
                "size": "12",
                "createdTime": "2026-06-01T00:00:00Z",
                "modifiedTime": "2026-06-01T00:00:00Z",
            },
            {
                "id": "2",
                "name": "notes.txt",
                "mimeType": "text/plain",
                "size": "5",
            },
            {
                "id": "3",
                "name": "sheet.xlsx",
                "mimeType": (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            },
        ]
    }

    mock_drive = MagicMock()
    mock_drive.files.return_value = files_api

    mock_from_file.return_value = MagicMock(name="credentials")
    mock_build.return_value = mock_drive

    service = DriveService(settings)
    listed = service.list_files()

    assert len(listed) == 2
    assert listed[0].file_name == "doc.pdf"
    assert listed[1].file_name == "notes.txt"


@patch("app.services.drive_service.MediaIoBaseDownload")
@patch("app.services.drive_service.build")
@patch(
    "app.services.drive_service.service_account.Credentials.from_service_account_file"
)
def test_download_workflow(
    mock_from_file: MagicMock,
    mock_build: MagicMock,
    mock_downloader_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """download_all_supported_files should download all listed supported files."""

    settings = build_settings(tmp_path)

    files_api = MagicMock()
    files_api.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "1",
                "name": "a.pdf",
                "mimeType": "application/pdf",
            },
            {
                "id": "2",
                "name": "b.txt",
                "mimeType": "text/plain",
            },
        ]
    }
    files_api.get_media.return_value = MagicMock(name="media_request")

    mock_drive = MagicMock()
    mock_drive.files.return_value = files_api

    mock_from_file.return_value = MagicMock(name="credentials")
    mock_build.return_value = mock_drive

    downloader_a = MagicMock()
    downloader_a.next_chunk.side_effect = [(None, False), (None, True)]
    downloader_b = MagicMock()
    downloader_b.next_chunk.side_effect = [(None, False), (None, True)]
    mock_downloader_cls.side_effect = [downloader_a, downloader_b]

    service = DriveService(settings)
    result = service.download_all_supported_files()

    assert result == {"downloaded": 2, "failed": 0}


def test_configuration_error_for_missing_service_account_file(tmp_path: Path) -> None:
    """Settings validation should fail for missing service account path."""

    settings = Settings(
        google_drive_folder_id="folder_123",
        google_service_account_file=str(tmp_path / "missing.json"),
        download_dir=str(tmp_path / "downloads"),
    )
    service = DriveService(settings)

    with pytest.raises(ConfigurationError):
        service.authenticate()


@patch(
    "app.services.drive_service.MediaIoBaseDownload",
    side_effect=RuntimeError("download failed"),
)
@patch("app.services.drive_service.build")
@patch(
    "app.services.drive_service.service_account.Credentials.from_service_account_file"
)
def test_download_error_raises_file_download_error(
    mock_from_file: MagicMock,
    mock_build: MagicMock,
    _: MagicMock,
    tmp_path: Path,
) -> None:
    """download_file should raise FileDownloadError when transfer fails."""

    settings = build_settings(tmp_path)

    files_api = MagicMock()
    files_api.get_media.return_value = MagicMock(name="media_request")

    mock_drive = MagicMock()
    mock_drive.files.return_value = files_api

    mock_from_file.return_value = MagicMock(name="credentials")
    mock_build.return_value = mock_drive

    service = DriveService(settings)
    metadata = DocumentMetadata(
        file_id="1",
        file_name="broken.pdf",
        mime_type="application/pdf",
    )

    with pytest.raises(FileDownloadError):
        service.download_file(metadata)


class InMemoryStorageService(StorageService):
    """Simple in-memory-like storage adapter for dependency injection tests."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def resolve_path(self, file_name: str) -> Path:
        self.base_path.mkdir(parents=True, exist_ok=True)
        return self.base_path / file_name

    def open_binary_writer(self, file_name: str):
        return self.resolve_path(file_name).open("wb")


@patch("app.services.drive_service.MediaIoBaseDownload")
@patch("app.services.drive_service.build")
@patch(
    "app.services.drive_service.service_account.Credentials.from_service_account_file"
)
def test_download_with_injected_storage_service(
    mock_from_file: MagicMock,
    mock_build: MagicMock,
    mock_downloader_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """DriveService should use injected storage abstraction for destination writes."""

    settings = build_settings(tmp_path)
    storage_base = tmp_path / "custom-storage"
    storage = InMemoryStorageService(storage_base)

    files_api = MagicMock()
    files_api.get_media.return_value = MagicMock(name="media_request")

    mock_drive = MagicMock()
    mock_drive.files.return_value = files_api

    mock_from_file.return_value = MagicMock(name="credentials")
    mock_build.return_value = mock_drive

    downloader = MagicMock()
    downloader.next_chunk.side_effect = [(None, False), (None, True)]
    mock_downloader_cls.return_value = downloader

    service = DriveService(settings=settings, storage_service=storage)
    metadata = DocumentMetadata(
        file_id="1",
        file_name="custom.pdf",
        mime_type="application/pdf",
    )

    result = service.download_file(metadata)
    assert result.download_path == str(storage_base / "custom.pdf")


@patch("app.services.drive_service.MediaIoBaseDownload")
@patch("app.services.drive_service.build")
@patch(
    "app.services.drive_service.service_account.Credentials.from_service_account_file"
)
def test_download_reuses_existing_local_file(
    mock_from_file: MagicMock,
    mock_build: MagicMock,
    mock_downloader_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """download_file should reuse a local copy instead of downloading again."""

    settings = build_settings(tmp_path)

    files_api = MagicMock()
    files_api.get_media.return_value = MagicMock(name="media_request")

    mock_drive = MagicMock()
    mock_drive.files.return_value = files_api

    mock_from_file.return_value = MagicMock(name="credentials")
    mock_build.return_value = mock_drive

    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    existing_file = downloads_dir / "cached.pdf"
    existing_file.write_bytes(b"cached content")

    service = DriveService(settings)
    metadata = DocumentMetadata(
        file_id="1",
        file_name="cached.pdf",
        mime_type="application/pdf",
    )

    result = service.download_file(metadata)

    assert result.download_path == str(existing_file)
    mock_downloader_cls.assert_not_called()
