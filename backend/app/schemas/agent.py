import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AnalysisRequest(Contract):
    dataset_id: UUID
    question: str = Field(min_length=1, max_length=4000)
    session_id: UUID | None = None
    use_cache: bool = True

    @field_validator("question")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()


class Plan(Contract):
    steps: list[str] = Field(min_length=1, max_length=8)


class CodeDraft(Contract):
    code: str = Field(min_length=1, max_length=60000)


class ChartSpec(Contract):
    option: dict

    @field_validator("option")
    @classmethod
    def validate_option(cls, option):
        encoded = json.dumps(option, allow_nan=False)
        if len(encoded.encode()) > 200_000:
            raise ValueError("Chart exceeds 200 KB")
        series = option.get("series")
        if not isinstance(series, list) or not 1 <= len(series) <= 12:
            raise ValueError("Chart must have 1–12 series")
        for item in series:
            if not isinstance(item, dict) or item.get("type") not in {"line", "bar", "pie", "scatter"}:
                raise ValueError("Supported series: line, bar, pie, scatter")
            if not isinstance(item.get("data"), list) or len(item["data"]) > 5000:
                raise ValueError("Each series needs at most 5000 data points")
        # No callbacks, raw HTML, external images, links, or prototype properties.
        blocked = {"formatter", "renderItem", "graphic", "image", "link", "sublink", "__proto__", "constructor", "prototype"}
        def check(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in blocked:
                        raise ValueError(f"Unsupported chart property: {key}")
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)
            elif isinstance(value, str) and ("image://" in value or "javascript:" in value.lower()):
                raise ValueError("External assets/scripts are not supported")
        check(option)
        # ECharts rich text tooltips render on canvas; uploaded strings never become HTML.
        option["tooltip"] = {"trigger": "item" if series[0]["type"] == "pie" else "axis", "renderMode": "richText"}
        if series[0]["type"] != "pie":
            option["dataZoom"] = [{"type": "inside"}, {"type": "slider"}]
        return option


class ExecutionOutput(Contract):
    chart: ChartSpec
    facts: list[str] = Field(min_length=1, max_length=20)


class Insight(Contract):
    text: str = Field(min_length=1, max_length=12000)


class AgentEvent(Contract):
    event: Literal["plan", "code", "stdout", "chart", "insight", "error", "status", "done"]
    data: dict
