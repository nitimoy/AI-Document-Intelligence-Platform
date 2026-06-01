# API Reference

Base API prefix: `/api/v1`

## Health

### GET /api/v1/health
Purpose: Service health signal for monitoring.

Sample response:
```json
{
  "status": "healthy",
  "service": "AI Document Intelligence Platform",
  "version": "1.0.0"
}
```

### GET /api/v1/info
Purpose: Runtime application metadata.

Sample response:
```json
{
  "application": "AI Document Intelligence Platform",
  "environment": "development",
  "version": "1.0.0"
}
```

## Files

### GET /api/v1/files
Purpose: List supported files from configured Google Drive folder.

Sample response:
```json
{
  "count": 3,
  "files": [
    {
      "file_id": "abc123",
      "file_name": "demo1.pdf",
      "mime_type": "application/pdf",
      "size": 12456,
      "created_time": "2026-06-01T12:00:00Z",
      "modified_time": "2026-06-01T12:05:00Z",
      "download_path": null
    }
  ]
}
```

### POST /api/v1/files/download
Purpose: Download all supported files to local download directory.

Sample response:
```json
{
  "downloaded": 3,
  "failed": 0
}
```

## Parsing

### POST /api/v1/parse
Purpose: Download + parse supported files and return extraction results.

Sample response:
```json
{
  "parsed": 3,
  "failed": 0,
  "documents": [
    {
      "file_name": "demo1.pdf",
      "file_type": "pdf",
      "file_path": "downloads/demo1.pdf",
      "content": "...",
      "word_count": 420,
      "character_count": 3120,
      "extraction_success": true,
      "error_message": null
    }
  ]
}
```

### GET /api/v1/parse/status
Purpose: Parser health and supported file type metadata.

Sample response:
```json
{
  "status": "healthy",
  "component": "document-parser",
  "supported_file_types": ["pdf", "doc", "docx", "txt"]
}
```

## Summarization

### POST /api/v1/summarize
Purpose: Download + parse + summarize documents.

Query parameters:
- `force_refresh` (optional, bool): bypass cache and regenerate summaries.
- `file_name` (optional, repeatable): summarize only selected files.

Examples:
- `/api/v1/summarize`
- `/api/v1/summarize?force_refresh=true`
- `/api/v1/summarize?force_refresh=true&file_name=demo1.pdf&file_name=demo2.txt`

Sample response:
```json
{
  "summarized": 2,
  "failed": 0,
  "selected_files": ["demo1.pdf", "demo2.txt"]
}
```

### GET /api/v1/summaries
Purpose: List cached summaries.

Sample response:
```json
{
  "count": 2,
  "summaries": [
    {
      "file_name": "demo1.pdf",
      "summary": "...",
      "summary_type": "small",
      "chunk_count": 1,
      "processing_time_seconds": 2.31,
      "model_used": "gpt-4o",
      "document_hash": "<sha256>",
      "created_at": "2026-06-01T17:24:44.915214+00:00"
    }
  ]
}
```

### DELETE /api/v1/summaries/cache
Purpose: Clear previous generated artifacts for a clean restart.

This removes:
- Summary cache files
- Report export files
- Report metadata history

Sample response:
```json
{
  "removed_summaries": 6,
  "removed_report_exports": 4,
  "removed_report_metadata": 4
}
```

## Reports

### GET /api/v1/reports/csv
Purpose: Generate CSV report and return downloadable file.

Response: File download (`text/csv`).

### GET /api/v1/reports/pdf
Purpose: Generate PDF report and return downloadable file.

Response: File download (`application/pdf`).

### GET /api/v1/reports
Purpose: List report metadata history.

Sample response:
```json
{
  "count": 2,
  "reports": [
    {
      "report_id": "8e86f1be-5db0-4ebf-9696-fb3fda4fd7c8",
      "format": "pdf",
      "created_at": "2026-06-01T18:10:20.004112+00:00",
      "document_count": 3,
      "file_path": "reports/exports/summaries_20260601_181020.pdf"
    }
  ]
}
```

### GET /api/v1/reports/{report_id}/download
Purpose: Download an existing report by report ID.

Response: File download (CSV or PDF depending on report format).

## Dashboard

### GET /dashboard
Purpose: Main single-page dashboard UI.

Rendered capabilities:
- Pipeline action center
- Status panel with next-step guidance
- Search/filter summary table
- Modal-based detail view
- Integrated report generation and report history table

### Notes
- Legacy standalone pages for report center and summary detail were deprecated in favor of in-dashboard workflows.
- Dashboard actions use API endpoints above for execution and data updates.

## Error Model
Most failure responses return:
```json
{
  "detail": "Human-readable error message"
}
```

Common status codes:
- `200`: Success
- `404`: Resource not found (for report download)
- `500`: Configuration/system errors
- `502`: Upstream integration or processing failures
