from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Scalar = str | int | float | bool | None


class ColumnProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    name: str
    dtype: str
    missing_count: int = Field(ge=0)
    missing_fraction: float = Field(ge=0, le=1)


class DatasetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    dataset_id: UUID
    filename: str
    format: Literal["csv", "xlsx", "xls", "parquet"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(gt=0)
    row_count: int = Field(ge=0)
    column_count: int = Field(gt=0)
    columns: list[ColumnProfile]
    sample_rows: list[dict[str, Scalar]] = Field(max_length=5)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
