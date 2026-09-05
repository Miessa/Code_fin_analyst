"""Shared types and validation rules for the benchmark bank."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


Identifier = Annotated[
    str,
    Field(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
MetricKey = Annotated[
    str,
    Field(min_length=2, max_length=96, pattern=r"^[a-z][a-z0-9_]*$"),
]


class StrEnum(str, Enum):
    pass


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class QualityLevel(StrEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class ObservationType(StrEnum):
    PROJECT = "project"
    SECTOR_STATISTIC = "sector_statistic"
    REFERENCE_POINT = "reference_point"
    FINANCING_INSTRUMENT = "financing_instrument"


class ValueStatus(StrEnum):
    REPORTED = "reported"
    DERIVED = "derived"
    ESTIMATED = "estimated"
    IMPUTED = "imputed"


class CanonicalModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_aware_datetime(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value


def validate_finite(value: float | None) -> float | None:
    if value is not None and not math.isfinite(value):
        raise ValueError("numeric values must be finite")
    return value


def validate_checksum(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.lower().removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ValueError("checksum must be a SHA-256 hexadecimal digest")
    return normalized


JsonValue = Any
