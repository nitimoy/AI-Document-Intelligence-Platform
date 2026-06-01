"""Storage abstraction for downloaded files."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class StorageService(ABC):
    """Contract for storage backends used by download workflows."""

    @abstractmethod
    def resolve_path(self, file_name: str) -> Path:
        """Resolve the destination path for a file name."""

    @abstractmethod
    def open_binary_writer(self, file_name: str) -> BinaryIO:
        """Open a writable binary stream for a file name."""


class LocalStorageService(StorageService):
    """Filesystem-backed storage implementation for local development."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)

    def resolve_path(self, file_name: str) -> Path:
        """Return the local destination path and ensure the directory exists."""

        self._base_dir.mkdir(parents=True, exist_ok=True)
        return self._base_dir / file_name

    def open_binary_writer(self, file_name: str) -> BinaryIO:
        """Open or overwrite a local file for binary writes."""

        destination = self.resolve_path(file_name)
        return destination.open("wb")
