from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.datasets import router
from app.core.config import Settings, get_settings
from app.core.upload_limit import UploadLimitMiddleware
from app.services.datasets import DatasetError, DatasetService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Automated Data Analysis Agent", version="0.2.0")
    app.state.datasets = DatasetService(settings)
    app.add_middleware(UploadLimitMiddleware, max_bytes=settings.upload_max_bytes + 64 * 1024)
    app.include_router(router)

    @app.exception_handler(DatasetError)
    async def dataset_error(request: Request, error: DatasetError):
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)

    @app.get("/healthz", tags=["infrastructure"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
