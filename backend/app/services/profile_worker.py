"""Parse data in a killable process; this worker never executes generated code."""

import json
import resource
import sys
from pathlib import Path


def main() -> int:
    folder, extension, row_limit, column_limit, memory_limit = sys.argv[1:]
    root = Path(folder)
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # macOS RLIMIT_AS is not reliably enforced. Linux deployments enforce this
    # parser budget in addition to the backend's container memory limit.
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    from app.services.profiling import InvalidDataset, profile_table, read_table

    try:
        frame, warnings = read_table(root / f"source.{extension}", extension, int(row_limit), int(column_limit), int(memory_limit))
        profile = profile_table(frame, warnings)
        # Normalize for subsequent analysis, without retaining the upload name as a path.
        frame.to_parquet(root / "dataset.parquet", index=False)
        (root / "result.json").write_text(json.dumps(profile, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        return 0
    except InvalidDataset as error:
        message = str(error)
    except Exception:
        # Parser exceptions may embed uploaded cell contents or host file paths.
        message = "Unable to parse dataset. Check file format, UTF-8 CSV encoding, and consistent column types."
    (root / "error.json").write_text(json.dumps({"detail": message}), encoding="utf-8")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
