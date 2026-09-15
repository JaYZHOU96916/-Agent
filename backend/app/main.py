from fastapi import FastAPI

app = FastAPI(title="Automated Data Analysis Agent", version="0.1.0")


@app.get("/healthz", tags=["infrastructure"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
