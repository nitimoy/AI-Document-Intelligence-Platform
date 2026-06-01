"""Google Drive integration service."""

from __future__ import annotations

from typing import Any

import httplib2
from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_httplib2 import AuthorizedHttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings
from app.models.document import DocumentMetadata
from app.services.parser_service import LEGACY_DOC_SUPPORTED
from app.services.storage_service import LocalStorageService, StorageService
from app.utils.exceptions import AuthenticationError, FileDownloadError
from app.utils.logger import get_logger

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_DOCS_MIME_TYPE = "application/vnd.google-apps.document"
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    DOCX_MIME_TYPE,
    GOOGLE_DOCS_MIME_TYPE,
    "text/plain",
}

if LEGACY_DOC_SUPPORTED:
    SUPPORTED_MIME_TYPES.add("application/msword")


class DriveService:
    """Encapsulates Google Drive authentication, listing, and download operations."""

    def __init__(
        self, settings: Settings, storage_service: StorageService | None = None
    ) -> None:
        self._settings = settings
        self._storage_service = storage_service or LocalStorageService(
            settings.download_dir
        )
        self._logger = get_logger(__name__)
        self._service: Resource | None = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
        retry=retry_if_exception_type(AuthenticationError),
        reraise=True,
    )
    def authenticate(self) -> Resource:
        """Authenticate using a service account and create a Drive API client."""

        self._settings.validate_google_drive_config()

        try:
            credentials = service_account.Credentials.from_service_account_file(
                self._settings.google_service_account_file,
                scopes=[DRIVE_READONLY_SCOPE],
            )
            authorized_http = AuthorizedHttp(
                credentials,
                http=httplib2.Http(timeout=self._settings.drive_download_timeout_seconds),
            )
            self._service = build(
                "drive",
                "v3",
                http=authorized_http,
                cache_discovery=False,
            )
            self._logger.info("Google Drive authentication succeeded")
            return self._service
        except Exception as exc:  # pragma: no cover - covered through retry behavior
            self._logger.error("Google Drive authentication failed: %s", exc)
            raise AuthenticationError(
                "Failed to authenticate with Google Drive"
            ) from exc

    def _get_service(self) -> Resource:
        """Return an existing service client or authenticate if none exists."""

        return self._service or self.authenticate()

    @staticmethod
    def _to_document_metadata(raw_file: dict[str, Any]) -> DocumentMetadata:
        """Convert a Drive API file payload into the platform metadata model."""

        raw_size = raw_file.get("size")
        size_value = int(raw_size) if raw_size is not None else None

        return DocumentMetadata(
            file_id=raw_file["id"],
            file_name=raw_file["name"],
            mime_type=raw_file["mimeType"],
            size=size_value,
            created_time=raw_file.get("createdTime"),
            modified_time=raw_file.get("modifiedTime"),
        )

    @staticmethod
    def _resolve_download_name(file_metadata: DocumentMetadata) -> str:
        """Normalize download filenames for parser-friendly local processing."""

        file_name = file_metadata.file_name
        suffix = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""

        if file_metadata.mime_type == GOOGLE_DOCS_MIME_TYPE:
            if suffix != "docx":
                if suffix == "":
                    return f"{file_name}.docx"
                return f"{file_name.rsplit('.', 1)[0]}.docx"
        if file_metadata.mime_type == "application/msword" and suffix == "":
            return f"{file_name}.doc"

        return file_name

    def list_files(self) -> list[DocumentMetadata]:
        """List supported files from the configured Drive folder."""

        service = self._get_service()
        query = (
            f"'{self._settings.google_drive_folder_id}' in parents and trashed=false"
        )
        fields = "nextPageToken, files(id,name,mimeType,size,createdTime,modifiedTime)"

        files: list[DocumentMetadata] = []
        page_token: str | None = None

        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    fields=fields,
                    pageToken=page_token,
                    pageSize=100,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )

            raw_files = response.get("files", [])
            filtered = [
                self._to_document_metadata(file_info)
                for file_info in raw_files
                if file_info.get("mimeType") in SUPPORTED_MIME_TYPES
            ]
            files.extend(filtered)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        self._logger.info(
            "Discovered %s supported files in Google Drive folder", len(files)
        )
        return files

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
        retry=retry_if_exception_type(FileDownloadError),
        reraise=True,
    )
    def download_file(self, file_metadata: DocumentMetadata) -> DocumentMetadata:
        """Download one supported file to the configured local download directory."""

        service = self._get_service()
        download_name = self._resolve_download_name(file_metadata)
        destination_path = self._storage_service.resolve_path(download_name)

        if destination_path.exists() and destination_path.stat().st_size > 0:
            file_metadata.file_name = download_name
            if file_metadata.mime_type == GOOGLE_DOCS_MIME_TYPE:
                file_metadata.mime_type = DOCX_MIME_TYPE
            file_metadata.download_path = str(destination_path)
            self._logger.info(
                "Reused existing file %s from %s", file_metadata.file_name, destination_path
            )
            return file_metadata

        try:
            if file_metadata.mime_type == GOOGLE_DOCS_MIME_TYPE:
                request = service.files().export_media(
                    fileId=file_metadata.file_id,
                    mimeType=DOCX_MIME_TYPE,
                )
            else:
                request = service.files().get_media(fileId=file_metadata.file_id)

            with self._storage_service.open_binary_writer(download_name) as output:
                downloader = MediaIoBaseDownload(output, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk(
                        num_retries=self._settings.drive_download_chunk_retries
                    )

            file_metadata.file_name = download_name
            if file_metadata.mime_type == GOOGLE_DOCS_MIME_TYPE:
                file_metadata.mime_type = DOCX_MIME_TYPE
            file_metadata.download_path = str(destination_path)
            self._logger.info(
                "Downloaded file %s to %s", file_metadata.file_name, destination_path
            )
            return file_metadata
        except Exception as exc:
            self._logger.error(
                "Failed to download file %s: %s", file_metadata.file_name, exc
            )
            raise FileDownloadError(
                f"Failed to download file: {file_metadata.file_name}"
            ) from exc

    def download_all_supported_files(self) -> dict[str, int]:
        """Download all supported files and return success/failure counts."""

        files = self.list_files()
        downloaded = 0
        failed = 0

        for file_metadata in files:
            try:
                self.download_file(file_metadata)
                downloaded += 1
            except FileDownloadError:
                failed += 1

        self._logger.info(
            "Downloads completed. downloaded=%s failed=%s", downloaded, failed
        )
        if failed > 0:
            self._logger.warning("Some file downloads failed")

        return {"downloaded": downloaded, "failed": failed}
