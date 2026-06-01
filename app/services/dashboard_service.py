"""Dashboard service for summary listing, metrics, search, and filtering."""

from __future__ import annotations

from pathlib import Path

from app.models.summary import SummaryResult
from app.services.cache_service import CacheService
from app.utils.logger import get_logger


class DashboardService:
    """Provides dashboard-ready summary data and derived statistics."""

    def __init__(self, cache_service: CacheService) -> None:
        self._cache_service = cache_service
        self._logger = get_logger(__name__)

    def load_summaries(self) -> list[SummaryResult]:
        """Load all summaries available in cache storage."""

        self._logger.info("Dashboard access")
        return self._cache_service.get_all_summaries()

    @staticmethod
    def _infer_file_type(file_name: str) -> str:
        """Infer a normalized file type label from filename extension."""

        suffix = Path(file_name).suffix.lower().lstrip(".")
        if suffix in {"pdf", "docx", "txt"}:
            return suffix.upper()
        return "UNKNOWN"

    def get_file_type(self, file_name: str) -> str:
        """Public accessor for normalized file type labels."""

        return self._infer_file_type(file_name)

    def enrich_summaries(
        self, summaries: list[SummaryResult]
    ) -> list[dict[str, object]]:
        """Transform summary records into dashboard-friendly rows."""

        rows: list[dict[str, object]] = []
        for summary in summaries:
            rows.append(
                {
                    "file_name": summary.file_name,
                    "file_type": self._infer_file_type(summary.file_name),
                    "summary_preview": summary.summary[:140]
                    + ("..." if len(summary.summary) > 140 else ""),
                    "summary": summary.summary,
                    "chunk_count": summary.chunk_count,
                    "processing_time_seconds": summary.processing_time_seconds,
                    "created_at": summary.created_at,
                    "model_used": summary.model_used,
                    "document_hash": summary.document_hash,
                    "summary_type": summary.summary_type,
                }
            )
        return rows

    def search_summaries(
        self, rows: list[dict[str, object]], query: str | None
    ) -> list[dict[str, object]]:
        """Perform case-insensitive search over file names and summary content."""

        if not query:
            return rows

        query_lower = query.strip().lower()
        self._logger.info("Dashboard search query: %s", query)

        return [
            row
            for row in rows
            if query_lower in str(row["file_name"]).lower()
            or query_lower in str(row["summary"]).lower()
        ]

    def filter_summaries(
        self, rows: list[dict[str, object]], file_type: str | None
    ) -> list[dict[str, object]]:
        """Filter rows by file type (PDF, DOCX, TXT, or ALL)."""

        selected = (file_type or "ALL").upper()
        self._logger.info("Dashboard filter usage: %s", selected)

        if selected == "ALL":
            return rows

        allowed = {"PDF", "DOCX", "TXT"}
        if selected not in allowed:
            return rows

        return [row for row in rows if row["file_type"] == selected]

    def calculate_metrics(self, rows: list[dict[str, object]]) -> dict[str, object]:
        """Compute dashboard metrics from currently visible summary rows."""

        total_summaries = len(rows)
        total_documents = len({row["document_hash"] for row in rows})
        processing_times: list[float] = []
        for row in rows:
            value = row.get("processing_time_seconds")
            if isinstance(value, (int, float)):
                processing_times.append(float(value))

        average_processing_time = (
            round(sum(processing_times) / total_summaries, 3)
            if total_summaries > 0 and processing_times
            else 0.0
        )

        cache_files = total_summaries
        cache_hit_percentage = (
            f"{round((cache_files / total_summaries) * 100, 1)}%"
            if total_summaries > 0
            else "0%"
        )

        return {
            "total_documents": total_documents,
            "total_summaries": total_summaries,
            "cached_summaries": total_summaries,
            "average_processing_time": average_processing_time,
            "cache_files": cache_files,
            "cache_hit_percentage": cache_hit_percentage,
        }

    def get_summary_by_hash(self, document_hash: str) -> SummaryResult | None:
        """Retrieve one summary by its document hash."""

        self._logger.info("Summary detail access for hash: %s", document_hash)
        return self._cache_service.get_cached_summary(document_hash)
