import asyncio
import json
import logging
import threading
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.schemas.agent import AgentEvent, AnalysisRequest

router = APIRouter(prefix="/api/v1", tags=["analysis"])


def sse(event, sequence):
    data = json.dumps(event.data, ensure_ascii=False, allow_nan=False)
    return f"id: {sequence}\nevent: {event.event}\ndata: {data}\n\n"


@router.get("/system")
async def system_status(request: Request):
    state = request.app.state
    return {"model_configured": state.model.configured, "redis_available": await state.store.ping(),
            "model": state.settings.llm_model, "max_repairs": state.settings.agent_max_repairs}


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, request: Request):
    session = await request.app.state.store.session(str(session_id))
    if session is None:
        raise HTTPException(404, "Session missing, expired, or Redis unavailable.")
    return session


@router.post("/analyses")
async def analyze(body: AnalysisRequest, request: Request):
    state = request.app.state
    profile = await run_in_threadpool(state.datasets.get, body.dataset_id)
    if not state.model.configured:
        raise HTTPException(503, "请先在服务端配置 LLM_API_KEY 和 LLM_MODEL。")
    if state.analysis_slots.locked():
        raise HTTPException(429, "分析队列已满，请稍后重试。")
    await state.analysis_slots.acquire()
    session_id = str(body.session_id or uuid4())
    run_id = str(uuid4())
    cancelled = threading.Event()

    async def stream():
        queue = asyncio.Queue(maxsize=64)
        sequence = 0
        journal = []
        journal_bytes = 0
        status = "running"
        meta = {"session_id": session_id, "run_id": run_id, "dataset_id": str(body.dataset_id), "question": body.question}

        async def produce():
            nonlocal status
            try:
                await queue.put(AgentEvent(event="status", data={**meta, "state": "started"}))
                await state.store.session(session_id, {**meta, "status": "running", "events": []})
                cached, kind, vector = await state.store.find(profile.sha256, body.question) if body.use_cache else (None, None, None)
                if cached:
                    await queue.put(AgentEvent(event="status", data={"state": "cache_hit", "cache": kind}))
                    for item in cached:
                        await queue.put(AgentEvent.model_validate(item))
                    status = "completed"
                    return
                events = []
                async for event in state.agent.run(profile, body.question, state.datasets.root / str(body.dataset_id) / "dataset.parquet", cancelled):
                    if event.event == "done":
                        status = event.data["status"]
                    events.append(event.model_dump())
                    await queue.put(event)
                if status == "completed" and body.use_cache:
                    reusable = [e for e in events if e["event"] in {"plan", "code", "chart", "insight", "done"}]
                    await state.store.save(profile.sha256, body.question, reusable, vector)
            except asyncio.CancelledError:
                status = "cancelled"
                raise
            except Exception as error:
                from app.services.llm import ModelUnavailable
                logging.getLogger(__name__).exception("Analysis failed: %s", run_id)
                status = "failed"
                message = str(error) if isinstance(error, ModelUnavailable) else "分析未完成，请重试或检查服务端日志。"
                await queue.put(AgentEvent(event="error", data={"message": message, "recoverable": False}))
                await queue.put(AgentEvent(event="done", data={"status": "failed"}))
            finally:
                if not cancelled.is_set():
                    await queue.put(None)

        task = asyncio.create_task(produce())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=5)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if event is None:
                    break
                sequence += 1
                record = event.model_dump()
                encoded_size = len(json.dumps(record).encode())
                if journal_bytes + encoded_size <= 1_000_000:
                    journal.append(record)
                    journal_bytes += encoded_size
                yield sse(event, sequence)
        finally:
            cancelled.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if status == "running":
                status = "cancelled"
            state.analysis_slots.release()
            await state.store.session(session_id, {**meta, "status": status, "events": journal})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "X-Session-ID": session_id,
    })
