from pathlib import Path
from unittest.mock import Mock

import pytest

from app.schemas.agent import ChartSpec, CodeDraft, ExecutionOutput, Insight, Plan
from app.schemas.dataset import DatasetProfile
from app.schemas.sandbox import SandboxResult, SandboxStatus
from app.services.agent import AnalysisAgent, OUTPUT_MARKER, parse_output
from app.services.llm import ModelClient, ModelUnavailable
from app.core.config import Settings


def profile():
    return DatasetProfile(dataset_id="11111111-1111-4111-8111-111111111111", filename="sales.csv", format="csv",
                          sha256="a" * 64, size_bytes=10, row_count=1, column_count=1,
                          columns=[{"name": "sales", "dtype": "int64", "missing_count": 0, "missing_fraction": 0}],
                          sample_rows=[{"sales": 12}], created_at="2026-01-01T00:00:00Z")


def output():
    return ExecutionOutput(chart=ChartSpec(option={"series": [{"type": "bar", "data": [12]}]}), facts=["Sales total is 12"])


class FakeModel:
    def __init__(self):
        self.calls = []

    async def complete(self, messages, contract):
        self.calls.append((messages, contract))
        if contract is Plan:
            return Plan(steps=["Compute sales total"])
        if contract is Insight:
            return Insight(text="销售总额为 12，仅覆盖本数据集。")
        return CodeDraft(code="print('sales')" if len(self.calls) == 2 else "print('fixed sales')")


@pytest.mark.asyncio
@pytest.mark.parametrize("error", ["KeyError: 'sale'", "ValueError: cannot convert", "SyntaxError: invalid syntax"])
async def test_repair_feedback_diff_and_success(error):
    model = FakeModel()
    sandbox = Mock()
    sandbox.execute.side_effect = [SandboxResult(status=SandboxStatus.FAILED, stderr=error, duration_ms=1),
                                   SandboxResult(status=SandboxStatus.COMPLETED, stdout=OUTPUT_MARKER + output().model_dump_json(), duration_ms=1)]
    events = [e async for e in AnalysisAgent(model, sandbox).run(profile(), "sum sales", Path("dataset.parquet"))]
    assert events[-1].data == {"status": "completed", "repairs": 1}
    assert any(error in str(m) for m, _ in model.calls)
    codes = [e for e in events if e.event == "code"]
    assert codes[1].data["diff"].startswith("--- previous.py")
    assert any(e.event == "error" and e.data["recoverable"] for e in events)
    assert any(e.event == "chart" for e in events)


@pytest.mark.asyncio
async def test_maximum_three_repairs():
    sandbox = Mock()
    sandbox.execute.return_value = SandboxResult(status=SandboxStatus.FAILED, stderr="KeyError", duration_ms=1)
    events = [e async for e in AnalysisAgent(FakeModel(), sandbox).run(profile(), "sum", Path("x"))]
    assert sandbox.execute.call_count == 4
    assert events[-1].data["status"] == "failed"
    assert not any(e.event == "chart" for e in events)


@pytest.mark.asyncio
async def test_bad_output_is_repaired_and_engine_failure_is_terminal():
    sandbox = Mock()
    sandbox.execute.side_effect = [SandboxResult(status=SandboxStatus.COMPLETED, stdout="not JSON", duration_ms=1),
                                   SandboxResult(status=SandboxStatus.ENGINE_ERROR, stderr="socket", duration_ms=1)]
    events = [e async for e in AnalysisAgent(FakeModel(), sandbox).run(profile(), "sum", Path("x"))]
    assert sandbox.execute.call_count == 2
    assert events[-1].data["status"] == "failed"


@pytest.mark.parametrize("option", [
    {"series": []}, {"series": [{"type": "custom", "data": []}]},
    {"series": [{"type": "bar", "data": [float('nan')]}]},
    {"series": [{"type": "bar", "data": []}], "tooltip": {"formatter": "<script>"}},
])
def test_invalid_chart_rejected(option):
    with pytest.raises(ValueError):
        ChartSpec(option=option)


def test_chart_protocol_and_json_validation():
    valid = output().model_dump_json()
    assert parse_output(OUTPUT_MARKER + valid).chart.option["tooltip"]["renderMode"] == "richText"
    with pytest.raises(ValueError):
        parse_output(OUTPUT_MARKER + valid + "\n" + OUTPUT_MARKER + valid)


@pytest.mark.asyncio
async def test_missing_credentials_clear_error():
    with pytest.raises(ModelUnavailable, match="LLM_API_KEY"):
        await ModelClient(Settings(llm_api_key="", llm_model="")).complete([], Plan)
