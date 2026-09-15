import io
import json
import subprocess
from uuid import uuid4

import pandas as pd
import pytest
import xlwt
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.dataset import DatasetProfile
from app.services.prompts import build_dataset_context


@pytest.fixture
def client(tmp_path):
    settings = Settings(dataset_dir=tmp_path / "datasets")
    with TestClient(create_app(settings)) as client:
        yield client


def sample_bytes(extension):
    frame = pd.DataFrame({"地区": ["上海", "北京", "广州", "杭州", "苏州", "成都"],
                          "sales": [10, 20, None, 40, 50, 60]})
    output = io.BytesIO()
    if extension == "csv":
        return frame.to_csv(index=False).encode("utf-8-sig")
    if extension == "xlsx":
        frame.to_excel(output, index=False)
    elif extension == "xls":
        book = xlwt.Workbook()
        sheet = book.add_sheet("Sales")
        for j, name in enumerate(frame.columns):
            sheet.write(0, j, name)
        for i, row in enumerate(frame.itertuples(index=False), start=1):
            for j, value in enumerate(row):
                if not pd.isna(value):
                    sheet.write(i, j, value)
        book.save(output)
    else:
        frame.to_parquet(output, index=False)
    return output.getvalue()


@pytest.mark.parametrize("extension", ["csv", "xlsx", "xls", "parquet"])
def test_real_upload_profile_persistence_and_prompt(client, extension):
    response = client.post("/api/v1/datasets", files={"file": (f"sales.{extension}", sample_bytes(extension))})
    assert response.status_code == 201, response.text
    profile = DatasetProfile.model_validate(response.json())
    assert profile.row_count == 6
    assert profile.column_count == 2
    assert [c.name for c in profile.columns] == ["地区", "sales"]
    assert profile.columns[1].missing_count == 1
    assert profile.columns[1].missing_fraction == pytest.approx(1 / 6)
    assert len(profile.sample_rows) == 5
    assert profile.sample_rows[2]["sales"] is None
    assert client.get(f"/api/v1/datasets/{profile.dataset_id}").json() == response.json()
    folder = client.app.state.datasets.root / str(profile.dataset_id)
    restored = pd.read_parquet(folder / "dataset.parquet")
    assert len(restored) == 6
    assert not list(folder.glob("source*"))
    context = build_dataset_context(profile)
    assert "sales" in context and "untrusted data" in context
    assert "成都" not in context  # Sixth row must never enter the prompt preview.


@pytest.mark.parametrize(("name", "data", "status"), [
    ("code.py", b"print('hi')", 415),
    ("empty.csv", b"", 422),
    ("wrong.xlsx", b"not a workbook", 422),
    ("wrong.parquet", b"not parquet", 422),
    ("duplicate.csv", b"x,x\n1,2\n", 422),
    ("missing.csv", b"x,\n1,2\n", 422),
    ("ragged.csv", b"x,y\n1,2,3\n", 422),
    ("bad-encoding.csv", b"x\n\xff\n", 422),
])
def test_invalid_upload_cleans_staging(client, name, data, status):
    response = client.post("/api/v1/datasets", files={"file": (name, data)})
    assert response.status_code == status, response.text
    assert list(client.app.state.datasets.root.glob("*")) == []


def test_filename_cannot_escape_dataset_directory(client):
    response = client.post("/api/v1/datasets", files={"file": ("../../escaped.csv", b"x\n1\n")})
    assert response.status_code == 201
    assert response.json()["filename"] == "escaped.csv"
    assert not (client.app.state.datasets.root.parent / "escaped.csv").exists()


def test_missing_dataset_and_invalid_id(client):
    assert client.get(f"/api/v1/datasets/{uuid4()}").status_code == 404
    assert client.get("/api/v1/datasets/not-a-uuid").status_code == 422


@pytest.mark.parametrize("limit", ["rows", "columns", "bytes"])
def test_dataset_limits(tmp_path, limit):
    options = {"rows": {"dataset_max_rows": 1}, "columns": {"dataset_max_columns": 1},
               "bytes": {"upload_max_bytes": 4}}
    with TestClient(create_app(Settings(dataset_dir=tmp_path, **options[limit]))) as client:
        response = client.post("/api/v1/datasets", files={"file": ("data.csv", b"a,b\n1,2\n3,4\n")})
        assert response.status_code == (413 if limit == "bytes" else 422), response.text
        assert not list(tmp_path.iterdir())


def test_parser_timeout_cleans_upload(client, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr("app.services.datasets.subprocess.run", timeout)
    response = client.post("/api/v1/datasets", files={"file": ("data.csv", b"x\n1\n")})
    assert response.status_code == 422
    assert "time limit" in response.json()["detail"]
    assert not list(client.app.state.datasets.root.iterdir())


def test_busy_workers_return_retryable_status(client):
    service = client.app.state.datasets
    for _ in range(service.settings.profiling_concurrency):
        service._slots.acquire()
    try:
        response = client.post("/api/v1/datasets", files={"file": ("data.csv", b"x\n1\n")})
        assert response.status_code == 503
    finally:
        for _ in range(service.settings.profiling_concurrency):
            service._slots.release()


def test_prompt_budget_has_valid_json_and_explicit_truncation(client):
    response = client.post("/api/v1/datasets", files={"file": ("data.csv", b"x\n1\n")})
    profile = DatasetProfile.model_validate(response.json())
    original = profile.columns[0]
    profile.columns = [original.model_copy(update={"name": f"column_{i}_" + "z" * 100}) for i in range(100)]
    profile.column_count = 100
    context = build_dataset_context(profile, max_chars=1500)
    assert len(context) <= 1500
    data = json.loads(context.split("DATASET_PROFILE_JSON\n", 1)[1])
    assert data["omitted_columns"] > 0
    assert data["omitted_columns"] + len(data["columns"]) == 100
    assert data["sample_rows"] == []


def test_header_only_file_has_zero_missing_fractions(client):
    response = client.post("/api/v1/datasets", files={"file": ("header.csv", b"x,y\n")})
    assert response.status_code == 201, response.text
    assert response.json()["row_count"] == 0
    assert response.json()["sample_rows"] == []
    assert all(c["missing_fraction"] == 0 for c in response.json()["columns"])


def test_request_body_limit_without_content_length(client):
    # A streaming multipart request exercises the actual ASGI byte counter.
    boundary = "upload-boundary"
    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="data.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n').encode()
    from app.core.upload_limit import UploadLimitMiddleware
    middleware = client.app.middleware_stack.app
    while not isinstance(middleware, UploadLimitMiddleware):
        middleware = middleware.app
    middleware.max_bytes = 1024
    response = client.post("/api/v1/datasets", content=iter([data, b"x" * 2048]),
                           headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    assert response.status_code == 413, response.text
