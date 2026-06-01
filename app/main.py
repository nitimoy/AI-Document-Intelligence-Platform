"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import dashboard_router, router
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Emit startup and shutdown logs for service lifecycle events."""

    logger.info("Starting AI Document Intelligence Platform")
    try:
        yield
    finally:
        logger.info("Shutting down AI Document Intelligence Platform")


app = FastAPI(
    title="AI Document Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=Path("app/static")), name="static")

app.include_router(router, prefix="/api/v1")
app.include_router(dashboard_router)


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")
