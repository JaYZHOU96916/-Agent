from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SandboxStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    ENGINE_ERROR = "engine_error"


class SandboxResult(BaseModel):
    """Structured result returned by the untrusted-code Docker sandbox."""

    status: SandboxStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    duration_ms: int = Field(ge=0)
    timed_out: bool = False
    memory_limit_exceeded: bool = False
