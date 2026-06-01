"""AI summarization service using OpenAI Responses API with map-reduce and caching."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import tiktoken
from openai import AsyncOpenAI

from app.config import Settings
from app.models.parsed_document import ParsedDocument
from app.models.summary import SummaryResult
from app.services.cache_service import CacheService
from app.services.prompt_service import PromptService
from app.utils.chunking import chunk_document
from app.utils.exceptions import OpenAIServiceError, SummarizationError
from app.utils.hashing import generate_document_hash
from app.utils.logger import get_logger


class OpenAIResponsesClient:
    """Thin wrapper around OpenAI Responses API for summarization calls."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def summarize(self, prompt: str, content: str) -> str:
        """Call OpenAI Responses API and return plain output text."""

        try:
            response = await self._client.responses.create(
                model=self._model,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": content}],
                    },
                ],
            )

            output_text = getattr(response, "output_text", "")
            if output_text:
                return output_text.strip()

            # Defensive fallback for SDK versions where output_text may be empty.
            chunks: list[str] = []
            for item in getattr(response, "output", []):
                for piece in getattr(item, "content", []):
                    text = getattr(piece, "text", "")
                    if text:
                        chunks.append(text)

            merged = "\n".join(chunks).strip()
            if not merged:
                raise OpenAIServiceError("OpenAI response did not contain summary text")
            return merged
        except OpenAIServiceError:
            raise
        except Exception as exc:
            raise OpenAIServiceError(
                f"OpenAI summarization request failed: {exc}"
            ) from exc


class SummarizationService:
    """Coordinates small/large document summarization with cache and metrics."""

    def __init__(
        self,
        settings: Settings,
        cache_service: CacheService,
        prompt_service: PromptService,
        openai_client: OpenAIResponsesClient | None = None,
    ) -> None:
        self._settings = settings
        self._cache_service = cache_service
        self._prompt_service = prompt_service
        self._logger = get_logger(__name__)
        self._encoding = tiktoken.get_encoding("cl100k_base")
        self._openai_client = openai_client or OpenAIResponsesClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    async def summarize_document(
        self,
        parsed_document: ParsedDocument,
        force_refresh: bool = False,
    ) -> SummaryResult:
        """Summarize a parsed document using cache-aware small/large workflows."""

        start = time.perf_counter()
        document_hash = generate_document_hash(parsed_document.content)

        cached = self._cache_service.get_cached_summary(document_hash)
        if cached is not None and not force_refresh:
            self._logger.info("Cache hit for document %s", parsed_document.file_name)
            return cached

        if force_refresh and cached is not None:
            self._logger.info(
                "Force refresh enabled; regenerating summary for %s",
                parsed_document.file_name,
            )

        self._logger.info("Cache miss for document %s", parsed_document.file_name)

        token_count = len(self._encoding.encode(parsed_document.content))

        if token_count <= self._settings.summary_chunk_size:
            summary = await self.summarize_small_document(parsed_document.content)
            summary_type = "small"
            chunk_count = 1
        else:
            summary, chunk_count = await self.summarize_large_document(
                parsed_document.content
            )
            summary_type = "map-reduce"

        duration = time.perf_counter() - start
        self._logger.info(
            "Processing duration for %s: %.3f seconds",
            parsed_document.file_name,
            duration,
        )

        result = SummaryResult(
            file_name=parsed_document.file_name,
            summary=summary,
            summary_type=summary_type,
            chunk_count=chunk_count,
            processing_time_seconds=duration,
            model_used=self._settings.openai_model,
            document_hash=document_hash,
            created_at=datetime.now(UTC).isoformat(),
        )

        self._cache_service.save_summary(result)
        return result

    async def summarize_small_document(self, content: str) -> str:
        """Summarize short documents with a single OpenAI request."""

        try:
            map_prompt = self._prompt_service.get_map_summary_prompt()
            return await self._openai_client.summarize(map_prompt, content)
        except OpenAIServiceError as exc:
            self._logger.error(
                "OpenAI error during small document summarization: %s", exc
            )
            raise SummarizationError(str(exc)) from exc

    async def summarize_large_document(self, content: str) -> tuple[str, int]:
        """Summarize long documents via map-reduce chunk workflow."""

        chunks = chunk_document(
            content,
            chunk_size=self._settings.summary_chunk_size,
            overlap=self._settings.summary_chunk_overlap,
        )

        self._logger.info("Chunk count: %s", len(chunks))
        self._logger.info("Map summarization start")
        partial_summaries = await self.map_summarize(chunks)
        self._logger.info("Map summarization complete")

        self._logger.info("Reduce summarization start")
        final_summary = await self.reduce_summaries(partial_summaries)
        self._logger.info("Reduce summarization complete")

        return final_summary, len(chunks)

    async def map_summarize(self, chunks: list[str]) -> list[str]:
        """Summarize all chunks concurrently using asyncio.gather."""

        try:
            map_prompt = self._prompt_service.get_map_summary_prompt()
            tasks = [
                self._openai_client.summarize(map_prompt, chunk) for chunk in chunks
            ]
            return await asyncio.gather(*tasks)
        except OpenAIServiceError as exc:
            self._logger.error("OpenAI error during map summarization: %s", exc)
            raise SummarizationError(str(exc)) from exc
        except Exception as exc:
            self._logger.error("Unexpected error during map summarization: %s", exc)
            raise SummarizationError(f"Map summarization failed: {exc}") from exc

    async def reduce_summaries(self, partial_summaries: list[str]) -> str:
        """Combine partial summaries into a final executive summary."""

        try:
            combined_content = "\n\n".join(partial_summaries)
            reduce_prompt = self._prompt_service.get_reduce_summary_prompt()
            return await self._openai_client.summarize(reduce_prompt, combined_content)
        except OpenAIServiceError as exc:
            self._logger.error("OpenAI error during reduce summarization: %s", exc)
            raise SummarizationError(str(exc)) from exc

    def list_cached_summaries(self) -> list[SummaryResult]:
        """Return all summary results currently stored in cache."""

        return self._cache_service.get_all_summaries()
