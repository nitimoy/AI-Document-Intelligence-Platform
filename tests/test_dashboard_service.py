"""Unit tests for dashboard service behavior."""

from pathlib import Path

from app.config import Settings
from app.models.summary import SummaryResult
from app.services.cache_service import CacheService
from app.services.dashboard_service import DashboardService


def build_dashboard_service(tmp_path: Path) -> DashboardService:
    """Create dashboard service backed by a temporary cache directory."""

    settings = Settings(cache_dir=str(tmp_path / "cache"))
    cache_service = CacheService(settings.cache_dir)
    return DashboardService(cache_service=cache_service)


def seed_summary(
    cache_service: CacheService, file_name: str, summary: str, document_hash: str
) -> SummaryResult:
    """Create and persist one summary fixture."""

    item = SummaryResult(
        file_name=file_name,
        summary=summary,
        summary_type="small",
        chunk_count=1,
        processing_time_seconds=0.4,
        model_used="gpt-4o",
        document_hash=document_hash,
        created_at="2026-06-01T00:00:00+00:00",
    )
    cache_service.save_summary(item)
    return item


def test_metric_calculations(tmp_path: Path) -> None:
    """Dashboard metrics should compute counts and average processing time."""

    service = build_dashboard_service(tmp_path)

    cache_service = CacheService(str(tmp_path / "cache"))
    seed_summary(cache_service, "one.pdf", "A concise summary with details", "hash-1")
    second = seed_summary(
        cache_service, "two.docx", "Another summary body with findings", "hash-2"
    )

    second.processing_time_seconds = 0.6
    cache_service.save_summary(second)

    rows = service.enrich_summaries(service.load_summaries())
    metrics = service.calculate_metrics(rows)

    assert metrics["total_documents"] == 2
    assert metrics["total_summaries"] == 2
    assert metrics["cached_summaries"] == 2
    assert metrics["average_processing_time"] == 0.5
    assert metrics["cache_files"] == 2


def test_search_case_insensitive(tmp_path: Path) -> None:
    """Search should match file names and summary content case-insensitively."""

    service = build_dashboard_service(tmp_path)
    cache_service = CacheService(str(tmp_path / "cache"))

    seed_summary(cache_service, "alpha.pdf", "Contains strategic FINDINGS", "hash-1")
    seed_summary(cache_service, "beta.txt", "No keyword present", "hash-2")

    rows = service.enrich_summaries(service.load_summaries())

    by_name = service.search_summaries(rows, "ALPHA")
    by_content = service.search_summaries(rows, "findings")

    assert len(by_name) == 1
    assert by_name[0]["file_name"] == "alpha.pdf"
    assert len(by_content) == 1
    assert by_content[0]["file_name"] == "alpha.pdf"


def test_filtering_by_file_type(tmp_path: Path) -> None:
    """Filter should keep only requested file type rows."""

    service = build_dashboard_service(tmp_path)
    cache_service = CacheService(str(tmp_path / "cache"))

    seed_summary(cache_service, "alpha.pdf", "Summary one", "hash-1")
    seed_summary(cache_service, "beta.docx", "Summary two", "hash-2")
    seed_summary(cache_service, "gamma.txt", "Summary three", "hash-3")

    rows = service.enrich_summaries(service.load_summaries())

    pdf_only = service.filter_summaries(rows, "PDF")
    all_rows = service.filter_summaries(rows, "ALL")

    assert len(pdf_only) == 1
    assert pdf_only[0]["file_type"] == "PDF"
    assert len(all_rows) == 3


def test_summary_retrieval(tmp_path: Path) -> None:
    """Summary retrieval by hash should return expected record."""

    service = build_dashboard_service(tmp_path)
    cache_service = CacheService(str(tmp_path / "cache"))
    seeded = seed_summary(cache_service, "alpha.pdf", "Detailed summary", "hash-1")

    fetched = service.get_summary_by_hash("hash-1")
    missing = service.get_summary_by_hash("missing-hash")

    assert fetched is not None
    assert fetched.file_name == seeded.file_name
    assert missing is None
