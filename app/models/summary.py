"""Summary result model for AI-generated document summaries."""

from pydantic import BaseModel


class SummaryResult(BaseModel):
    """Represents summarized output and metadata for one document."""

    file_name: str
    summary: str
    summary_type: str
    chunk_count: int
    processing_time_seconds: float
    model_used: str
    document_hash: str
    created_at: str
