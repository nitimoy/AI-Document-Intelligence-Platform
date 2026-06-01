"""Hashing utilities for document deduplication and cache keys."""

import hashlib


def generate_document_hash(content: str) -> str:
    """Generate a SHA256 hash for document content."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()
