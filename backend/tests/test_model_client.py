import json

import httpx
import pytest

from app.core.config import Settings
from app.schemas.agent import CodeDraft
from app.services.llm import ModelClient, ModelUnavailable


@pytest.mark.asyncio
async def test_model_client_sends_bounded_json_contract_without_exposing_credentials(monkeypatch):
    captured = []
    def respond(request):
        captured.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"code":"print(1)"}'}}]})
    real_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client)
    client = ModelClient(Settings(llm_api_key="secret-test-only", llm_model="fixture", llm_base_url="https://example.invalid/v1"))
    draft = await client.complete([{"role": "user", "content": "make a chart"}], CodeDraft)
    assert draft.code == "print(1)"
    assert str(captured[0].url) == "https://example.invalid/v1/chat/completions"
    assert captured[0].headers["Authorization"] == "Bearer secret-test-only"
    body = json.loads(captured[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["model"] == "fixture"
    assert "secret-test-only" not in json.dumps(body)
    assert "CodeDraft" in body["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_model_refusal_is_terminal_and_response_is_validated(monkeypatch):
    real_client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"refusal": "no", "content": None}}]})
    ))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client)
    client = ModelClient(Settings(llm_api_key="fixture", llm_model="fixture"))
    with pytest.raises(ModelUnavailable, match="拒绝"):
        await client.complete([], CodeDraft)
