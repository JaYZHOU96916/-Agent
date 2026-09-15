"""OpenAI-compatible JSON completions. No credentials are sent to the browser."""
import json

import httpx

from app.core.config import Settings


class ModelUnavailable(RuntimeError):
    pass


class ModelClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self):
        return bool(self.settings.llm_api_key.get_secret_value() and self.settings.llm_model)

    async def complete(self, messages: list[dict], contract):
        if not self.configured:
            raise ModelUnavailable("请在服务端配置 LLM_API_KEY 和 LLM_MODEL。")
        schema = json.dumps(contract.model_json_schema(), ensure_ascii=False)
        messages = [*messages, {"role": "system", "content": "Return only a JSON object matching this schema: " + schema}]
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(
                    self.settings.llm_base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": "Bearer " + self.settings.llm_api_key.get_secret_value()},
                    json={"model": self.settings.llm_model, "messages": messages,
                          "response_format": {"type": "json_object"}},
                )
                response.raise_for_status()
                payload = response.json()
                message = payload["choices"][0]["message"]
                if message.get("refusal"):
                    raise ModelUnavailable("模型拒绝了该请求，请调整分析问题。")
                content = message["content"]
                if not isinstance(content, str) or len(content) > 100_000:
                    raise ValueError("Invalid or oversized model response")
                return contract.model_validate_json(content)
        except httpx.HTTPStatusError as error:
            raise ModelUnavailable(f"模型服务返回 HTTP {error.response.status_code}；请检查模型、密钥及配额。") from error
        except httpx.HTTPError as error:
            raise ModelUnavailable("模型服务连接失败或超时。") from error
        except (KeyError, IndexError, TypeError) as error:
            raise ModelUnavailable("模型服务响应格式不兼容。") from error
