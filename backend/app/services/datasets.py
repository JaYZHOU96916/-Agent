import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from app.core.config import Settings
from app.schemas.dataset import DatasetProfile


class DatasetError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class DatasetService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.dataset_dir.resolve()
        self._slots = threading.BoundedSemaphore(settings.profiling_concurrency)

    def create(self, source: BinaryIO, filename: str) -> DatasetProfile:
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not filename or len(filename) > 255 or any(ord(c) < 32 for c in filename):
            raise DatasetError(422, "Invalid filename.")
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in {"csv", "xlsx", "xls", "parquet"}:
            raise DatasetError(415, "Supported formats: CSV, XLSX, XLS, Parquet.")
        if not self._slots.acquire(blocking=False):
            raise DatasetError(503, "All profiling workers are busy; retry shortly.")
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.TemporaryDirectory(prefix=".pending-", dir=self.root) as staging:
                folder = Path(staging)
                size = 0
                digest = hashlib.sha256()
                with (folder / f"source.{extension}").open("xb") as target:
                    while chunk := source.read(64 * 1024):
                        size += len(chunk)
                        if size > self.settings.upload_max_bytes:
                            raise DatasetError(413, "File exceeds upload size limit.")
                        digest.update(chunk)
                        target.write(chunk)
                if not size:
                    raise DatasetError(422, "Empty file.")
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "app.services.profile_worker", str(folder), extension,
                         str(self.settings.dataset_max_rows), str(self.settings.dataset_max_columns),
                         str(self.settings.dataset_max_memory_bytes)],
                        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                             "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "ARROW_NUM_THREADS": "1"},
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=self.settings.profiling_timeout_seconds, check=False,
                    )
                except subprocess.TimeoutExpired as error:
                    raise DatasetError(422, "Dataset parsing exceeded the time limit.") from error
                if result.returncode:
                    error_file = folder / "error.json"
                    detail = json.loads(error_file.read_text())["detail"] if error_file.exists() else "Parser exceeded its resource budget or failed to start."
                    raise DatasetError(422, detail)
                profile = DatasetProfile(
                    dataset_id=uuid4(), filename=filename, format=extension, sha256=digest.hexdigest(),
                    size_bytes=size, created_at=datetime.now(timezone.utc),
                    **json.loads((folder / "result.json").read_text(encoding="utf-8")),
                )
                (folder / "profile.json").write_text(profile.model_dump_json(), encoding="utf-8")
                # Remove only our temporary input/intermediate metadata before publication.
                (folder / f"source.{extension}").unlink()
                (folder / "result.json").unlink()
                folder.rename(self.root / str(profile.dataset_id))
                return profile
        finally:
            self._slots.release()

    def get(self, dataset_id: UUID) -> DatasetProfile:
        try:
            return DatasetProfile.model_validate_json((self.root / str(dataset_id) / "profile.json").read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise DatasetError(404, "Dataset not found.") from error
