"""Prompt loading service for AI summarization templates."""

from __future__ import annotations

from pathlib import Path

from app.utils.exceptions import SummarizationError


class PromptService:
    """Loads and serves prompt templates from the filesystem."""

    def __init__(self, prompts_dir: str = "prompts") -> None:
        self._prompts_dir = Path(prompts_dir)

    def _load_prompt(self, file_name: str) -> str:
        """Load a prompt template file and return normalized text."""

        path = self._prompts_dir / file_name
        try:
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                raise SummarizationError(f"Prompt file is empty: {path}")
            return content
        except SummarizationError:
            raise
        except Exception as exc:
            raise SummarizationError(f"Failed to load prompt file: {path}") from exc

    def get_map_summary_prompt(self) -> str:
        """Return the map-stage summarization prompt template."""

        return self._load_prompt("map_summary.txt")

    def get_reduce_summary_prompt(self) -> str:
        """Return the reduce-stage summarization prompt template."""

        return self._load_prompt("reduce_summary.txt")
