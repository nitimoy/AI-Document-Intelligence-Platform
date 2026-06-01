"""Summary caching service for hash-based document summaries."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.summary import SummaryResult
from app.utils.exceptions import CacheError


class CacheService:
    """Persist and retrieve summary results using JSON files keyed by hash."""

    def __init__(self, cache_dir: str) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, document_hash: str) -> Path:
        """Return the JSON cache file path for a document hash."""

        return self._cache_dir / f"{document_hash}.json"

    def summary_exists(self, document_hash: str) -> bool:
        """Check whether a cached summary exists for a document hash."""

        return self._cache_path(document_hash).exists()

    def get_cached_summary(self, document_hash: str) -> SummaryResult | None:
        """Load a cached summary for a hash, if available."""

        cache_path = self._cache_path(document_hash)
        if not cache_path.exists():
            return None

        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return SummaryResult(**payload)
        except Exception as exc:
            raise CacheError(
                f"Failed to load cached summary for {document_hash}"
            ) from exc

    def save_summary(self, summary: SummaryResult) -> None:
        """Save a summary result to cache using its document hash."""

        cache_path = self._cache_path(summary.document_hash)
        try:
            cache_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        except Exception as exc:
            raise CacheError(
                f"Failed to save summary for {summary.document_hash}"
            ) from exc

    def get_all_summaries(self) -> list[SummaryResult]:
        """Load all cached summary records from the cache directory."""

        summaries: list[SummaryResult] = []
        for file_path in sorted(self._cache_dir.glob("*.json")):
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                summaries.append(SummaryResult(**payload))
            except Exception as exc:
                raise CacheError(
                    f"Failed to read cache file: {file_path.name}"
                ) from exc
        return summaries

    def clear_all_summaries(self) -> int:
        """Delete all summary cache files and return removed file count."""

        removed = 0
        for file_path in self._cache_dir.glob("*.json"):
            try:
                file_path.unlink(missing_ok=True)
                removed += 1
            except Exception as exc:
                raise CacheError(
                    f"Failed to remove cache file: {file_path.name}"
                ) from exc

        return removed
