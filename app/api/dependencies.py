"""Shared API dependencies."""

import logging
from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.cache_service import CacheService
from app.services.dashboard_service import DashboardService
from app.services.drive_service import DriveService
from app.services.parser_service import ParserService
from app.services.prompt_service import PromptService
from app.services.report_service import ReportService
from app.services.summarization_service import SummarizationService
from app.utils.logger import get_logger


def get_app_settings() -> Settings:
    """Provide cached application settings to route handlers."""

    return get_settings()


def get_request_logger() -> logging.Logger:
    """Provide a shared API logger dependency."""

    return get_logger("app.api")


def get_drive_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> DriveService:
    """Provide a DriveService instance configured from environment settings."""

    return DriveService(settings=settings)


def get_parser_service() -> ParserService:
    """Provide a ParserService instance for document extraction workflows."""

    return ParserService()


def get_cache_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> CacheService:
    """Provide a cache service configured for summary persistence."""

    return CacheService(cache_dir=settings.cache_dir)


def get_prompt_service() -> PromptService:
    """Provide prompt loader service for summarization templates."""

    return PromptService(prompts_dir="prompts")


def get_dashboard_service(
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
) -> DashboardService:
    """Provide dashboard service for UI metrics and summary exploration."""

    return DashboardService(cache_service=cache_service)


def get_report_service(
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
) -> ReportService:
    """Provide report service for export generation and history management."""

    return ReportService(cache_service=cache_service)


def get_summarization_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
    prompt_service: Annotated[PromptService, Depends(get_prompt_service)],
) -> SummarizationService:
    """Provide a summarization service with configured OpenAI and cache dependencies."""

    return SummarizationService(
        settings=settings,
        cache_service=cache_service,
        prompt_service=prompt_service,
    )
