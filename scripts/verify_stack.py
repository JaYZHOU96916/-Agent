"""Run inside the backend container: verify actual services without calling a model."""
import sys

import httpx
import redis

from app.core.config import Settings
from app.schemas.sandbox import SandboxStatus
from app.services.sandbox import DockerSandboxExecutor


def main():
    settings = Settings()
    headers = {"X-API-Key": settings.api_token.get_secret_value()}
    with httpx.Client(timeout=15, headers=headers) as client:
        client.get("http://127.0.0.1:8000/healthz").raise_for_status()
        client.get("http://frontend:3000/").raise_for_status()
        # Also exercise the browser's real Next.js -> FastAPI proxy path and auth.
        response = client.get("http://frontend:3000/api/v1/system")
        response.raise_for_status()
        state = response.json()
        if not state["redis_available"]:
            raise RuntimeError("Redis unavailable through API")
    with redis.Redis.from_url(settings.redis_url, socket_timeout=5) as store:
        if not store.ping():
            raise RuntimeError("Redis ping failed")
    print("OK: frontend, backend, authenticated proxy and Redis", flush=True)

    result = DockerSandboxExecutor(settings).execute(
        "import pandas as pd, duckdb\n"
        "assert int(pd.Series([10, 20]).sum()) == 30\n"
        "assert duckdb.sql('select 1').fetchone()[0] == 1\n"
        "print('sandbox-ready')\n"
    )
    if result.status != SandboxStatus.COMPLETED or result.stdout.strip() != "sandbox-ready":
        print(f"FAIL: sandbox returned {result.status.value}. Check Docker socket GID, image and daemon access.", file=sys.stderr)
        return 1
    print("OK: actual isolated sandbox execution (Pandas + DuckDB)")
    print("Model configuration present; no paid API call was made." if state["model_configured"] else
          "Upload/profile mode: set LLM_API_KEY and LLM_MODEL in .env, then run ./start.sh again to enable analysis.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (httpx.HTTPError, redis.RedisError, RuntimeError, KeyError, ValueError) as error:
        # Avoid printing connection strings or credentials in terminal/CI output.
        print(f"FAIL: service verification ({type(error).__name__}). Check Compose service status and configuration.", file=sys.stderr)
        sys.exit(1)
