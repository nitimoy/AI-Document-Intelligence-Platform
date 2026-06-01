"""Unit tests for AI summarization service workflows."""

import asyncio
from pathlib import Path

from app.config import Settings
from app.models.parsed_document import ParsedDocument
from app.models.summary import SummaryResult
from app.services.cache_service import CacheService
from app.services.summarization_service import SummarizationService
from app.utils.hashing import generate_document_hash

MAP_PROMPT_TEST = "You are an expert document analyst."
REDUCE_PROMPT_TEST = "You are an expert executive assistant."


class FakeOpenAIClient:
    """Simple async fake OpenAI client for deterministic summary tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def summarize(self, prompt: str, content: str) -> str:
        self.calls.append((prompt, content))
        if prompt.strip() == REDUCE_PROMPT_TEST.strip():
            return "final executive summary"
        return f"partial summary {len(self.calls)}"


class FakePromptService:
    """Fake prompt service returning deterministic prompt templates."""

    def get_map_summary_prompt(self) -> str:
        return MAP_PROMPT_TEST

    def get_reduce_summary_prompt(self) -> str:
        return REDUCE_PROMPT_TEST


def build_settings(
    tmp_path: Path, chunk_size: int = 120, overlap: int = 20
) -> Settings:
    """Create test settings for summarization workflows."""

    return Settings(
        openai_api_key="test-key",
        openai_model="gpt-4o",
        summary_chunk_size=chunk_size,
        summary_chunk_overlap=overlap,
        cache_dir=str(tmp_path / "cache"),
    )


def build_parsed_document(content: str, file_name: str = "doc.txt") -> ParsedDocument:
    """Create a parsed document fixture for summarization tests."""

    return ParsedDocument(
        file_name=file_name,
        file_type="txt",
        file_path=f"/tmp/{file_name}",
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        extraction_success=True,
        error_message=None,
    )


def test_small_document_flow(tmp_path: Path) -> None:
    """Small documents should use the single-call summarization path."""

    settings = build_settings(tmp_path, chunk_size=500, overlap=50)
    cache_service = CacheService(settings.cache_dir)
    fake_client = FakeOpenAIClient()
    prompt_service = FakePromptService()
    service = SummarizationService(settings, cache_service, prompt_service, fake_client)

    parsed = build_parsed_document("This is a short document with useful details.")
    result = asyncio.run(service.summarize_document(parsed))

    assert result.summary_type == "small"
    assert result.chunk_count == 1
    assert result.summary
    assert len(fake_client.calls) == 1


def test_large_document_flow(tmp_path: Path) -> None:
    """Large documents should trigger map-reduce summarization."""

    settings = build_settings(tmp_path, chunk_size=80, overlap=10)
    cache_service = CacheService(settings.cache_dir)
    fake_client = FakeOpenAIClient()
    prompt_service = FakePromptService()
    service = SummarizationService(settings, cache_service, prompt_service, fake_client)

    long_content = " ".join(["important"] * 700)
    parsed = build_parsed_document(long_content, file_name="large.txt")

    result = asyncio.run(service.summarize_document(parsed))

    assert result.summary_type == "map-reduce"
    assert result.chunk_count > 1
    assert result.summary == "final executive summary"


def test_cache_hit(tmp_path: Path) -> None:
    """Cache hit should skip OpenAI calls and return cached summary."""

    settings = build_settings(tmp_path)
    cache_service = CacheService(settings.cache_dir)

    content = "This content has already been summarized previously."
    document_hash = generate_document_hash(content)

    cached_summary = SummaryResult(
        file_name="cached.txt",
        summary="cached summary",
        summary_type="small",
        chunk_count=1,
        processing_time_seconds=0.01,
        model_used="gpt-4o",
        document_hash=document_hash,
        created_at="2026-06-01T00:00:00+00:00",
    )
    cache_service.save_summary(cached_summary)

    fake_client = FakeOpenAIClient()
    prompt_service = FakePromptService()
    service = SummarizationService(settings, cache_service, prompt_service, fake_client)

    parsed = build_parsed_document(content, file_name="cached.txt")
    result = asyncio.run(service.summarize_document(parsed))

    assert result.summary == "cached summary"
    assert len(fake_client.calls) == 0


def test_cache_miss(tmp_path: Path) -> None:
    """Cache miss should call OpenAI and persist generated summary."""

    settings = build_settings(tmp_path)
    cache_service = CacheService(settings.cache_dir)
    fake_client = FakeOpenAIClient()
    prompt_service = FakePromptService()
    service = SummarizationService(settings, cache_service, prompt_service, fake_client)

    parsed = build_parsed_document(
        "Fresh content needing AI summary now.", file_name="new.txt"
    )
    result = asyncio.run(service.summarize_document(parsed))

    assert result.summary
    assert len(fake_client.calls) >= 1
    assert cache_service.summary_exists(result.document_hash)


def test_hashing() -> None:
    """Document hashing should be deterministic and content-sensitive."""

    value_a1 = generate_document_hash("same content")
    value_a2 = generate_document_hash("same content")
    value_b = generate_document_hash("different content")

    assert value_a1 == value_a2
    assert value_a1 != value_b


def test_map_reduce_workflow(tmp_path: Path) -> None:
    """Map-reduce should call OpenAI once per chunk plus one reduce call."""

    settings = build_settings(tmp_path, chunk_size=60, overlap=10)
    cache_service = CacheService(settings.cache_dir)
    fake_client = FakeOpenAIClient()
    prompt_service = FakePromptService()
    service = SummarizationService(settings, cache_service, prompt_service, fake_client)

    content = " ".join(["analysis"] * 600)
    final_summary, chunk_count = asyncio.run(service.summarize_large_document(content))

    assert chunk_count > 1
    assert final_summary == "final executive summary"
    assert len(fake_client.calls) == chunk_count + 1
