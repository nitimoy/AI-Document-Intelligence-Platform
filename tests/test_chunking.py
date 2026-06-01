"""Unit tests for token-aware document chunking."""

import tiktoken

from app.utils.chunking import chunk_document


def test_chunk_creation() -> None:
    """Chunking should create multiple chunks for long content."""

    content = " ".join(f"token{i}" for i in range(300))
    chunks = chunk_document(content, chunk_size=80, overlap=10)

    assert len(chunks) > 1


def test_overlap_behavior() -> None:
    """Consecutive chunks should overlap by the configured token count."""

    content = " ".join(f"word{i}" for i in range(200))
    chunk_size = 60
    overlap = 15

    chunks = chunk_document(content, chunk_size=chunk_size, overlap=overlap)
    encoding = tiktoken.get_encoding("cl100k_base")

    first_tokens = encoding.encode(chunks[0])
    second_tokens = encoding.encode(chunks[1])

    assert first_tokens[-overlap:] == second_tokens[:overlap]


def test_chunk_sizing() -> None:
    """Each generated chunk should respect the configured maximum token size."""

    content = " ".join(f"unit{i}" for i in range(500))
    chunk_size = 90

    chunks = chunk_document(content, chunk_size=chunk_size, overlap=20)
    encoding = tiktoken.get_encoding("cl100k_base")

    assert all(len(encoding.encode(chunk)) <= chunk_size for chunk in chunks)
