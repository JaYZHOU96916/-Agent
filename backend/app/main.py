import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.datasets import router
from app.core.config import Settings, get_settings
from app.core.upload_limit import UploadLimitMiddleware
from app.services.datasets import DatasetError, DatasetService
from app.api.analysis import router as analysis_router
from app.core.auth import TokenAuthMiddleware
from app.services.agent import AnalysisAgent
from app.services.llm import ModelClient
from app.services.sandbox import DockerSandboxExecutor
from app.services.store import AnalysisStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    @asynccontextmanager
    async def lifespan(app):
        yield
        await app.state.store.redis.aclose()
    app = FastAPI(title="Automated Data Analysis Agent", version="0.4.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.model = ModelClient(settings)
    app.state.store = AnalysisStore(settings, app.state.model)
    app.state.agent = AnalysisAgent(app.state.model, DockerSandboxExecutor(settings), settings.agent_max_repairs)
    app.state.analysis_slots = asyncio.Semaphore(2)
    app.state.datasets = DatasetService(settings)
    app.add_middleware(UploadLimitMiddleware, max_bytes=settings.upload_max_bytes + 64 * 1024)
    app.add_middleware(TokenAuthMiddleware, token=settings.api_token.get_secret_value())
    app.include_router(router)
    app.include_router(analysis_router)

    @app.exception_handler(DatasetError)
    async def dataset_error(request: Request, error: DatasetError):
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)

    @app.get("/healthz", tags=["infrastructure"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
