"""Data model for parsed document output."""

from pydantic import BaseModel


class ParsedDocument(BaseModel):
    """Represents extracted content and parsing metadata for a document."""

    file_name: str
    file_type: str
    file_path: str
    content: str
    word_count: int
    character_count: int
    extraction_success: bool
    error_message: str | None = None
