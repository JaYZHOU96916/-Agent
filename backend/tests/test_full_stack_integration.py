"""Real Docker + real Redis; deterministic model fixture, never a production mock mode."""
import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.agent import CodeDraft, Insight, Plan
from app.services.agent import AnalysisAgent
from app.services.sandbox import DockerSandboxExecutor
from app.services.store import AnalysisStore
from test_streaming import parse_sse

pytestmark = pytest.mark.skipif(os.getenv("RUN_STACK_TESTS") != "1", reason="requires Docker and Redis")


class FixtureModel:
    configured = True
    code_calls = 0

    async def complete(self, messages, contract):
        if contract is Plan:
            return Plan(steps=["Read data and compute total sales"])
        if contract is Insight:
            return Insight(text="Total sales are 30.")
        self.code_calls += 1
        column = "sale" if self.code_calls == 1 else "sales"
        return CodeDraft(code=(
            "import pandas as pd, json\n"
            "df = pd.read_parquet('/tmp/dataset.parquet')\n"
            "print('Loaded dataset', flush=True)\n"
            f"total = int(df[{column!r}].sum())\n"
            "result = {'chart': {'option': {'series': [{'type': 'bar', 'data': [total]}]}}, 'facts': [f'Total sales are {total}']}\n"
            "print('__ANALYSIS_RESULT__=' + json.dumps(result))\n"
        ))


def test_upload_repair_sse_and_real_redis_cache(tmp_path):
    settings = Settings(dataset_dir=tmp_path, llm_model="fixture-real-docker", redis_url=os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15"))
    app = create_app(settings)
    model = FixtureModel()
    app.state.model = model
    app.state.agent = AnalysisAgent(model, DockerSandboxExecutor(settings))
    app.state.store = AnalysisStore(settings, model)
    with TestClient(app) as client:
        assert client.get("/api/v1/system").json()["redis_available"] is True
        upload = client.post("/api/v1/datasets", files={"file": ("sales.csv", b"sales\n10\n20\n")})
        assert upload.status_code == 201
        question = "total sales " + tmp_path.name
        body = {"dataset_id": upload.json()["dataset_id"], "question": question}
        response = client.post("/api/v1/analyses", json=body)
        events = parse_sse(response.text)
        assert events[-1]["data"]["status"] == "completed", response.text
        assert any(e["event"] == "error" and e["data"]["recoverable"] for e in events)
        assert any(e["event"] == "stdout" and "Loaded" in e["data"]["text"] for e in events)
        chart = next(e for e in events if e["event"] == "chart")
        assert chart["data"]["option"]["series"][0]["data"] == [30]
        assert model.code_calls == 2
        cached = client.post("/api/v1/analyses", json=body)
        assert any(e["data"].get("cache") == "exact" for e in parse_sse(cached.text))
        assert model.code_calls == 2
        session = client.get("/api/v1/sessions/" + response.headers["x-session-id"])
        assert session.json()["status"] == "completed"
