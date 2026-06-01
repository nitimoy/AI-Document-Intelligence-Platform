"""Service for CSV/PDF report generation and report metadata management."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from textwrap import wrap
from uuid import uuid4

import pandas as pd
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.models.report import ReportMetadata
from app.models.summary import SummaryResult
from app.services.cache_service import CacheService
from app.utils.logger import get_logger


class ReportService:
    """Generate downloadable report files and maintain report history metadata."""

    def __init__(
        self, cache_service: CacheService, reports_root: str = "reports"
    ) -> None:
        self._cache_service = cache_service
        self._reports_root = Path(reports_root)
        self._exports_dir = self._reports_root / "exports"
        self._metadata_dir = self._reports_root / "metadata"
        self._logger = get_logger(__name__)

        self._exports_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _timestamp() -> str:
        """Return a UTC timestamp for filenames and metadata."""

        return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _infer_file_type(file_name: str) -> str:
        """Infer normalized file type label from file name."""

        return Path(file_name).suffix.lower().lstrip(".").upper() or "UNKNOWN"

    def _build_metadata(
        self, report_format: str, file_path: Path, document_count: int
    ) -> ReportMetadata:
        """Build a metadata object for a generated report."""

        return ReportMetadata(
            report_id=str(uuid4()),
            format=report_format,
            created_at=datetime.now(UTC).isoformat(),
            document_count=document_count,
            file_path=str(file_path),
        )

    def _load_summaries(self) -> list[SummaryResult]:
        """Load summaries used as source records for reports."""

        return self._cache_service.get_all_summaries()

    def save_metadata(self, metadata: ReportMetadata) -> None:
        """Persist report metadata JSON record to history store."""

        metadata_path = self._metadata_dir / f"{metadata.report_id}.json"
        metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
        self._logger.info("Metadata writes: %s", metadata_path.name)

    def generate_csv_report(self) -> ReportMetadata:
        """Generate CSV report from current summaries and return report metadata."""

        self._logger.info("Report generation start: CSV")
        try:
            summaries = self._load_summaries()
            timestamp = self._timestamp()
            csv_path = self._exports_dir / f"summaries_{timestamp}.csv"

            rows = [
                {
                    "File Name": item.file_name,
                    "File Type": self._infer_file_type(item.file_name),
                    "Summary": item.summary,
                    "Chunk Count": item.chunk_count,
                    "Processing Time": item.processing_time_seconds,
                    "Model Used": item.model_used,
                    "Created At": item.created_at,
                }
                for item in summaries
            ]

            dataframe = pd.DataFrame(
                rows,
                columns=[
                    "File Name",
                    "File Type",
                    "Summary",
                    "Chunk Count",
                    "Processing Time",
                    "Model Used",
                    "Created At",
                ],
            )
            dataframe.to_csv(csv_path, index=False)

            metadata = self._build_metadata("csv", csv_path, len(summaries))
            self.save_metadata(metadata)
            self._logger.info("Report generation success: CSV (%s)", csv_path.name)
            return metadata
        except Exception as exc:
            self._logger.error("Report generation failure: CSV - %s", exc)
            raise

    def generate_pdf_report(self) -> ReportMetadata:
        """Generate professionally formatted PDF report and return metadata."""

        self._logger.info("Report generation start: PDF")
        try:
            summaries = self._load_summaries()
            timestamp = self._timestamp()
            pdf_path = self._exports_dir / f"summaries_{timestamp}.pdf"

            pdf = canvas.Canvas(str(pdf_path), pagesize=LETTER)
            page_width, page_height = LETTER
            y = page_height - 50

            def draw_footer(page_number: int) -> None:
                pdf.setFont("Helvetica", 9)
                pdf.drawRightString(page_width - 40, 25, f"Page {page_number}")

            def ensure_space(lines_needed: int, page_number: int) -> int:
                nonlocal y
                if y - (lines_needed * 14) < 50:
                    draw_footer(page_number)
                    pdf.showPage()
                    y = page_height - 50
                    return page_number + 1
                return page_number

            page_number = 1
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(40, y, "AI Document Intelligence Platform")
            y -= 24

            pdf.setFont("Helvetica", 10)
            pdf.drawString(40, y, f"Generation Date: {datetime.now(UTC).isoformat()}")
            y -= 14
            pdf.drawString(40, y, f"Document Count: {len(summaries)}")
            y -= 14
            unique_models = sorted({item.model_used for item in summaries})
            model_text = ", ".join(unique_models) if unique_models else "N/A"
            pdf.drawString(40, y, f"Model Used: {model_text}")
            y -= 22

            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(40, y, "Summary Sections")
            y -= 18

            for idx, item in enumerate(summaries, start=1):
                page_number = ensure_space(6, page_number)
                pdf.setFont("Helvetica-Bold", 11)
                title = (
                    f"{idx}. {item.file_name} ({self._infer_file_type(item.file_name)})"
                )
                pdf.drawString(
                    40,
                    y,
                    title,
                )
                y -= 14

                pdf.setFont("Helvetica", 10)
                meta_line = (
                    f"Chunks: {item.chunk_count} | "
                    f"Processing: {item.processing_time_seconds}s | "
                    f"Created: {item.created_at}"
                )
                pdf.drawString(40, y, meta_line)
                y -= 14

                wrapped_summary = wrap(item.summary, width=98) or [""]
                for line in wrapped_summary:
                    page_number = ensure_space(1, page_number)
                    pdf.drawString(40, y, line)
                    y -= 12

                y -= 8

            draw_footer(page_number)
            pdf.save()

            metadata = self._build_metadata("pdf", pdf_path, len(summaries))
            self.save_metadata(metadata)
            self._logger.info("Report generation success: PDF (%s)", pdf_path.name)
            return metadata
        except Exception as exc:
            self._logger.error("Report generation failure: PDF - %s", exc)
            raise

    def list_reports(self) -> list[ReportMetadata]:
        """Return report history records sorted by newest first."""

        records: list[ReportMetadata] = []
        for path in sorted(self._metadata_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                records.append(ReportMetadata(**payload))
            except Exception as exc:
                self._logger.error(
                    "Failed reading metadata file %s: %s", path.name, exc
                )

        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_report(self, report_id: str) -> ReportMetadata | None:
        """Retrieve a report metadata record by report identifier."""

        metadata_path = self._metadata_dir / f"{report_id}.json"
        if not metadata_path.exists():
            return None

        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        return ReportMetadata(**payload)

    def clear_all_reports(self) -> dict[str, int]:
        """Delete generated report files and metadata history records."""

        removed_exports = 0
        removed_metadata = 0

        for export_file in self._exports_dir.glob("*"):
            if export_file.is_file():
                export_file.unlink(missing_ok=True)
                removed_exports += 1

        for metadata_file in self._metadata_dir.glob("*.json"):
            if metadata_file.is_file():
                metadata_file.unlink(missing_ok=True)
                removed_metadata += 1

        self._logger.info(
            "Cleared report artifacts. exports=%s metadata=%s",
            removed_exports,
            removed_metadata,
        )

        return {
            "removed_exports": removed_exports,
            "removed_metadata": removed_metadata,
        }
