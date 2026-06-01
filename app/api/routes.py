"""API route definitions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import (
    get_app_settings,
    get_cache_service,
    get_dashboard_service,
    get_drive_service,
    get_parser_service,
    get_report_service,
    get_summarization_service,
)
from app.config import Settings
from app.models.report import ReportMetadata
from app.services.cache_service import CacheService
from app.services.dashboard_service import DashboardService
from app.services.drive_service import DriveService
from app.services.parser_service import LEGACY_DOC_SUPPORTED, ParserService
from app.services.report_service import ReportService
from app.services.summarization_service import SummarizationService
from app.utils.exceptions import (
    ConfigurationError,
    DocumentParsingError,
    GoogleDriveError,
    FileDownloadError,
    SummarizationError,
)
from app.utils.logger import get_logger

APPLICATION_NAME = "AI Document Intelligence Platform"
APPLICATION_VERSION = "1.0.0"

router = APIRouter()
dashboard_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = get_logger(__name__)


def _filter_selected_files(
    files: list,
    selected_file_names: list[str] | None,
) -> list:
    """Filter Drive files by selected file names when provided."""

    if not selected_file_names:
        return files

    selected = {name.strip() for name in selected_file_names if name.strip()}
    if not selected:
        return files

    return [
        file_metadata for file_metadata in files if file_metadata.file_name in selected
    ]


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    """Render the landing page for the application."""

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request, "application_name": APPLICATION_NAME},
    )


@router.get("/health")
def health() -> dict[str, str]:
    """Return service health details for operational monitoring."""

    return {
        "status": "healthy",
        "service": APPLICATION_NAME,
        "version": APPLICATION_VERSION,
    }


@router.get("/info")
def info(settings: Annotated[Settings, Depends(get_app_settings)]) -> dict[str, str]:
    """Return basic application metadata."""

    return {
        "application": APPLICATION_NAME,
        "environment": settings.environment,
        "version": APPLICATION_VERSION,
    }


@router.get("/files")
def list_drive_files(
    drive_service: Annotated[DriveService, Depends(get_drive_service)],
) -> dict[str, object]:
    """List supported files from the configured Google Drive folder."""

    try:
        files = drive_service.list_files()
        return {"count": len(files), "files": [file.model_dump() for file in files]}
    except ConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except GoogleDriveError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/files/download")
def download_drive_files(
    drive_service: Annotated[DriveService, Depends(get_drive_service)],
) -> dict[str, int]:
    """Download all supported files into the configured local download directory."""

    try:
        return drive_service.download_all_supported_files()
    except ConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except GoogleDriveError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/parse")
def parse_documents(
    drive_service: Annotated[DriveService, Depends(get_drive_service)],
    parser_service: Annotated[ParserService, Depends(get_parser_service)],
) -> dict[str, object]:
    """Download supported Drive files, parse them, and return extraction results."""

    try:
        files = drive_service.list_files()
        downloaded_paths: list[str] = []
        download_failed = 0

        for file_metadata in files:
            try:
                downloaded = drive_service.download_file(file_metadata)
            except FileDownloadError as exc:
                logger.warning(
                    "Skipping file %s after download failure: %s",
                    file_metadata.file_name,
                    exc,
                )
                download_failed += 1
                continue

            if downloaded.download_path:
                downloaded_paths.append(downloaded.download_path)

        parsed_documents = parser_service.parse_multiple_files(downloaded_paths)
        parsed_count = sum(
            1 for document in parsed_documents if document.extraction_success
        )
        failed_count = (len(parsed_documents) - parsed_count) + download_failed

        return {
            "parsed": parsed_count,
            "failed": failed_count,
            "documents": [document.model_dump() for document in parsed_documents],
        }
    except ConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (GoogleDriveError, DocumentParsingError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/parse/status")
def parser_status() -> dict[str, object]:
    """Return parser health and supported format metadata."""

    supported_file_types = ["pdf", "docx", "txt"]
    if LEGACY_DOC_SUPPORTED:
        supported_file_types.insert(1, "doc")

    return {
        "status": "healthy",
        "component": "document-parser",
        "supported_file_types": supported_file_types,
    }


@router.post("/summarize")
async def summarize_documents(
    drive_service: Annotated[DriveService, Depends(get_drive_service)],
    parser_service: Annotated[ParserService, Depends(get_parser_service)],
    summarization_service: Annotated[
        SummarizationService, Depends(get_summarization_service)
    ],
    force_refresh: bool = False,
    file_name: Annotated[list[str] | None, Query()] = None,
) -> dict[str, int | list[str]]:
    """Download, parse, and summarize documents using AI summarization service."""

    try:
        all_files = drive_service.list_files()
        files = _filter_selected_files(all_files, file_name)
        selected_display = [item.file_name for item in files]

        if not files:
            return {
                "summarized": 0,
                "failed": 0,
                "selected_files": [],
            }

        downloaded_paths: list[str] = []
        download_failed = 0

        for file_metadata in files:
            try:
                downloaded = drive_service.download_file(file_metadata)
            except FileDownloadError as exc:
                logger.warning(
                    "Skipping file %s after download failure: %s",
                    file_metadata.file_name,
                    exc,
                )
                download_failed += 1
                continue

            if downloaded.download_path:
                downloaded_paths.append(downloaded.download_path)

        parsed_documents = parser_service.parse_multiple_files(downloaded_paths)

        summarized = 0
        failed = download_failed

        for parsed_document in parsed_documents:
            if not parsed_document.extraction_success:
                failed += 1
                continue
            try:
                await summarization_service.summarize_document(
                    parsed_document,
                    force_refresh=force_refresh,
                )
                summarized += 1
            except SummarizationError:
                failed += 1

        return {
            "summarized": summarized,
            "failed": failed,
            "selected_files": selected_display,
        }
    except ConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (GoogleDriveError, DocumentParsingError, SummarizationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/summaries")
def list_summaries(
    summarization_service: Annotated[
        SummarizationService, Depends(get_summarization_service)
    ],
) -> dict[str, object]:
    """Return all generated summaries from cache storage."""

    try:
        summaries = summarization_service.list_cached_summaries()
        return {
            "count": len(summaries),
            "summaries": [summary.model_dump() for summary in summaries],
        }
    except SummarizationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/summaries/cache")
def clear_summaries_cache(
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> dict[str, int]:
    """Remove cached summaries and generated reports for a clean restart."""

    try:
        removed_summaries = cache_service.clear_all_summaries()
        report_cleanup = report_service.clear_all_reports()
        return {
            "removed_summaries": removed_summaries,
            "removed_report_exports": report_cleanup["removed_exports"],
            "removed_report_metadata": report_cleanup["removed_metadata"],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to clear cache: {exc}"
        ) from exc


@router.get("/reports/csv")
def generate_csv_report(
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> FileResponse:
    """Generate a CSV report and return it as downloadable response."""

    metadata = report_service.generate_csv_report()
    logger.info("Download request for report: %s", metadata.report_id)
    return FileResponse(
        path=metadata.file_path,
        media_type="text/csv",
        filename=metadata.file_path.split("/")[-1],
    )


@router.get("/reports/pdf")
def generate_pdf_report(
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> FileResponse:
    """Generate a PDF report and return it as downloadable response."""

    metadata = report_service.generate_pdf_report()
    logger.info("Download request for report: %s", metadata.report_id)
    return FileResponse(
        path=metadata.file_path,
        media_type="application/pdf",
        filename=metadata.file_path.split("/")[-1],
    )


@router.get("/reports")
def list_reports(
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> dict[str, object]:
    """List generated report metadata records."""

    reports = report_service.list_reports()
    return {
        "count": len(reports),
        "reports": [report.model_dump() for report in reports],
    }


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> FileResponse:
    """Download a previously generated report by report identifier."""

    metadata: ReportMetadata | None = report_service.get_report(report_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Report not found")

    logger.info("Download request for report: %s", report_id)
    media_type = "application/pdf" if metadata.format.lower() == "pdf" else "text/csv"
    return FileResponse(
        path=metadata.file_path,
        media_type=media_type,
        filename=metadata.file_path.split("/")[-1],
    )


@dashboard_router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
    report_service: Annotated[ReportService, Depends(get_report_service)],
    q: str | None = None,
    file_type: str = "ALL",
) -> HTMLResponse:
    """Render dashboard with metrics, search, filter, and summary table."""

    try:
        summaries = dashboard_service.load_summaries()
        rows = dashboard_service.enrich_summaries(summaries)
        rows = dashboard_service.search_summaries(rows, q)
        rows = dashboard_service.filter_summaries(rows, file_type)
        metrics = dashboard_service.calculate_metrics(rows)
        reports = report_service.list_reports()

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "request": request,
                "application_name": APPLICATION_NAME,
                "rows": rows,
                "metrics": metrics,
                "reports": [report.model_dump() for report in reports],
                "query": q or "",
                "file_type": file_type.upper(),
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to load dashboard: {exc}"
        ) from exc
