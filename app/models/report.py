"""Models for report generation metadata."""

from pydantic import BaseModel


class ReportMetadata(BaseModel):
    """Metadata describing a generated report artifact."""

    report_id: str
    format: str
    created_at: str
    document_count: int
    file_path: str
