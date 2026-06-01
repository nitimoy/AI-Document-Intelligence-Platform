"""Unit tests for report generation and history services."""

from pathlib import Path

from app.config import Settings
from app.models.summary import SummaryResult
from app.services.cache_service import CacheService
from app.services.report_service import ReportService


def _seed_summary(
    cache_service: CacheService, file_name: str, document_hash: str
) -> SummaryResult:
    """Create and persist one summary fixture for report generation tests."""

    summary = SummaryResult(
        file_name=file_name,
        summary="Detailed summary content for reporting validation.",
        summary_type="small",
        chunk_count=1,
        processing_time_seconds=0.52,
        model_used="gpt-4o",
        document_hash=document_hash,
        created_at="2026-06-01T00:00:00+00:00",
    )
    cache_service.save_summary(summary)
    return summary


def _build_service(tmp_path: Path) -> tuple[ReportService, CacheService]:
    """Create report service and backing cache service with temp directories."""

    settings = Settings(cache_dir=str(tmp_path / "cache"))
    cache_service = CacheService(settings.cache_dir)
    report_service = ReportService(
        cache_service=cache_service, reports_root=str(tmp_path / "reports")
    )
    return report_service, cache_service


def test_csv_generation(tmp_path: Path) -> None:
    """CSV report generation should create file and metadata with expected fields."""

    report_service, cache_service = _build_service(tmp_path)
    _seed_summary(cache_service, "one.pdf", "hash-1")

    metadata = report_service.generate_csv_report()

    export_path = Path(metadata.file_path)
    assert metadata.format == "csv"
    assert export_path.exists()
    assert export_path.suffix == ".csv"

    csv_content = export_path.read_text(encoding="utf-8")
    assert "File Name" in csv_content
    assert "Summary" in csv_content


def test_pdf_generation(tmp_path: Path) -> None:
    """PDF report generation should create a non-empty PDF and metadata."""

    report_service, cache_service = _build_service(tmp_path)
    _seed_summary(cache_service, "two.docx", "hash-2")

    metadata = report_service.generate_pdf_report()

    export_path = Path(metadata.file_path)
    assert metadata.format == "pdf"
    assert export_path.exists()
    assert export_path.suffix == ".pdf"
    assert export_path.stat().st_size > 0


def test_metadata_persistence(tmp_path: Path) -> None:
    """Generating reports should persist metadata JSON history files."""

    report_service, cache_service = _build_service(tmp_path)
    _seed_summary(cache_service, "three.txt", "hash-3")

    metadata = report_service.generate_csv_report()

    metadata_path = tmp_path / "reports" / "metadata" / f"{metadata.report_id}.json"
    assert metadata_path.exists()


def test_report_listing(tmp_path: Path) -> None:
    """Listing should return generated report records."""

    report_service, cache_service = _build_service(tmp_path)
    _seed_summary(cache_service, "a.pdf", "hash-a")

    report_service.generate_csv_report()
    report_service.generate_pdf_report()

    reports = report_service.list_reports()

    assert len(reports) == 2
    assert {item.format for item in reports} == {"csv", "pdf"}


def test_report_retrieval(tmp_path: Path) -> None:
    """Report retrieval by ID should return matching metadata."""

    report_service, cache_service = _build_service(tmp_path)
    _seed_summary(cache_service, "b.txt", "hash-b")

    created = report_service.generate_csv_report()
    fetched = report_service.get_report(created.report_id)
    missing = report_service.get_report("does-not-exist")

    assert fetched is not None
    assert fetched.report_id == created.report_id
    assert missing is None
