"""Data models for document metadata."""

from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    """Metadata for a file discovered and optionally downloaded from Google Drive."""

    file_id: str
    file_name: str
    mime_type: str
    size: int | None = None
    download_path: str | None = None
    created_time: str | None = None
    modified_time: str | None = None
