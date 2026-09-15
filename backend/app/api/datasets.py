from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.schemas.dataset import DatasetProfile
from app.services.datasets import DatasetService

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.post("", response_model=DatasetProfile, status_code=201, openapi_extra={
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["file"],
        "properties": {"file": {"type": "string", "format": "binary"}},
    }}}},
})
async def upload_dataset(request: Request) -> DatasetProfile:
    service: DatasetService = request.app.state.datasets
    async with request.form(max_files=1, max_fields=0) as form:
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise HTTPException(422, "A multipart file field named 'file' is required.")
        return await run_in_threadpool(service.create, file.file, file.filename or "")


@router.get("/{dataset_id}", response_model=DatasetProfile)
def get_dataset(dataset_id: UUID, request: Request) -> DatasetProfile:
    return request.app.state.datasets.get(dataset_id)
