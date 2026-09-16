"""Delivery artifacts exercise real parsers; startup failures must not report success."""
import csv
import os
from pathlib import Path
import shutil
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def examples(tmp_path_factory):
    output = tmp_path_factory.mktemp("generated-examples")
    subprocess.run([sys.executable, str(ROOT / "examples/generate.py"), "--output", str(output),
                    "--format", "all"], check=True, capture_output=True)
    return output


@pytest.mark.parametrize("extension", ["csv", "xlsx", "parquet"])
def test_examples_are_uploadable_with_consistent_profiles(examples, extension, tmp_path):
    with TestClient(create_app(Settings(dataset_dir=tmp_path / "uploads"))) as client:
        for name, rows, columns in [("sales", 288, 10), ("financial_timeseries", 522, 5)]:
            path = examples / f"{name}.{extension}"
            response = client.post("/api/v1/datasets", files={"file": (path.name, path.read_bytes())})
            assert response.status_code == 201, response.text
            profile = response.json()
            assert (profile["row_count"], profile["column_count"]) == (rows, columns)
            assert len(profile["sample_rows"]) == 5
            if name == "sales":
                missing = next(c for c in profile["columns"] if c["name"] == "marketing_spend")
                assert missing["missing_count"] == 17
            else:
                assert all(c["missing_count"] == 0 for c in profile["columns"])


def test_examples_reproducible_and_never_overwrite(examples, tmp_path):
    command = [sys.executable, str(ROOT / "examples/generate.py"), "--output", str(tmp_path)]
    subprocess.run(command, check=True, capture_output=True)
    for name in ("sales.csv", "financial_timeseries.csv"):
        assert (examples / name).read_bytes() == (tmp_path / name).read_bytes()
    original = (tmp_path / "sales.csv").read_bytes()
    duplicate = subprocess.run(command, capture_output=True, text=True)
    assert duplicate.returncode == 1
    assert "no files were overwritten" in duplicate.stderr
    assert (tmp_path / "sales.csv").read_bytes() == original
    with (tmp_path / "sales.csv").open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    assert all(int(row["units"]) * int(row["unit_price"]) == int(row["revenue"]) for row in rows)


@pytest.fixture
def startup(tmp_path):
    project = tmp_path / "workspace with spaces"
    project.mkdir()
    (project / "scripts").mkdir()
    for name in ("start.sh", ".env.example", "docker-compose.yml", "scripts/verify_stack.py"):
        shutil.copyfile(ROOT / name, project / name)
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text("""#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$DOCKER_CALLS"
if [[ "$*" == 'compose up --help' ]]; then printf '%s\\n' '--wait-timeout'; fi
if [[ "$*" == 'info --format {{.OSType}}' ]]; then printf 'linux\\n'; fi
if [[ "$*" == *' up --build '* && "${FAIL_START:-}" == 1 ]]; then exit 1; fi
if [[ "$*" == *' exec -T '* ]]; then cat >/dev/null; fi
""")
    docker.chmod(0o755)
    env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"],
           "DOCKER_CALLS": str(tmp_path / "calls")}
    return project, env


def test_startup_preserves_env_and_does_not_execute_secrets(startup):
    project, env = startup
    marker = project / "must-not-exist"
    original = f'LLM_API_KEY=$(touch "{marker}")\nDOCKER_GID=123\n'
    (project / ".env").write_text(original)
    result = subprocess.run(["bash", str(project / "start.sh")], cwd=project.parent,
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (project / ".env").read_text() == original
    assert not marker.exists()
    calls = Path(env["DOCKER_CALLS"]).read_text()
    assert "--wait --wait-timeout 120 backend frontend" in calls
    assert "exec -T backend python -" in calls
    assert "touch" not in result.stdout + result.stderr + calls


def test_startup_creates_private_env_and_stops_on_failed_services(startup):
    project, env = startup
    result = subprocess.run(["bash", str(project / "start.sh")], env={**env, "FAIL_START": "1"},
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert (project / ".env").read_bytes() == (project / ".env.example").read_bytes()
    assert (project / ".env").stat().st_mode & 0o777 == 0o600
    assert "Workspace ready" not in result.stdout
    assert "exec -T" not in Path(env["DOCKER_CALLS"]).read_text()
    assert "data volumes have been preserved" in result.stderr
