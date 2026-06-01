"""Token-aware chunking utilities for long document summarization."""

from __future__ import annotations

import tiktoken


def chunk_document(
    content: str, chunk_size: int, overlap: int, encoding_name: str = "cl100k_base"
) -> list[str]:
    """Split content into overlapping token-aware chunks."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(content)

    if not tokens:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap

    for start in range(0, len(tokens), step):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        if not chunk_tokens:
            break
        chunks.append(encoding.decode(chunk_tokens))
        if end >= len(tokens):
            break

    return chunks
