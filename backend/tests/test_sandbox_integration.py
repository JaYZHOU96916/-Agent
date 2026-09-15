"""Opt in with RUN_DOCKER_TESTS=1 after building data-analysis-sandbox:latest."""

import os

import pytest

from app.core.config import Settings
from app.schemas.sandbox import SandboxStatus
from app.services.sandbox import DockerSandboxExecutor

pytestmark = pytest.mark.skipif(os.getenv("RUN_DOCKER_TESTS") != "1", reason="requires Docker Engine and sandbox image")


@pytest.mark.parametrize(("code", "expected"), [
    ("import sys; print('hello'); print('stderr', file=sys.stderr)", SandboxStatus.COMPLETED),
    ("while True: pass", SandboxStatus.TIMED_OUT),
    ("blocks = []\nwhile True: blocks.append(bytearray(8 * 1024 * 1024))", SandboxStatus.MEMORY_LIMIT_EXCEEDED),
    ("open('/etc/forbidden', 'w')", SandboxStatus.FAILED),
    ("import socket; socket.create_connection(('1.1.1.1', 443), timeout=1)", SandboxStatus.FAILED),
])
def test_real_container(code: str, expected: SandboxStatus) -> None:
    executor = DockerSandboxExecutor(Settings(sandbox_timeout_seconds=3, sandbox_memory_limit_mb=64))
    result = executor.execute(code)
    assert result.status == expected, result
    if expected == SandboxStatus.COMPLETED:
        assert result.stdout == "hello\n"
        assert result.stderr == "stderr\n"
