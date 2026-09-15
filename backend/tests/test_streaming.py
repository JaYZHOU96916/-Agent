import io
import json
from unittest.mock import Mock

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.agent import AgentEvent
from app.schemas.sandbox import SandboxResult, SandboxStatus
from app.services.agent import AnalysisAgent, OUTPUT_MARKER
from app.services.llm import ModelUnavailable
from app.services.store import AnalysisStore, Equivalent
from test_agent import FakeModel, output


class ReadyModel(FakeModel):
    configured = True


def parse_sse(text):
    events = []
    for block in text.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append({"event": fields["event"], "data": json.loads(fields["data"])})
    return events


@pytest.fixture
def streaming_app(tmp_path):
    settings = Settings(dataset_dir=tmp_path)
    app = create_app(settings)
    model = ReadyModel()
    sandbox = Mock()
    sandbox.execute.return_value = SandboxResult(status=SandboxStatus.COMPLETED, stdout=OUTPUT_MARKER + output().model_dump_json(), duration_ms=1)
    app.state.model = model
    app.state.agent = AnalysisAgent(model, sandbox)
    app.state.store = AnalysisStore(settings, model, fakeredis.aioredis.FakeRedis(decode_responses=True))
    profile = app.state.datasets.create(io.BytesIO(b"sales\n12\n"), "sales.csv")
    with TestClient(app) as client:
        yield app, client, str(profile.dataset_id), sandbox


def test_sse_order_sessions_and_exact_cache(streaming_app):
    app, client, dataset_id, sandbox = streaming_app
    response = client.post("/api/v1/analyses", json={"dataset_id": dataset_id, "question": "Sum sales"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    names = [e["event"] for e in events]
    assert names.index("plan") < names.index("code") < names.index("chart") < names.index("insight") < names.index("done")
    session = client.get("/api/v1/sessions/" + response.headers["x-session-id"]).json()
    assert session["status"] == "completed"
    cached = client.post("/api/v1/analyses", json={"dataset_id": dataset_id, "question": " sum   SALES "})
    assert any(e["data"].get("cache") == "exact" for e in parse_sse(cached.text))
    assert sandbox.execute.call_count == 1


def test_repair_does_not_close_sse_and_failures_not_cached(streaming_app):
    app, client, dataset_id, sandbox = streaming_app
    sandbox.execute.side_effect = [SandboxResult(status=SandboxStatus.FAILED, stderr="KeyError: sale", duration_ms=1),
                                   sandbox.execute.return_value]
    response = client.post("/api/v1/analyses", json={"dataset_id": dataset_id, "question": "total"})
    events = parse_sse(response.text)
    assert any(e["event"] == "error" and e["data"]["recoverable"] for e in events)
    assert events[-1]["data"]["status"] == "completed"
    assert response.text.count("event: code") == 2


def test_exception_becomes_terminal_error_event(streaming_app):
    app, client, dataset_id, _ = streaming_app
    class BrokenAgent:
        async def run(self, *args):
            yield AgentEvent(event="plan", data={"steps": ["start"]})
            raise ModelUnavailable("provider offline")
    app.state.agent = BrokenAgent()
    response = client.post("/api/v1/analyses", json={"dataset_id": dataset_id, "question": "total"})
    events = parse_sse(response.text)
    assert events[-2]["event"] == "error"
    assert events[-1]["data"]["status"] == "failed"
    assert app.state.analysis_slots._value == 2


def test_auth_and_missing_configuration(tmp_path):
    app = create_app(Settings(dataset_dir=tmp_path, api_token="test-token", llm_api_key="", llm_model=""))
    with TestClient(app) as client:
        assert client.get("/api/v1/system").status_code == 401
        assert client.get("/healthz").status_code == 200
        headers = {"X-API-Key": "test-token"}
        profile = client.post("/api/v1/datasets", headers=headers, files={"file": ("x.csv", b"x\n1\n")}).json()
        response = client.post("/api/v1/analyses", headers=headers, json={"dataset_id": profile["dataset_id"], "question": "sum"})
        assert response.status_code == 503


@pytest.mark.asyncio
async def test_semantic_cache_requires_verification_and_dataset_scope():
    settings = Settings(semantic_cache_enabled=True, embedding_model="test")
    class Model:
        configured = True
        async def complete(self, messages, contract):
            return Equivalent(equivalent=True)
    store = AnalysisStore(settings, Model(), fakeredis.aioredis.FakeRedis(decode_responses=True))
    async def embedding(text):
        return [1.0, 0.0]
    store.embedding = embedding
    await store.save("data1", "total revenue", [{"event": "done", "data": {"status": "completed"}}], [1.0, 0.0])
    cached, kind, _ = await store.find("data1", "sum revenue")
    assert cached and kind == "semantic"
    assert (await store.find("data2", "sum revenue"))[0] is None
    assert (await store.find("data1", "sum revenue in 2025"))[0] is None
    await store.redis.aclose()


@pytest.mark.asyncio
async def test_live_execution_logs_are_emitted_before_completion():
    import threading
    from pathlib import Path
    from test_agent import profile
    allow_finish = threading.Event()
    class Sandbox:
        def execute(self, code, on_output, **kwargs):
            on_output("stdout", "live progress\n")
            assert allow_finish.wait(3)
            return SandboxResult(status=SandboxStatus.COMPLETED, stdout=OUTPUT_MARKER + output().model_dump_json(), duration_ms=1)
    agent = AnalysisAgent(ReadyModel(), Sandbox())
    async for event in agent.run(profile(), "sum", Path("x")):
        if event.event == "stdout":
            assert event.data["text"] == "live progress\n"
            allow_finish.set()
    assert allow_finish.is_set()
