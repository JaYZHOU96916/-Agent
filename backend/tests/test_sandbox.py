from unittest.mock import Mock

import pytest
from requests.exceptions import ReadTimeout
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.sandbox import SandboxStatus
from app.services.sandbox import DockerSandboxExecutor


def build_executor(container: Mock) -> tuple[DockerSandboxExecutor, Mock]:
    client = Mock()
    client.containers.create.return_value = container
    settings = Settings(sandbox_timeout_seconds=10, sandbox_memory_limit_mb=512)
    return DockerSandboxExecutor(settings=settings, client=client), client


def test_sandbox_uses_restrictive_docker_options() -> None:
    container = Mock()
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = (b"safe output\n", b"")
    container.attrs = {"State": {"OOMKilled": False}}
    executor, client = build_executor(container)

    result = executor.execute("print('safe output')")

    assert result.status is SandboxStatus.COMPLETED
    assert result.stdout == "safe output\n"
    kwargs = client.containers.create.call_args.kwargs
    assert kwargs["network_disabled"] is True
    assert kwargs["mem_limit"] == "512m"
    assert kwargs["pids_limit"] == 64
    assert kwargs["read_only"] is True
    assert kwargs["user"] == "65534:65534"
    assert kwargs["cap_drop"] == ["ALL"]
    assert kwargs["security_opt"] == ["no-new-privileges:true"]
    assert kwargs["tmpfs"] == {"/tmp": "rw,noexec,nosuid,size=64m"}
    assert container.put_archive.called
    assert container.remove.call_args.kwargs == {"force": True}


def test_timeout_kills_container_and_returns_streams() -> None:
    container = Mock()
    container.wait.side_effect = ReadTimeout("timeout")
    container.logs.return_value = (b"progress", b"")
    container.attrs = {"State": {"OOMKilled": False}}
    executor, _ = build_executor(container)

    result = executor.execute("while True: pass")

    assert result.status is SandboxStatus.TIMED_OUT
    assert result.timed_out is True
    assert result.stdout == "progress"
    container.kill.assert_called_once_with()
    container.remove.assert_called_once_with(force=True)


def test_oom_is_reported_as_memory_limit_exceeded() -> None:
    container = Mock()
    container.wait.return_value = {"StatusCode": 137}
    container.logs.return_value = (b"", b"")
    container.attrs = {"State": {"OOMKilled": True}}
    executor, _ = build_executor(container)

    result = executor.execute("x = 'a' * 1024**3")

    assert result.status is SandboxStatus.MEMORY_LIMIT_EXCEEDED
    assert result.memory_limit_exceeded is True
    assert result.exit_code == 137


def test_script_archive_contains_non_writable_executable_script() -> None:
    archive = DockerSandboxExecutor._script_archive("print('ok')")

    import io
    import tarfile

    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        member = tar.getmember("analysis.py")
        assert member.mode == 0o500
        assert tar.extractfile(member).read() == b"print('ok')"


def test_settings_reject_relaxed_resource_limits() -> None:
    with pytest.raises(ValidationError):
        Settings(sandbox_timeout_seconds=11)
    with pytest.raises(ValidationError):
        Settings(sandbox_memory_limit_mb=513)
