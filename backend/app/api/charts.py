import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, Request

from app.schemas.agent import ChartSpec

router = APIRouter(prefix="/api/v1/charts", tags=["charts"])


def render(chart: ChartSpec):
    with tempfile.TemporaryDirectory(prefix="chart-render-") as folder:
        try:
            result = subprocess.run([sys.executable, "-m", "app.services.chart_renderer"],
                input=chart.model_dump_json().encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env={**os.environ, "MPLCONFIGDIR": folder, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                     "PYTHONPATH": str(Path(__file__).resolve().parents[2])}, timeout=12, check=False)
        except subprocess.TimeoutExpired as error:
            raise HTTPException(422, "静态图表渲染超时，请减少图表数据。") from error
        if result.returncode or not result.stdout.startswith(b"\x89PNG"):
            raise HTTPException(422, "当前图表数据不支持静态渲染，请导出 JSON。")
        return result.stdout


@router.post("/png")
async def png(chart: ChartSpec, request: Request):
    slots = request.app.state.chart_slots
    if slots.locked():
        raise HTTPException(429, "图表渲染队列已满，请稍后重试。")
    async with slots:
        from starlette.concurrency import run_in_threadpool
        result = await run_in_threadpool(render, chart)
        return Response(result, media_type="image/png", headers={"Cache-Control": "no-store"})
